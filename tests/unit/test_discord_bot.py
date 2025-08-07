import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Optional
import discord

class TestDiscordBot:
    
    def test_bot_initialization_with_correct_intents(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        
        assert bot.intents.message_content is True
        assert bot.intents.voice_states is True
        assert bot.intents.guilds is True
        assert bot.command_prefix == '/'
    
    @pytest.mark.asyncio
    async def test_bot_starts_with_valid_token(self):
        from application.bot.discord_client import DiscordMinutesBot
        from infrastructure.config.settings import EnvironmentConfig
        
        config = EnvironmentConfig()
        config.set_config('DISCORD_BOT_TOKEN', 'valid_token')
        
        bot = DiscordMinutesBot(config)
        
        with patch.object(bot, 'start', new_callable=AsyncMock) as mock_start:
            await bot.start_bot()
            mock_start.assert_called_once_with('valid_token')
    
    @pytest.mark.asyncio
    async def test_bot_raises_error_with_invalid_token(self):
        from application.bot.discord_client import DiscordMinutesBot
        from infrastructure.config.settings import EnvironmentConfig
        from framework.error_code.errors import DetailedError, ErrorCode
        
        config = EnvironmentConfig()
        config.set_config('DISCORD_BOT_TOKEN', '')
        
        bot = DiscordMinutesBot(config)
        
        with pytest.raises(DetailedError) as exc_info:
            await bot.start_bot()
        
        assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR
    
    def test_bot_has_priority_scheduler(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        
        assert hasattr(bot, 'scheduler')
        assert bot.scheduler is not None
    
    def test_bot_has_recorders_dict(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        
        assert hasattr(bot, 'recorders')
        assert isinstance(bot.recorders, dict)
        assert len(bot.recorders) == 0
    
    @pytest.mark.asyncio
    async def test_on_ready_calls_scan_voice_channels(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        
        with patch.object(bot, 'scan_voice_channels', new_callable=AsyncMock) as mock_scan:
            with patch('discord.Client.guilds', new_callable=lambda: [Mock()]):
                await bot.on_ready()
                mock_scan.assert_called()
    
    @pytest.mark.asyncio
    async def test_on_voice_state_update_ignores_bots(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        member = Mock()
        member.bot = True
        before = Mock()
        after = Mock()
        
        with patch.object(bot, 'handle_vc_join', new_callable=AsyncMock) as mock_join:
            await bot.on_voice_state_update(member, before, after)
            mock_join.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_voice_state_update_handles_member_join(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        member = Mock()
        member.bot = False
        before = Mock()
        before.channel = None
        after = Mock()
        after.channel = Mock()
        
        with patch.object(bot, 'handle_vc_join', new_callable=AsyncMock) as mock_join:
            await bot.on_voice_state_update(member, before, after)
            mock_join.assert_called_once_with(member, after.channel)
    
    @pytest.mark.asyncio
    async def test_on_voice_state_update_handles_member_leave(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        member = Mock()
        member.bot = False
        before = Mock()
        before.channel = Mock()
        after = Mock()
        after.channel = None
        
        with patch.object(bot, 'handle_vc_leave', new_callable=AsyncMock) as mock_leave:
            await bot.on_voice_state_update(member, before, after)
            mock_leave.assert_called_once_with(member, before.channel)