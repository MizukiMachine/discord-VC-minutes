import discord
from discord.ext import commands
from typing import Dict, Optional
import asyncio

from services.scheduler.priority_scheduler import PriorityScheduler
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
        self.recorders: Dict[int, object] = {}
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
        pass
    
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
        pass
    
    async def handle_vc_leave(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        pass