import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from framework.interfaces.ui import PanelState, UIService
from application.ui.panel_manager import PanelManager
from infrastructure.config.settings import EnvironmentConfig


class TestPanelManagerMinimal:
    """Minimal PanelManager TDD tests - starting with simplest functionality"""
    
    @pytest.fixture
    def config(self):
        return EnvironmentConfig()
    
    @pytest.fixture
    def mock_bot(self):
        return MagicMock()
    
    @pytest.fixture
    def panel_state(self):
        return PanelState(
            channel_id=12345,
            is_recording=True,
            elapsed_time=120,
            member_count=3
        )
    
    @pytest.fixture
    def panel_manager(self, config, mock_bot):
        return PanelManager(config, mock_bot)
    
    def test_implements_ui_service_interface(self, panel_manager):
        """Test that PanelManager implements UIService interface"""
        assert isinstance(panel_manager, UIService)
    
    @pytest.mark.asyncio
    async def test_create_embed_basic_structure(self, panel_manager, panel_state):
        """Test creating basic embed structure"""
        embed = await panel_manager.create_embed(panel_state, "Test Channel")
        
        assert isinstance(embed, discord.Embed)
        assert "Test Channel" in embed.description
        assert embed.color is not None
    
    @pytest.mark.asyncio
    async def test_create_embed_recording_state(self, panel_manager):
        """Test embed shows recording state correctly"""
        recording_state = PanelState(
            channel_id=12345,
            is_recording=True,
            elapsed_time=120,
            member_count=3
        )
        
        embed = await panel_manager.create_embed(recording_state, "Test Channel")
        
        assert "🔴" in embed.title or "録音中" in embed.title
        assert embed.color.value == 0xFF0000
    
    @pytest.mark.asyncio
    async def test_create_embed_waiting_state(self, panel_manager):
        """Test embed shows waiting state correctly"""
        waiting_state = PanelState(
            channel_id=12345,
            is_recording=False,
            elapsed_time=0,
            member_count=1
        )
        
        embed = await panel_manager.create_embed(waiting_state, "Test Channel")
        
        assert "⚪" in embed.title or "待機中" in embed.title
        assert embed.color.value == 0x808080
    
    @pytest.mark.asyncio
    async def test_create_view_basic_structure(self, panel_manager, panel_state):
        """Test creating basic view structure"""
        view = panel_manager.create_view(panel_state)
        
        assert isinstance(view, discord.ui.View)
        assert view.timeout is None
    
    @pytest.mark.asyncio
    async def test_create_view_has_required_buttons(self, panel_manager, panel_state):
        """Test view has all required control buttons"""
        view = panel_manager.create_view(panel_state)
        
        # Should have 4 buttons: stop, summary, save, start
        assert len(view.children) == 4
        
        button_labels = [child.label for child in view.children if hasattr(child, 'label')]
        expected_labels = ["🔴停止", "📜今まで", "💾過去30分", "🔴録音開始"]
        
        for label in expected_labels:
            assert label in button_labels
    
    @pytest.mark.asyncio
    async def test_post_panel_finds_text_channel(self, panel_manager, panel_state):
        """Test posting panel finds appropriate text channel"""
        mock_channel = MagicMock(spec=discord.VoiceChannel)
        mock_channel.id = 12345
        mock_channel.name = "General Voice"
        mock_channel.category = MagicMock()
        
        mock_guild = MagicMock()
        mock_channel.guild = mock_guild
        
        # Mock text channel that matches voice channel
        mock_text_channel = MagicMock()
        mock_text_channel.name = "general-voice"
        mock_text_channel.send = AsyncMock()
        mock_text_channel.send.return_value = MagicMock()  # mock message
        
        mock_guild.text_channels = [mock_text_channel]
        
        result = await panel_manager.post_panel(mock_channel, panel_state)
        
        # Should find text channel and send message
        assert result is not None
        mock_text_channel.send.assert_called_once()
        call_kwargs = mock_text_channel.send.call_args.kwargs
        assert 'embed' in call_kwargs
        assert 'view' in call_kwargs
    
    @pytest.mark.asyncio
    async def test_post_panel_uses_first_text_channel_as_fallback(self, panel_manager, panel_state):
        """Test posting panel uses first text channel as fallback"""
        mock_channel = MagicMock(spec=discord.VoiceChannel)
        mock_channel.id = 12345
        mock_channel.name = "Voice Channel"
        mock_channel.category = MagicMock()
        
        mock_guild = MagicMock()
        mock_channel.guild = mock_guild
        
        # Mock text channel that doesn't match
        mock_text_channel = MagicMock()
        mock_text_channel.name = "random-chat"
        mock_text_channel.send = AsyncMock()
        mock_text_channel.send.return_value = MagicMock()
        
        mock_guild.text_channels = [mock_text_channel]
        
        result = await panel_manager.post_panel(mock_channel, panel_state)
        
        # Should use first text channel as fallback
        assert result is not None
        mock_text_channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_panel_edits_existing_message(self, panel_manager, panel_state):
        """Test updating panel edits existing message"""
        mock_channel = MagicMock(spec=discord.VoiceChannel)
        mock_channel.id = 12345
        mock_channel.name = "Test Channel"
        
        # Mock existing panel message
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        panel_manager.panels[12345] = mock_message
        
        await panel_manager.update_panel(mock_channel, panel_state)
        
        # Should edit existing message
        mock_message.edit.assert_called_once()
        call_kwargs = mock_message.edit.call_args.kwargs
        assert 'embed' in call_kwargs
        assert 'view' in call_kwargs
    
    @pytest.mark.asyncio
    async def test_update_panel_handles_missing_panel(self, panel_manager, panel_state):
        """Test updating panel when no existing panel exists"""
        mock_channel = MagicMock(spec=discord.VoiceChannel)
        mock_channel.id = 99999  # Non-existing channel
        mock_channel.name = "Test Channel"
        
        # Should not raise exception
        await panel_manager.update_panel(mock_channel, panel_state)