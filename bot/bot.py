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
from utils.context import ContextManager
from utils.audio import join_voice_channel, leave_voice_channel, play_tts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

channel_contexts = {}
ACTIVATED_CHANNELS_FILE = "activated_channels.json"
DISCORD_MESSAGE_LENGTH_LIMIT = 2000
tts_enabled_channels = set()
voice_clients = {}

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
        channel_contexts[channel_id] = ContextManager(channel_id)
    return channel_contexts[channel_id]

class BotCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.attachment_handler = MessageAttachment()
        setup_gemini_api()
        
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{self.bot.user} est prêt et connecté à Discord!")
        setup_gemini_api()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            logger.info("on_message: Message ignoré (auteur = bot)")
            return

        if message.content.startswith(self.bot.command_prefix):
            logger.info("on_message: Message ignoré (start with command prefix)")
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

        message_parts = [{"text": f"{message.author.display_name}: {message.content}"}]

        errors = []
        for attachment in message.attachments:
            processed_data, error = await self.attachment_handler.process_attachment(attachment)
            if error:
                errors.append(error)
            elif processed_data:
                if processed_data.get("mime_type") == "text/plain":
                    message_parts[0]["text"] += "\n" + processed_data["data"]
                else:
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
                    if message.channel.id in tts_enabled_channels and message.guild.id in voice_clients:
                        await play_tts(voice_clients[message.guild.id], response_text)
                else:
                    await sent_message.delete()
            elif response_text:
                await message.channel.send(response_text)
                if message.channel.id in tts_enabled_channels and message.guild.id in voice_clients:
                    await play_tts(voice_clients[message.guild.id], response_text)

        # Ajouter la réponse au contexte
            logger.info(f"on_message: Ajout de la réponse au contexte: {response_text}")
            context.add_message("model", response_text)

        except Exception as e:
            logger.error(f"on_message: Une erreur est survenue: {e}")
            error_message = handle_api_error(e)
            await message.channel.send(f"Une erreur est survenue: {error_message}")

    @commands.command(name="activer", help="Active le bot dans le channel courant.")
    async def activer(self, ctx):
        logger.info(f"'activer' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
        activated_channels.add(ctx.channel.id)
        context = get_channel_context(ctx.channel.id)
        save_activated_channels()
        await ctx.send(f"Bot activé dans ce channel. Contexte initialisé avec le prompt système : '{context.system_prompt}'. Modèle: {context.model_name}")

    @commands.command(name="desactiver", help="Désactive le bot dans le channel courant.")
    async def desactiver(self, ctx):
        logger.info(f"'desactiver' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
        if ctx.channel.id in activated_channels:
            activated_channels.remove(ctx.channel.id)
            if ctx.channel.id in tts_enabled_channels:
                tts_enabled_channels.remove(ctx.channel.id)
                await leave_voice_channel(ctx.guild.id, voice_clients)
            if ctx.channel.id in channel_contexts:
                del channel_contexts[ctx.channel.id]
            save_activated_channels()
            await ctx.send("Bot désactivé dans ce channel.")
        else:
            await ctx.send("Le bot n'était pas activé dans ce channel.")

    @commands.command(name="clear", help="Efface le contexte du channel courant.")
    async def clear(self, ctx):
        logger.info(f"'clear' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
        context = get_channel_context(ctx.channel.id)
        if context:
            context.clear_context()
            await ctx.send("Contexte effacé.")
        else:
            await ctx.send("Le bot n'est pas actif dans ce channel.")

    @commands.command(name="download", help="Télécharge le contexte du channel courant.")
    async def download(self, ctx):
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

    @commands.command(name="set_system_prompt", help="Change le prompt système pour ce channel.")
    async def set_system_prompt(self, ctx, *, new_system_prompt: str):
        logger.info(f"'set_system_prompt' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
        context = get_channel_context(ctx.channel.id)
        if context:
            context.set_system_prompt(new_system_prompt)
            await ctx.send(f"Prompt système mis à jour pour ce channel : '{new_system_prompt}'")
        else:
            await ctx.send("Le bot n'est pas actif dans ce channel.")

    @commands.command(name="set_context_size", help="Change la taille maximale du contexte pour ce channel.")
    async def set_context_size(self, ctx, new_context_size: int):
        logger.info(f"'set_context_size' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
        context = get_channel_context(ctx.channel.id)
        if context:
            context.set_context_size(new_context_size)
            await ctx.send(f"Taille maximale du contexte mise à jour pour ce channel : {new_context_size} tokens.")
        else:
            await ctx.send("Le bot n'est pas actif dans ce channel.")

    @commands.command(name="set_model", help="Change le modèle utilisé pour ce channel.")
    async def set_model(self, ctx, new_model: str):
        logger.info(f"'set_model' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
        context = get_channel_context(ctx.channel.id)
        if context:
            context.set_model(new_model)
            await ctx.send(f"Modèle mis à jour pour ce channel : {new_model}")
        else:
            await ctx.send("Le bot n'est pas actif dans ce channel.")

    @commands.command(name="info", help="Affiche les informations du bot pour le channel courant.")
    async def info(self, ctx):
        logger.info(f"'info' command exécutée par {ctx.author} dans le channel {ctx.channel.id}")
        context = get_channel_context(ctx.channel.id)
        if context:
            await ctx.send(f"Voici les paramètres utilisés par Ruber dans ce channel:\n- Prompt Système: {context.system_prompt}\n- Modèle: {context.model_name}\n- Taille du contexte: {context.context_size} tokens")
        else:
            await ctx.send("Le bot n'est pas actif dans ce channel.")

    @commands.command(name="imagen", help="Génère une image à partir d'un prompt.")
    async def imagen(self, ctx, prompt: str, aspect_ratio: str = "1:1", negative_prompt: str = None):
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

    @commands.command(name="debug_listmodels", help="Liste les modèles Gemini disponibles et leurs méthodes supportées.")
    async def debug_listmodels(self, ctx):
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

    @commands.command(name="tts", help="Active/désactive la lecture vocale des réponses du bot.")
    async def tts(self, ctx):
        """Active ou désactive le TTS pour ce canal."""
        if ctx.channel.id not in activated_channels:
            await ctx.send("Le bot n'est pas activé dans ce canal. Utilisez d'abord ?activer")
            return

        if not ctx.author.voice:
            await ctx.send("Vous devez être dans un canal vocal pour utiliser cette commande.")
            return

        if ctx.channel.id in tts_enabled_channels:
        # Désactivation du TTS
            tts_enabled_channels.remove(ctx.channel.id)
            await leave_voice_channel(ctx.guild.id, voice_clients)
            await ctx.send("Lecture vocale désactivée pour ce canal.")
        else:
        # Activation du TTS
            voice_client = await join_voice_channel(ctx.author.voice.channel)
            if voice_client:
                voice_clients[ctx.guild.id] = voice_client
                tts_enabled_channels.add(ctx.channel.id)
                await ctx.send("Lecture vocale activée pour ce canal.")
            else:
                await ctx.send("Impossible de rejoindre le canal vocal.")
                
def setup_bot(bot):
    bot.add_cog(BotCommands(bot))