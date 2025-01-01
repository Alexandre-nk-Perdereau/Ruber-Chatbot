import discord
import wave
import os
import asyncio
import logging
import audioop

logger = logging.getLogger(__name__)

class VoiceRecorder:
    def __init__(self, voice_client: discord.VoiceClient, user: discord.Member):
        self.voice_client = voice_client
        self.user = user
        self.audio_data = []
        self.filename = None
        self.recording = False
        self.last_voice_activity = None
        self.silence_threshold = 3
        self.silence_duration_threshold = 2.0
        self.min_recording_duration = 1.0
        self.last_packet_time = None
        self.wave_file = None

    async def start_recording(self):
        if not self.recording:
            self.recording = True
            self.last_voice_activity = discord.utils.utcnow().timestamp()
            logger.info(f"Recording started for {self.user.display_name}")

    async def stop_recording(self):
        if self.recording:
            self.recording = False
            recording_duration = discord.utils.utcnow().timestamp() - (self.last_voice_activity - self.silence_duration_threshold)
            if self.wave_file:
                self.wave_file.close()
                self.wave_file = None
            if recording_duration >= self.min_recording_duration:
                logger.info(f"Recording stopped for {self.user.display_name}. Saved to {self.filename}")
            else:
                logger.info(f"Recording stopped for {self.user.display_name}. Discarded due to short duration.")
                if self.filename and os.path.exists(self.filename):
                    os.remove(self.filename)
            self.audio_data = []
            self.filename = None

    def write_audio(self, user, data):
        self.last_packet_time = discord.utils.utcnow().timestamp()
        if self.recording and user.id == self.user.id:
            rms = audioop.rms(data.pcm, 2)
            if rms > self.silence_threshold:
                self.last_voice_activity = discord.utils.utcnow().timestamp()
                if not self.filename:
                    recordings_dir = "recordings"
                    if not os.path.exists(recordings_dir):
                        os.makedirs(recordings_dir)
                    self.filename = os.path.join(recordings_dir, f"{self.user.id}-{int(discord.utils.time_snowflake(discord.utils.utcnow()))}.wav")
                    self.wave_file = wave.open(self.filename, 'wb')
                    self.wave_file.setnchannels(2)
                    self.wave_file.setsampwidth(2)
                    self.wave_file.setframerate(48000)
                self.audio_data.append(data.pcm)
                self.wave_file.writeframes(data.pcm)
            else:
                if discord.utils.utcnow().timestamp() - self.last_voice_activity > self.silence_duration_threshold:
                    asyncio.run_coroutine_threadsafe(self.handle_silence(), self.voice_client.loop)

    async def handle_silence(self):
        await self.stop_recording()
        await self.start_recording()