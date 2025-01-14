import discord
import asyncio
import io
import logging
from elevenlabs.client import ElevenLabs
from utils.config import get_elevenlabs_api_key, get_elevenlabs_voice_id, get_elevenlabs_model_id

logger = logging.getLogger(__name__)

async def join_voice_channel(voice_channel):
    """Rejoint un canal vocal."""
    try:
        voice_client = await voice_channel.connect()
        return voice_client
    except Exception as e:
        logger.error(f"Erreur lors de la connexion au canal vocal: {e}")
        return None

async def leave_voice_channel(guild_id, voice_clients):
    """Quitte un canal vocal."""
    if guild_id in voice_clients:
        try:
            await voice_clients[guild_id].disconnect()
            del voice_clients[guild_id]
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion du canal vocal: {e}")

async def play_tts(voice_client, text):
    """Joue le texte en TTS dans le canal vocal."""
    try:
        temp_file = io.BytesIO()
        elevenlabs_client = ElevenLabs(api_key=get_elevenlabs_api_key())
        audio_stream = elevenlabs_client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=get_elevenlabs_voice_id(),
            model_id=get_elevenlabs_model_id(),
            output_format="mp3_44100_128"
        )
        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                temp_file.write(chunk)
        temp_file.seek(0)
        audio_source = discord.FFmpegPCMAudio(
            temp_file,
            pipe=True,
            before_options='-f mp3',
            options='-acodec pcm_s16le -ar 44100 -ac 2'
        )
        if voice_client.is_playing():
            voice_client.stop()
        voice_client.play(audio_source, after=lambda e: temp_file.close() if e is None else print(f'Error: {e}'))
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture TTS: {e}")