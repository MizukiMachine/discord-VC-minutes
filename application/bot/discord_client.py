import discord
from discord.ext import commands
from typing import Dict, Optional
import asyncio

from services.scheduler.priority_scheduler import PriorityScheduler
from services.audio.recorder import AudioRecorder
from infrastructure.config.settings import EnvironmentConfig
from framework.error_code.errors import DetailedError, ErrorCode

class DiscordMinutesBot(commands.Bot):
    def __init__(self, config: Optional[EnvironmentConfig] = None):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(
            command_prefix='/',
            intents=intents,
            description='Discord議事録自動化Bot'
        )
        
        self.config = config or EnvironmentConfig()
        self.recorders: Dict[int, AudioRecorder] = {}
        self.scheduler = PriorityScheduler(
            max_concurrent=self.config.get_config('MAX_CONCURRENT_RECORDINGS') or 4
        )
    
    async def start_bot(self) -> None:
        token = self.config.get_config('DISCORD_BOT_TOKEN')
        if not token:
            raise DetailedError(
                ErrorCode.CONFIGURATION_ERROR,
                "Discord bot token is required"
            )
        await self.start(token)
    
    async def on_ready(self) -> None:
        if hasattr(self, 'guilds'):
            for guild in self.guilds:
                await self.scan_voice_channels(guild)
    
    async def scan_voice_channels(self, guild: discord.Guild) -> None:
        for vc in guild.voice_channels:
            if len(vc.members) > 0:
                non_bot_members = [m for m in vc.members if not m.bot]
                if non_bot_members:
                    await self.start_auto_recording(vc)
    
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ) -> None:
        if member.bot:
            return
            
        if before.channel != after.channel:
            if after.channel:
                await self.handle_vc_join(member, after.channel)
            if before.channel:
                await self.handle_vc_leave(member, before.channel)
    
    async def handle_vc_join(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        non_bot_members = [m for m in channel.members if not m.bot]
        if len(non_bot_members) == 1:
            await self.start_auto_recording(channel)
    
    async def handle_vc_leave(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        non_bot_members = [m for m in channel.members if not m.bot]
        if len(non_bot_members) == 0 and channel.id in self.recorders:
            await self.stop_recording(channel)
    
    async def start_auto_recording(self, channel: discord.VoiceChannel) -> None:
        if channel.id in self.recorders:
            return
            
        if self.scheduler.can_add_auto_recording(channel.id, len(channel.members)):
            await self.start_recording(channel, is_manual=False)
    
    async def start_recording(self, channel: discord.VoiceChannel, is_manual: bool = False) -> bool:
        if channel.id in self.recorders:
            return False
            
        try:
            if is_manual:
                replaced_vc = self.scheduler.add_manual_recording(channel.id, len(channel.members))
                if replaced_vc and replaced_vc in self.recorders:
                    await self.stop_recording_by_id(replaced_vc)
            else:
                if not self.scheduler.add_auto_recording(channel.id, len(channel.members)):
                    return False
            
            voice_client = await channel.connect()
            recorder = AudioRecorder(channel, voice_client)
            await recorder.start()
            
            self.recorders[channel.id] = recorder
            return True
            
        except Exception as e:
            print(f"Failed to start recording for {channel.name}: {e}")
            if channel.id in self.recorders:
                del self.recorders[channel.id]
            self.scheduler.remove_recording(channel.id)
            return False
    
    async def stop_recording(self, channel: discord.VoiceChannel) -> None:
        await self.stop_recording_by_id(channel.id)
    
    async def stop_recording_by_id(self, channel_id: int) -> None:
        if channel_id in self.recorders:
            try:
                recorder = self.recorders[channel_id]
                await recorder.stop()
                
                if recorder.voice_client and recorder.voice_client.is_connected():
                    await recorder.voice_client.disconnect()
                    
            except Exception as e:
                print(f"Error stopping recording for channel {channel_id}: {e}")
            finally:
                del self.recorders[channel_id]
                self.scheduler.remove_recording(channel_id)