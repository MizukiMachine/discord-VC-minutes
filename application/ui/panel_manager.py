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
            ("🔴停止", discord.ButtonStyle.danger, not state.is_recording),
            ("📜今まで", discord.ButtonStyle.primary, not state.is_recording), 
            ("💾過去30分", discord.ButtonStyle.secondary, not state.is_recording),
            ("🔴録音開始", discord.ButtonStyle.success, state.is_recording)
        ]
        
        for label, style, disabled in buttons:
            button = discord.ui.Button(label=label, style=style, disabled=disabled)
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
        pass
    
    async def handle_summary(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle summary request button"""
        pass
    
    async def handle_save_transcript(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle save transcript button"""
        pass
    
    async def handle_start_recording(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle start recording button"""
        pass