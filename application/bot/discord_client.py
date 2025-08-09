import discord
from discord.ext import commands
from typing import Dict, Optional
import asyncio
import time

from services.audio.recorder import AudioRecorder
from services.redis.buffer_manager import RedisBufferManager
from services.summary.openai_client import OpenAIClient
from infrastructure.config.settings import EnvironmentConfig
from framework.error_code.errors import DetailedError, ErrorCode
from application.ui.panel_manager import PanelManager
from framework.interfaces.ui import PanelState

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
        self.panel_manager = PanelManager(self.config, self)
        self.recording_start_times: Dict[int, float] = {}
    
    async def start_bot(self) -> None:
        token = self.config.get_config('DISCORD_BOT_TOKEN')
        if not token:
            raise DetailedError(
                ErrorCode.CONFIGURATION_ERROR,
                "Discord bot token is required"
            )
        await self.start(token)
    
    async def on_ready(self) -> None:
        print(f"🤖 Bot is ready! Logged in as {self.user}")
        if hasattr(self, 'guilds'):
            for guild in self.guilds:
                await self.setup_permanent_panels(guild)
                await self.scan_voice_channels(guild)
    
    async def setup_permanent_panels(self, guild: discord.Guild) -> None:
        """Setup permanent control panels for all voice channels"""
        print(f"📋 Setting up permanent panels for guild: {guild.name}")
        for vc in guild.voice_channels:
            try:
                # Create panel state for waiting state
                panel_state = self.create_panel_state(vc)
                
                # Check if panel already exists for this channel
                if vc.id not in self.panel_manager.panels:
                    await self.panel_manager.post_panel(vc, panel_state)
                    print(f"✅ Posted permanent panel for {vc.name}")
                else:
                    # Update existing panel
                    await self.panel_manager.update_panel(vc, panel_state)
                    print(f"🔄 Updated existing panel for {vc.name}")
                    
            except Exception as e:
                print(f"❌ Failed to setup panel for {vc.name}: {e}")
    
    async def scan_voice_channels(self, guild: discord.Guild) -> None:
        """v2.0: 既存参加者がいるVCで自動録音開始"""
        print(f"🔍 Scanning voice channels in {guild.name}")
        for vc in guild.voice_channels:
            non_bot_members = [m for m in vc.members if not m.bot]
            if non_bot_members:
                print(f"👥 Found {len(non_bot_members)} users in {vc.name}, starting auto recording...")
                await self.start_auto_recording(vc)
                # Update panel
                panel_state = self.create_panel_state(vc)
                if vc.id in self.panel_manager.panels:
                    await self.panel_manager.update_panel(vc, panel_state)
    
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
            # 最初の人が参加したら自動録音開始
            await self.start_auto_recording(channel)
        
        # パネルの状態を更新
        panel_state = self.create_panel_state(channel)
        if channel.id in self.panel_manager.panels:
            await self.panel_manager.update_panel(channel, panel_state)
    
    async def handle_vc_leave(self, member: discord.Member, channel: discord.VoiceChannel) -> None:
        non_bot_members = [m for m in channel.members if not m.bot]
        if len(non_bot_members) == 0 and channel.id in self.recorders:
            await self.stop_recording(channel)
        
        # パネルの状態を更新（メンバー数変更を反映）
        panel_state = self.create_panel_state(channel)
        if channel.id in self.panel_manager.panels:
            await self.panel_manager.update_panel(channel, panel_state)
    
    async def start_auto_recording(self, channel: discord.VoiceChannel) -> None:
        """v2.0: スケジューラー不使用、直接録音開始"""
        if channel.id in self.recorders:
            print(f"🔄 Recording already active for {channel.name}")
            return
        
        try:
            print(f"🎙️ Starting auto recording for {channel.name}")
            
            # Check if bot is already connected to this guild
            voice_client = None
            for vc in self.voice_clients:
                if vc.guild == channel.guild:
                    if vc.channel != channel:
                        await vc.disconnect()
                    else:
                        voice_client = vc
                        break
            
            if not voice_client:
                # Connect to voice channel
                try:
                    voice_client = await channel.connect()
                    print(f"🔗 Connected to {channel.name}")
                except Exception as e:
                    print(f"❌ Failed to connect to {channel.name}: {e}")
                    return
            
            # Create AudioRecorder with v1.0 interface
            recorder = AudioRecorder(channel, voice_client)
            
            # Start recording
            await recorder.start()
            self.recorders[channel.id] = recorder
            self.recording_start_times[channel.id] = time.time()
            print(f"✅ Auto recording started for {channel.name}")
                
        except Exception as e:
            print(f"❌ Error starting auto recording for {channel.name}: {e}")
    
    
    async def stop_recording(self, channel: discord.VoiceChannel) -> None:
        await self.stop_recording_by_id(channel.id)
    
    async def stop_recording_by_id(self, channel_id: int) -> None:
        """v2.0: スケジューラー不使用の録音停止"""
        if channel_id in self.recorders:
            try:
                print(f"🛑 Stopping recording for channel {channel_id}")
                recorder = self.recorders[channel_id]
                await recorder.stop()
                
                # VoiceClient切断は AudioRecorder内で処理される
                    
            except Exception as e:
                print(f"❌ Error stopping recording for channel {channel_id}: {e}")
            finally:
                del self.recorders[channel_id]
                if channel_id in self.recording_start_times:
                    del self.recording_start_times[channel_id]
                
                # Update control panel
                channel = self.get_channel(channel_id)
                if channel:
                    panel_state = self.create_panel_state(channel)
                    await self.panel_manager.update_panel(channel, panel_state)
                    print(f"✅ Recording stopped for {channel.name}")
    
    
    def create_panel_state(self, channel: discord.VoiceChannel) -> PanelState:
        """Create PanelState from bot's current state"""
        # 常にリスニング状態として扱う（シンプル化）
        is_recording = True
        elapsed_time = 0
        
        non_bot_members = [m for m in channel.members if not m.bot]
        member_count = len(non_bot_members)
        
        return PanelState(
            channel_id=channel.id,
            is_recording=is_recording,
            elapsed_time=elapsed_time,
            member_count=member_count
        )
    
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Handle button interactions"""
        try:
            # Discord.pyバージョン対応: data.custom_idを確認
            if not hasattr(interaction, 'data') or not interaction.data:
                print(f"❌ No interaction data")
                return
                
            custom_id = interaction.data.get('custom_id')
            print(f"🎯 Interaction received: {custom_id}")
            
            if not custom_id:
                return
            
            parts = custom_id.split('_')
            if len(parts) != 2:
                print(f"❌ Invalid custom_id format: {custom_id}")
                return
            
            action, channel_id_str = parts
            try:
                channel_id = int(channel_id_str)
            except ValueError:
                print(f"❌ Invalid channel_id: {channel_id_str}")
                return
            
            print(f"📝 Processing {action} for channel {channel_id}")
            
            if action == "sofar":
                await self.panel_manager.handle_summary(interaction, channel_id)
                print(f"✅ Summary request processed for channel {channel_id}")
        except Exception as e:
            print(f"❌ Error in interaction handler: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
            except:
                pass