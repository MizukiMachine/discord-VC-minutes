from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from dataclasses import dataclass
import discord
from .core import CoreService


@dataclass
class PanelState:
    """Control panel state information"""
    channel_id: int
    is_recording: bool
    elapsed_time: int
    member_count: int


class PanelProvider(ABC):
    """Abstract interface for Discord UI panel management"""
    
    @abstractmethod
    async def create_embed(self, state: PanelState, channel_name: str) -> discord.Embed:
        """Create control panel embed"""
        pass
    
    @abstractmethod
    def create_view(self, state: PanelState) -> discord.ui.View:
        """Create control panel view with buttons"""
        pass
    
    @abstractmethod
    async def post_panel(self, channel: discord.VoiceChannel, state: PanelState) -> Optional[discord.Message]:
        """Post control panel to voice channel's text chat"""
        pass
    
    @abstractmethod
    async def update_panel(self, channel: discord.VoiceChannel, state: PanelState) -> None:
        """Update existing control panel"""
        pass


class ButtonInteractionHandler(ABC):
    """Abstract interface for button interaction handling"""
    
    @abstractmethod
    async def handle_stop(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle stop recording button"""
        pass
    
    @abstractmethod
    async def handle_summary(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle summary request button"""
        pass
    
    @abstractmethod
    async def handle_save_transcript(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle save transcript button"""
        pass
    
    @abstractmethod
    async def handle_start_recording(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle start recording button"""
        pass


class UIService(PanelProvider, ButtonInteractionHandler):
    """Combined UI service interface"""
    pass