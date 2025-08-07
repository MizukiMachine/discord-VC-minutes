import pytest
from unittest.mock import MagicMock
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