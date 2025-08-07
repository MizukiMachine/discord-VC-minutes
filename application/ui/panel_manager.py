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
        return None
    
    async def update_panel(self, channel: discord.VoiceChannel, state: PanelState) -> None:
        """Update existing control panel"""
        pass
    
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
        """Handle save transcript button"""
        try:
            await interaction.response.send_message("💾 過去30分の音声を保存中...", ephemeral=True)
            
            # TODO: Implement save30 functionality
            # This would involve retrieving the full transcript from Redis
            # and posting it to the text channel without LLM summarization
            
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
    
    async def handle_start_recording(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle start recording button"""
        try:
            await interaction.response.send_message("🔴 録音を開始しました", ephemeral=True)
            
            channel = self.bot.get_channel(channel_id)
            if channel:
                await self.bot.start_recording(channel, is_manual=True)
                
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)