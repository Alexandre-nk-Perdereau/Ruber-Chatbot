import discord
from discord.ext import commands
from utils.gemini import generate_images, generate_response, handle_api_error, list_models, setup_gemini_api
from utils.attachments import MessageAttachment
import os
import re
import json
import logging
import asyncio
import io
import PIL.Image
import base64
from discord.ext import voice_recv
from utils.context import ContextManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="?", intents=intents)
channel_contexts = {}
ACTIVATED_CHANNELS_FILE = "activated_channels.json"
DISCORD_MESSAGE_LENGTH_LIMIT = 2000

def load_activated_channels():
    try:
        with open(ACTIVATED_CHANNELS_FILE, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_activated_channels():
    with open(ACTIVATED_CHANNELS_FILE, "w") as f:
        json.dump(list(activated_channels), f)

activated_channels = load_activated_channels()

def get_channel_context(channel_id):
    if channel_id not in activated_channels:
        logger.info(f"get_channel_context: Bot désactivé dans le channel {channel_id}")
        return None
    if channel_id not in channel_contexts:
        logger.info(f"get_channel_context: Création d'un contexte pour le channel {channel_id}")
        channel_contexts[channel_id] = ContextManager(channel_id)  # Changé de ChannelContext à ContextManager
    return channel_contexts[channel_id]

@bot.event
async def on_ready():
    logger.info(f"{bot.user} est prêt et connecté à Discord!")
    setup_gemini_api()

async def process_attachment(attachment):
    try:
        file_data = await attachment.read()
        if attachment.content_type.startswith('image/'):
            if attachment.size >= 20 * 1024 * 1024:
                return "FileTooLarge"
            try:
                with PIL.Image.open(io.BytesIO(file_data)) as img:
                    with io.BytesIO() as output_buffer:
                        img.save(output_buffer, format="PNG")
                        png_data = output_buffer.getvalue()
                return {
                    "mime_type": "image/png",
                    "data": base64.b64encode(png_data).decode("utf-8")
                }
            except Exception as e:
                logger.error(f"Erreur lors du traitement de l'image {attachment.filename}: {e}")
                return "ImageError"
        elif attachment.content_type.startswith('audio/'):
            if attachment.size >= 20 * 1024 * 1024:
                return "FileTooLarge"
            return {
                "mime_type": attachment.content_type,
                "data": base64.b64encode(file_data).decode("utf-8")
            }
        elif attachment.content_type == 'text/plain' or (attachment.content_type and attachment.content_type.startswith("application/")):
          if attachment.size >= 20 * 1024 * 1024:
              return "FileTooLarge"
          try:
              decoded_text = file_data.decode("utf-8")
              return {"mime_type": "text/plain", "data": decoded_text}
          except UnicodeDecodeError:
              logger.error(
                  f"Erreur de décodage du fichier {attachment.filename}. Assurez-vous qu'il est encodé en UTF-8."
              )
              return "DecodingError"
        elif attachment.content_type == 'video/mp4':
            if attachment.size >= 20 * 1024 * 1024:
                return "FileTooLarge"
            return {
                "mime_type": "video/mp4",
                "data": base64.b64encode(file_data).decode("utf-8")
            }
        else:
            logger.warning(f"Type de fichier non pris en charge pour {attachment.filename}: {attachment.content_type}")
            return "UnsupportedType"
    except Exception as e:
        logger.error(f"Erreur lors de la lecture de la pièce jointe {attachment.filename}: {e}")
        return "ReadError"

@bot.event
async def on_message(message):
    if message.author.bot:
        logger.info("on_message: Message ignoré (auteur = bot)")
        return

    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    if message.content.lower().startswith("(ignore)"):
        logger.info("on_message: Message ignoré (commence par '(ignore)')")
        return

    if re.match(r"^\W", message.content):
        logger.info("on_message: Message ignoré (caractère non-alphanumérique au début, mais pas une commande)")
        return

    context = get_channel_context(message.channel.id)
    if context is None:
        logger.info(f"on_message: Bot désactivé dans le channel {message.channel.id}, message ignoré")
        return

    attachment_handler = MessageAttachment()
    
    message_parts = [{"text": f"{message.author.display_name}: {message.content}"}]
    
    errors = []
    for attachment in message.attachments:
        processed_data, error = await attachment_handler.process_attachment(attachment)
        if error:
            errors.append(error)
        elif processed_data:
            message_parts.append(processed_data)

    # Notifier l'utilisateur des erreurs de pièces jointes s'il y en a
    if errors:
        error_message = "\n".join(errors)
        await message.channel.send(f"Erreurs lors du traitement des pièces jointes:\n{error_message}")

    # Si pas de contenu texte et toutes les pièces jointes en erreur, on ne poursuit pas
    if not message_parts:
        logger.info("on_message: Pas de contenu à traiter (pas de texte et pièces jointes en erreur)")
        return

    # Ajouter le message au contexte
    logger.info(f"on_message: Ajout du message au contexte: {message_parts}")
    context.add_message("user", message_parts)

    try:
        # Générer la réponse
        logger.info("on_message: Appel de generate_response")
        response = generate_response(context.get_context(), context.model_name, context.system_prompt)
        response_text = ""
        sent_message = None

        logger.info("on_message: Début de la boucle de réception des chunks")
        for chunk in response:
            logger.info(f"on_message: Chunk reçu: {chunk.text}")
            
            if sent_message and len(response_text) + len(chunk.text) > DISCORD_MESSAGE_LENGTH_LIMIT - 3:
                logger.info("on_message: Envoi du message actuel car le prochain chunk ferait dépasser la limite")
                await sent_message.edit(content=response_text)
                sent_message = await message.channel.send("...")
                response_text = ""
            
            response_text += chunk.text
            
            if sent_message:
                if len(response_text) <= DISCORD_MESSAGE_LENGTH_LIMIT - 3:
                    await sent_message.edit(content=response_text + "...")
                else:
                    await sent_message.edit(content=response_text)
                    sent_message = None
                    response_text = ""
            else:
                sent_message = await message.channel.send(response_text + "...")

            await asyncio.sleep(0.5)

        logger.info("on_message: Fin de la boucle de réception des chunks")
        
        # Gérer le dernier message
        if sent_message:
            if response_text:
                await sent_message.edit(content=response_text)
            else:
                await sent_message.delete()
        elif response_text:
            await message.channel.send(response_text)

        # Ajouter la réponse au contexte
        logger.info(f"on_message: Ajout de la réponse au contexte: {response_text}")
        context.add_message("model", response_text)

    except Exception as e:
        logger.error(f"on_message: Une erreur est survenue: {e}")
        error_message = handle_api_error(e)
        await message.channel.send(f"Une erreur est survenue: {error_message}")

@bot.command(name="activer", help="Active le bot dans le channel courant.")
async def activer(ctx):
    logger.info(f"'activer' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    activated_channels.add(ctx.channel.id)
    context = get_channel_context(ctx.channel.id)
    save_activated_channels()
    await ctx.send(f"Bot activé dans ce channel. Contexte initialisé avec le prompt système : '{context.system_prompt}'. Modèle: {context.model_name}")

@bot.command(name="desactiver", help="Désactive le bot dans le channel courant.")
async def desactiver(ctx):
    logger.info(f"'desactiver' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    if ctx.channel.id in activated_channels:
        activated_channels.remove(ctx.channel.id)
        if ctx.channel.id in channel_contexts:
            del channel_contexts[ctx.channel.id]
        save_activated_channels()
        await ctx.send("Bot désactivé dans ce channel.")
    else:
        await ctx.send("Le bot n'était pas activé dans ce channel.")

@bot.command(name="clear", help="Efface le contexte du channel courant.")
async def clear(ctx):
    logger.info(f"'clear' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    context = get_channel_context(ctx.channel.id)
    if context:
        context.clear_context()
        await ctx.send("Contexte effacé.")
    else:
        await ctx.send("Le bot n'est pas actif dans ce channel.")

@bot.command(name="download", help="Télécharge le contexte du channel courant.")
async def download(ctx):
    logger.info(f"'download' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    context = get_channel_context(ctx.channel.id)
    if context:
        context_str = context.download_context()
        with open("context.txt", "w", encoding="utf-8") as f:
            f.write(context_str)
        with open("context.txt", "rb") as f:
            await ctx.send(file=discord.File(f, "context.txt"))
        os.remove("context.txt")
    else:
        await ctx.send("Le bot n'est pas actif dans ce channel.")

@bot.command(name="set_system_prompt", help="Change le prompt système pour ce channel.")
async def set_system_prompt(ctx, *, new_system_prompt: str):
    logger.info(f"'set_system_prompt' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    context = get_channel_context(ctx.channel.id)
    if context:
        context.set_system_prompt(new_system_prompt)
        await ctx.send(f"Prompt système mis à jour pour ce channel : '{new_system_prompt}'")
    else:
        await ctx.send("Le bot n'est pas actif dans ce channel.")

@bot.command(name="set_context_size", help="Change la taille maximale du contexte pour ce channel.")
async def set_context_size(ctx, new_context_size: int):
    logger.info(f"'set_context_size' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    context = get_channel_context(ctx.channel.id)
    if context:
        context.set_context_size(new_context_size)
        await ctx.send(f"Taille maximale du contexte mise à jour pour ce channel : {new_context_size} tokens.")
    else:
        await ctx.send("Le bot n'est pas actif dans ce channel.")

@bot.command(name="set_model", help="Change le modèle utilisé pour ce channel.")
async def set_model(ctx, new_model: str):
    logger.info(f"'set_model' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    context = get_channel_context(ctx.channel.id)
    if context:
        context.set_model(new_model)
        await ctx.send(f"Modèle mis à jour pour ce channel : {new_model}")
    else:
        await ctx.send("Le bot n'est pas actif dans ce channel.")

@bot.command(name="info", help="Affiche les informations du bot pour le channel courant.")
async def info(ctx):
    logger.info(f"'info' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    context = get_channel_context(ctx.channel.id)
    if context:
        await ctx.send(f"Voici les paramètres utilisés par Ruber dans ce channel:\n- Prompt Système: {context.system_prompt}\n- Modèle: {context.model_name}\n- Taille du contexte: {context.context_size} tokens")
    else:
        await ctx.send("Le bot n'est pas actif dans ce channel.")

@bot.command(name="imagen", help="Génère une image à partir d'un prompt.")
async def imagen(ctx, prompt: str, aspect_ratio: str = "1:1", negative_prompt: str = None):
    logger.info(f"'imagen' command exécutée par {ctx.author} dans le channel {ctx.channel.id} avec le prompt: '{prompt}', aspect ratio: '{aspect_ratio}', negative prompt: '{negative_prompt}'")
    if ":" not in aspect_ratio:
        await ctx.send("Erreur : Le format de l'aspect ratio doit être 'nombre:nombre'. Par exemple : '1:1', '3:4', '16:9'.")
        return
    await ctx.send("Génération de l'image en cours...")
    try:
        result = generate_images(prompt, aspect_ratio=aspect_ratio, negative_prompt=negative_prompt)
        for i, image in enumerate(result.images):
            with io.BytesIO() as image_binary:
                image.save(image_binary, 'PNG')
                image_binary.seek(0)
                if len(result.images) > 1:
                    await ctx.send(f"Image {i+1} sur {len(result.images)}:", file=discord.File(fp=image_binary, filename=f'image_{i+1}.png'))
                else:
                    await ctx.send(file=discord.File(fp=image_binary, filename='image.png'))
    except Exception as e:
        error_message = handle_api_error(e)
        await ctx.send(f"Erreur lors de la génération de l'image : {error_message}")

@bot.command(name="debug_listmodels", help="Liste les modèles Gemini disponibles et leurs méthodes supportées.")
async def debug_listmodels(ctx):
    logger.info(f"'debug_listmodels' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
    try:
        models_info = list_models()
        response_text = "Modèles disponibles:\n"
        for model in models_info:
            response_text += f"- **{model.name}**\n"
            response_text += f"  - Description: {model.description}\n"
            response_text += f"  - Méthodes supportées: {', '.join(model.supported_generation_methods)}\n"
        if len(response_text) > DISCORD_MESSAGE_LENGTH_LIMIT:
            for i in range(0, len(response_text), DISCORD_MESSAGE_LENGTH_LIMIT):
                await ctx.send(response_text[i:i + DISCORD_MESSAGE_LENGTH_LIMIT])
        else:
            await ctx.send(response_text)
    except Exception as e:
        error_message = handle_api_error(e)
        await ctx.send(f"Erreur lors de la récupération des modèles : {error_message}")
