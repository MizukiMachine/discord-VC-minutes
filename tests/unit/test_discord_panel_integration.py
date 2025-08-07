import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
import time

from application.bot.discord_client import DiscordMinutesBot
from application.ui.panel_manager import PanelManager
from framework.interfaces.ui import PanelState
from infrastructure.config.settings import EnvironmentConfig


class TestDiscordPanelIntegration:
    """Discord Bot and PanelManager integration tests"""
    
    @pytest.fixture
    def config(self):
        config = EnvironmentConfig()
        config.set_config('DISCORD_BOT_TOKEN', 'test_token')
        config.set_config('MAX_CONCURRENT_RECORDINGS', 4)
        return config
    
    @pytest.fixture
    def mock_voice_channel(self):
        channel = MagicMock(spec=discord.VoiceChannel)
        channel.id = 12345
        channel.name = "Test Channel"
        channel.members = []
        return channel
    
    @pytest.fixture
    def discord_bot(self, config):
        return DiscordMinutesBot(config)
    
    def test_discord_bot_has_panel_manager_dependency(self, discord_bot):
        """Test that DiscordBot can accept PanelManager dependency"""
        # This test will initially fail - RED state
        assert hasattr(discord_bot, 'panel_manager')
        assert discord_bot.panel_manager is not None
    
    @pytest.mark.asyncio
    async def test_bot_creates_panel_on_recording_start(self, discord_bot, mock_voice_channel):
        """Test that bot creates control panel when recording starts"""
        # Mock panel manager
        panel_manager = MagicMock()
        panel_manager.post_panel = AsyncMock()
        discord_bot.panel_manager = panel_manager
        
        # Mock the dependencies for actual recording
        mock_voice_channel.connect = AsyncMock()
        mock_voice_client = MagicMock()
        mock_voice_channel.connect.return_value = mock_voice_client
        
        with patch('application.bot.discord_client.AudioRecorder') as MockRecorder:
            mock_recorder = MagicMock()
            mock_recorder.start = AsyncMock()
            MockRecorder.return_value = mock_recorder
            
            # Call the actual method, not mock it
            result = await discord_bot.start_recording(mock_voice_channel, is_manual=False)
        
        # Should create panel
        assert result == True
        panel_manager.post_panel.assert_called_once()
        call_args = panel_manager.post_panel.call_args
        assert call_args[0][0] == mock_voice_channel  # channel argument
        panel_state = call_args[0][1]  # state argument
        assert isinstance(panel_state, PanelState)
        assert panel_state.is_recording == True
    
    @pytest.mark.asyncio
    async def test_bot_updates_panel_on_recording_stop(self, discord_bot, mock_voice_channel):
        """Test that bot updates control panel when recording stops"""
        # Mock panel manager
        panel_manager = MagicMock()
        panel_manager.update_panel = AsyncMock()
        discord_bot.panel_manager = panel_manager
        
        # Mock existing recorder
        mock_recorder = MagicMock()
        mock_recorder.stop = AsyncMock()
        mock_recorder.voice_client = MagicMock()
        mock_recorder.voice_client.is_connected.return_value = True
        mock_recorder.voice_client.disconnect = AsyncMock()
        
        discord_bot.recorders[mock_voice_channel.id] = mock_recorder
        discord_bot.recording_start_times[mock_voice_channel.id] = time.time()
        
        # Mock get_channel to return our mock channel
        discord_bot.get_channel = MagicMock(return_value=mock_voice_channel)
        
        await discord_bot.stop_recording(mock_voice_channel)
        
        # Should update panel
        panel_manager.update_panel.assert_called_once()
        call_args = panel_manager.update_panel.call_args
        assert call_args[0][0] == mock_voice_channel  # channel argument
        panel_state = call_args[0][1]  # state argument
        assert isinstance(panel_state, PanelState)
        assert panel_state.is_recording == False
    
    @pytest.mark.asyncio
    async def test_button_interaction_handler_integration(self, discord_bot):
        """Test that button interactions are properly handled"""
        # Mock interaction
        interaction = MagicMock()
        interaction.custom_id = "stop_12345"
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = MagicMock()
        interaction.user.voice.channel.id = 12345
        
        # Mock panel manager
        panel_manager = MagicMock()
        panel_manager.handle_stop = AsyncMock()
        discord_bot.panel_manager = panel_manager
        
        # Should have interaction handler
        assert hasattr(discord_bot, 'on_interaction')
        await discord_bot.on_interaction(interaction)
        
        # Should call appropriate handler
        panel_manager.handle_stop.assert_called_once_with(interaction, 12345)
    
    def test_panel_state_creation_from_bot_state(self, discord_bot, mock_voice_channel):
        """Test creating PanelState from bot's internal state"""
        # Mock bot state
        discord_bot.recorders[mock_voice_channel.id] = MagicMock()
        mock_voice_channel.members = [MagicMock(bot=False), MagicMock(bot=False)]
        
        # Should have method to create panel state
        assert hasattr(discord_bot, 'create_panel_state')
        
        panel_state = discord_bot.create_panel_state(mock_voice_channel)
        
        assert isinstance(panel_state, PanelState)
        assert panel_state.channel_id == mock_voice_channel.id
        assert panel_state.is_recording == True  # has recorder
        assert panel_state.member_count == 2  # non-bot members
        assert panel_state.elapsed_time >= 0