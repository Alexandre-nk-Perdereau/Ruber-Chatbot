# utils/audio.py
import discord
from discord.ext import commands, voice_recv
import wave
import os
import asyncio
import logging
import audioop

logger = logging.getLogger(__name__)

class VoiceRecorder:
    def __init__(self, bot, voice_client: discord.VoiceClient, user: discord.Member):
        self.bot = bot
        self.voice_client = voice_client
        self.user = user
        self.audio_data = {}
        self.recording = False
        self.filename = None
        self.last_voice_activity = None
        self.check_silence_task = None

    async def start_recording(self):
        if not self.recording:
            self.recording = True
            recordings_dir = "recordings"
            if not os.path.exists(recordings_dir):
                os.makedirs(recordings_dir)
            self.filename = os.path.join(recordings_dir, f"{self.user.id}-{int(discord.utils.time_snowflake(discord.utils.utcnow()))}.wav")
            self.audio_data[self.user.id] = []
            # On ne relance pas l'écoute ici, c'est fait dans join_vc
            # self.voice_client.listen(voice_recv.BasicSink(self.write_audio))
            self.last_voice_activity = discord.utils.utcnow().timestamp()
            logger.info(f"Démarrage de l'enregistrement pour {self.user.display_name} dans {self.filename}")

    async def stop_recording(self):
        if self.recording:
            self.recording = False
            if self.user.id in self.audio_data and self.audio_data[self.user.id]:  # Vérifie s'il y a des données audio
                audio_data = self.audio_data.pop(self.user.id)
                try:
                    with wave.open(self.filename, 'wb') as wave_file:
                        wave_file.setnchannels(2)
                        wave_file.setsampwidth(2)
                        wave_file.setframerate(48000)
                        wave_file.writeframes(b"".join(audio_data))
                    logger.info(f"Arrêt de l'enregistrement pour {self.user.display_name}. Fichier sauvegardé : {self.filename}")
                except Exception as e:
                    logger.error(f"Erreur lors de la sauvegarde du fichier audio : {e}")
            else:
                logger.info(f"Arrêt de l'enregistrement pour {self.user.display_name}. Aucune donnée audio à sauvegarder.")

    def write_audio(self, user, data):
        logger.info(f"write_audio called with user: {user.display_name} ({user.id})")  # LOG
        if self.recording and user.id == self.user.id:
            self.audio_data.setdefault(user.id, []).append(data.pcm)
            rms = audioop.rms(data.pcm, 2)
            logger.info(f"RMS value: {rms}")
            if rms > 3:  # Seuil encore plus bas
                self.last_voice_activity = discord.utils.utcnow().timestamp()
                logger.info(f"Voice activity detected from {user.display_name}")
        else:
            logger.info(f"write_audio: Not recording or wrong user. self.recording: {self.recording}, user.id: {user.id}, self.user.id: {self.user.id}")  # LOG

    def clear_audio(self, user_id):
        if user_id in self.audio_data:
            del self.audio_data[user_id]
            logger.info(f"Données audio effacées pour l'utilisateur ID {user_id}")

    async def on_silence(self, user, *args):
        if user is not None and user.id == self.user.id:
            logger.info(f"Silence détecté pour {self.user.display_name}, arrêt de l'enregistrement.")
            if self.recording:
              await self.stop_recording()
              # On ne relance pas l'enregistrement ici, check_silence s'en charge
              # await self.start_recording()