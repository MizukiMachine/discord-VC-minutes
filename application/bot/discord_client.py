import discord
from discord.ext import commands
from typing import Dict, Optional
import asyncio

from services.scheduler.priority_scheduler import PriorityScheduler
from services.audio.recorder import AudioRecorder
from services.redis.buffer_manager import RedisBufferManager
from services.summary.openai_client import OpenAIClient
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
    
    @commands.command(name='sofar', help='現在のボイスチャンネルの議事録を要約します')
    async def sofar_command(self, ctx: commands.Context) -> None:
        """Generate and post summary of current voice channel discussion"""
        try:
            # Check if user is in a voice channel
            if not ctx.author.voice or not ctx.author.voice.channel:
                await ctx.send("❌ ボイスチャンネルに参加してからコマンドを使用してください。")
                return
            
            voice_channel = ctx.author.voice.channel
            channel_id = voice_channel.id
            
            # Check if recording is active for this channel
            if channel_id not in self.recorders:
                await ctx.send("❌ このボイスチャンネルで録音が開始されていません。")
                return
            
            # Check configuration
            openai_api_key = self.config.get_config('OPENAI_API_KEY')
            redis_url = self.config.get_config('REDIS_URL')
            
            if not openai_api_key or not redis_url:
                await ctx.send("❌ 設定が不完全です。OPENAI_API_KEYまたはREDIS_URLが設定されていません。")
                return
            
            # Notify user that processing started
            processing_msg = await ctx.send("🤖 議事録を要約中...")
            
            # Get audio data from Redis buffer
            buffer_manager = RedisBufferManager(
                core_service=self.config,
                redis_url=redis_url
            )
            
            try:
                audio_chunks = await buffer_manager.get_all_audio_chunks(str(channel_id))
                
                if not audio_chunks:
                    await processing_msg.edit(content="❌ 要約する音声データがありません。録音開始後しばらく待ってから再試行してください。")
                    return
                
                # Combine audio chunks for summarization
                combined_text = "\n".join(audio_chunks)
                
                # Initialize OpenAI client and summarize
                openai_client = OpenAIClient(
                    core_service=self.config,
                    api_key=openai_api_key
                )
                
                response = openai_client.summarize(combined_text)
                
                if response.success:
                    # Create embed for summary
                    embed = discord.Embed(
                        title="📜 議事録要約",
                        description=response.summary,
                        color=0x00FF00
                    )
                    embed.add_field(
                        name="📊 処理情報", 
                        value=f"トークン使用量: {response.total_tokens}\n処理段階: {response.stages}段階",
                        inline=False
                    )
                    embed.set_footer(text=f"チャンネル: {voice_channel.name}")
                    
                    await processing_msg.delete()
                    await voice_channel.send(embed=embed)
                    
                else:
                    await processing_msg.edit(content=f"❌ 要約処理でエラーが発生しました: {response.error_message}")
                    
            finally:
                await buffer_manager.close()
                
        except Exception as e:
            await ctx.send(f"❌ 予期しないエラーが発生しました: {str(e)}")
            print(f"Error in sofar command: {e}")