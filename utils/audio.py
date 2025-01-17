import discord
import asyncio
import io
import logging
import wave
import time
import struct
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

class GlobalSilenceWatcher(discord.sinks.WaveSink):
    def __init__(self, callback, timeout=3.0, min_duration=0.5, volume_threshold=0.20):
        super().__init__()
        self.callback = callback
        self.timeout = timeout
        self.min_duration = min_duration
        self.volume_threshold = volume_threshold
        self.last_audio = 0
        self.buffer = io.BytesIO()
        self.wave_writer = None
        self.start_time = None

    def write(self, data, user):
        if data:
            sound_data = struct.unpack("%sh" % (len(data) // 2), data)
            volume = max(sound_data) / 32768.0

            if volume > self.volume_threshold:
                if self.wave_writer is None:
                    self.buffer = io.BytesIO()
                    self.wave_writer = wave.open(self.buffer, 'wb')
                    self.wave_writer.setnchannels(2)
                    self.wave_writer.setsampwidth(2)
                    self.wave_writer.setframerate(48000)
                    self.start_time = time.time()
                self.last_audio = time.time()
                self.wave_writer.writeframes(data)

    async def check_silence(self):
        while True:
            if self.wave_writer and self.last_audio > 0 and (time.time() - self.last_audio) > self.timeout and (time.time() - self.start_time) >= self.min_duration:
                self.last_audio = 0
                self.wave_writer.close()
                self.wave_writer = None

                send_buffer = io.BytesIO(self.buffer.getvalue())

                self.buffer.seek(0)
                self.buffer.truncate()

                await self.callback(send_buffer)
            await asyncio.sleep(0.1)

    def cleanup(self):
        if self.wave_writer:
            self.wave_writer.close()
        self.buffer.close()
            
async def start_recording(voice_client, sink, channel_id):
    try:
        voice_client.start_recording(sink, on_audio_complete, channel_id)
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de l'enregistrement: {e}")

async def on_audio_complete(sink, channel_id):
    pass