import discord
from discord.ext import commands
from typing import Dict, Optional

from framework.interfaces.ui import UIService, PanelState, PanelProvider, ButtonInteractionHandler
from infrastructure.config.settings import EnvironmentConfig


class PanelManager(UIService):
    """Discord control panel manager implementing UIService interface"""
    
    def __init__(self, config: EnvironmentConfig, bot: commands.Bot):
        self.config = config
        self.bot = bot
        self.panels: Dict[int, discord.Message] = {}
    
    async def create_embed(self, state: PanelState, channel_name: str) -> discord.Embed:
        """Create control panel embed"""
        if state.is_recording:
            title = "🔴 録音中 - Discord議事録Bot"
            color = 0xFF0000
        else:
            title = "⚪ 待機中 - Discord議事録Bot" 
            color = 0x808080
        
        embed = discord.Embed(
            title=title,
            description=f"**チャンネル**: {channel_name}",
            color=color
        )
        
        return embed
    
    def create_view(self, state: PanelState) -> discord.ui.View:
        """Create control panel view with buttons"""
        view = discord.ui.View(timeout=None)
        
        buttons = [
            ("🔴停止", discord.ButtonStyle.danger, not state.is_recording, "stop"),
            ("📜今まで", discord.ButtonStyle.primary, not state.is_recording, "sofar"), 
            ("💾過去30分", discord.ButtonStyle.secondary, not state.is_recording, "save30"),
            ("🔴録音開始", discord.ButtonStyle.success, state.is_recording, "start")
        ]
        
        for label, style, disabled, action in buttons:
            button = discord.ui.Button(
                label=label, 
                style=style, 
                disabled=disabled,
                custom_id=f"{action}_{state.channel_id}"
            )
            view.add_item(button)
        
        return view
    
    async def post_panel(self, channel: discord.VoiceChannel, state: PanelState) -> Optional[discord.Message]:
        """Post control panel to voice channel's text chat"""
        try:
            # Find corresponding text channel
            text_channel = None
            for text_ch in channel.guild.text_channels:
                if text_ch.name == f"{channel.name.lower().replace(' ', '-')}" or \
                   text_ch.name == f"{channel.name.lower()}-text" or \
                   text_ch.category == channel.category:
                    text_channel = text_ch
                    break
            
            if not text_channel:
                # Use first text channel as fallback
                text_channel = channel.guild.text_channels[0]
            
            embed = await self.create_embed(state, channel.name)
            view = self.create_view(state)
            
            message = await text_channel.send(embed=embed, view=view)
            self.panels[channel.id] = message
            
            return message
            
        except Exception as e:
            print(f"Failed to post panel for channel {channel.name}: {e}")
            return None
    
    async def update_panel(self, channel: discord.VoiceChannel, state: PanelState) -> None:
        """Update existing control panel"""
        if channel.id not in self.panels:
            return
        
        try:
            message = self.panels[channel.id]
            embed = await self.create_embed(state, channel.name)
            view = self.create_view(state)
            
            await message.edit(embed=embed, view=view)
            
        except Exception as e:
            print(f"Failed to update panel for channel {channel.name}: {e}")
            # Remove invalid panel reference
            if channel.id in self.panels:
                del self.panels[channel.id]
    
    async def handle_stop(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle stop recording button"""
        try:
            await interaction.response.send_message("🔴 録音を停止しました", ephemeral=True)
            
            channel = self.bot.get_channel(channel_id)
            if channel:
                await self.bot.stop_recording(channel)
                
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
    
    async def handle_summary(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle summary request button"""
        try:
            await interaction.response.send_message("📜 議事録を要約中...", ephemeral=True)
            
            # Simulate context for sofar command
            class MockContext:
                def __init__(self, author, channel):
                    self.author = author
                    self.channel = channel
                    
                async def send(self, *args, **kwargs):
                    pass  # Handled by sofar command itself
            
            # Get channel for context
            channel = self.bot.get_channel(channel_id)
            if channel and hasattr(channel, 'guild'):
                # Find text channel for this voice channel
                for text_ch in channel.guild.text_channels:
                    if text_ch.name == f"{channel.name.lower().replace(' ', '-')}" or \
                       text_ch.name == f"{channel.name.lower()}-text" or \
                       text_ch.category == channel.category:
                        mock_ctx = MockContext(interaction.user, text_ch)
                        sofar_command = self.bot.get_command('sofar')
                        if sofar_command:
                            await sofar_command(mock_ctx)
                        break
                
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
    
    async def handle_save_transcript(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle save transcript button - save past 30 min transcript to text channel"""
        try:
            await interaction.response.send_message("💾 過去30分の音声を保存中...", ephemeral=True)
            
            from services.redis.buffer_manager import RedisBufferManager
            
            # Get configuration
            redis_url = self.config.get_config('REDIS_URL')
            if not redis_url:
                await interaction.edit_original_response(content="❌ REDIS_URLが設定されていません。")
                return
            
            # Get voice channel
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await interaction.edit_original_response(content="❌ チャンネルが見つかりません。")
                return
            
            # Initialize Redis buffer manager
            buffer_manager = RedisBufferManager(
                core_service=self.config,
                redis_url=redis_url
            )
            
            try:
                # Get all transcript chunks
                transcript_chunks = await buffer_manager.get_all_audio_chunks(str(channel_id))
                
                if not transcript_chunks:
                    await interaction.edit_original_response(content="❌ 保存する音声データがありません。録音開始後しばらく待ってから再試行してください。")
                    return
                
                # Combine chunks into full transcript
                full_transcript = "\n".join(transcript_chunks)
                
                # Find text channel for this voice channel
                text_channel = None
                for text_ch in channel.guild.text_channels:
                    if text_ch.name == f"{channel.name.lower().replace(' ', '-')}" or \
                       text_ch.name == f"{channel.name.lower()}-text" or \
                       text_ch.category == channel.category:
                        text_channel = text_ch
                        break
                
                if not text_channel:
                    text_channel = channel.guild.text_channels[0]
                
                # Create embed for raw transcript
                embed = discord.Embed(
                    title="💾 過去30分間の音声記録",
                    description=f"**チャンネル**: {channel.name}",
                    color=0x0099FF
                )
                embed.set_footer(text=f"記録数: {len(transcript_chunks)} チャンク")
                
                # Split long transcript into chunks (Discord 2000 char limit)
                max_length = 1900  # Leave room for formatting
                if len(full_transcript) <= max_length:
                    embed.add_field(
                        name="📝 音声記録",
                        value=f"```{full_transcript}```",
                        inline=False
                    )
                    await text_channel.send(embed=embed)
                else:
                    await text_channel.send(embed=embed)
                    
                    # Send transcript in chunks
                    chunks = [full_transcript[i:i+max_length] for i in range(0, len(full_transcript), max_length)]
                    for i, chunk in enumerate(chunks, 1):
                        chunk_embed = discord.Embed(
                            title=f"📄 音声記録 (Part {i}/{len(chunks)})",
                            description=f"```{chunk}```",
                            color=0x0099FF
                        )
                        await text_channel.send(embed=chunk_embed)
                
                await interaction.edit_original_response(content="✅ 過去30分の音声記録をテキストチャンネルに保存しました。")
                
            finally:
                await buffer_manager.close()
                
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ エラーが発生しました: {str(e)}")
    
    async def handle_start_recording(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle start recording button"""
        try:
            await interaction.response.send_message("🔴 録音を開始しました", ephemeral=True)
            
            channel = self.bot.get_channel(channel_id)
            if channel:
                await self.bot.start_recording(channel, is_manual=True)
                
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)