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

    @pytest.mark.asyncio
    async def test_sofar_command_requires_voice_channel_membership(self):
        """Test /sofar command requires user to be in voice channel"""
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        mock_ctx = Mock()
        mock_ctx.author.voice = None  # User not in voice channel
        mock_ctx.send = AsyncMock()
        
        await bot.sofar_command.callback(bot, mock_ctx)
        
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[0][0]
        assert "ボイスチャンネル" in call_args

    @pytest.mark.asyncio  
    async def test_sofar_command_requires_active_recording(self):
        """Test /sofar command requires active recording in the voice channel"""
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        mock_ctx = Mock()
        mock_channel = Mock()
        mock_channel.id = 123456789
        mock_ctx.author.voice = Mock()
        mock_ctx.author.voice.channel = mock_channel
        mock_ctx.send = AsyncMock()
        
        # No active recording for this channel
        bot.recorders = {}
        
        await bot.sofar_command.callback(bot, mock_ctx)
        
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[0][0]
        assert "録音" in call_args

    @pytest.mark.asyncio
    async def test_sofar_command_success_flow(self):
        """Test successful /sofar command execution flow"""
        from application.bot.discord_client import DiscordMinutesBot
        
        with patch('application.bot.discord_client.RedisBufferManager') as MockBuffer, \
             patch('application.bot.discord_client.OpenAIClient') as MockOpenAI:
            
            bot = DiscordMinutesBot()
            
            # Setup mocks
            mock_ctx = Mock()
            mock_channel = Mock()
            mock_channel.id = 123456789
            mock_channel.send = AsyncMock()
            mock_ctx.author.voice = Mock()
            mock_ctx.author.voice.channel = mock_channel
            mock_ctx.send = AsyncMock()
            
            # Mock active recording
            mock_recorder = Mock()
            bot.recorders = {123456789: mock_recorder}
            
            # Mock configuration
            bot.config.get_config = Mock(side_effect=lambda key: {
                'OPENAI_API_KEY': 'test-api-key',
                'REDIS_URL': 'redis://localhost:6379'
            }.get(key))
            
            # Mock buffer manager
            mock_buffer_instance = MockBuffer.return_value
            mock_buffer_instance.get_all_audio_chunks = AsyncMock(return_value=["chunk1", "chunk2"])
            mock_buffer_instance.close = AsyncMock()
            
            # Mock OpenAI client
            mock_openai_instance = MockOpenAI.return_value
            mock_response = Mock()
            mock_response.success = True
            mock_response.summary = "これは要約された議事録です。"
            mock_response.total_tokens = 150
            mock_response.stages = 1
            mock_openai_instance.summarize.return_value = mock_response
            
            # Mock ctx.send for processing message
            mock_processing_msg = Mock()
            mock_processing_msg.delete = AsyncMock()
            mock_ctx.send.return_value = mock_processing_msg
            
            await bot.sofar_command.callback(bot, mock_ctx)
            
            # Verify buffer access
            mock_buffer_instance.get_all_audio_chunks.assert_called_once_with("123456789")
            
            # Verify OpenAI call  
            mock_openai_instance.summarize.assert_called_once_with("chunk1\nchunk2")
            
            # Verify processing message was sent and deleted
            mock_ctx.send.assert_called_once_with("🤖 議事録を要約中...")
            mock_processing_msg.delete.assert_called_once()
            
            # Verify response sent to channel
            mock_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_sofar_command_handles_empty_buffer(self):
        """Test /sofar command handles empty audio buffer"""
        from application.bot.discord_client import DiscordMinutesBot
        
        with patch('application.bot.discord_client.RedisBufferManager') as MockBuffer:
            bot = DiscordMinutesBot()
            mock_ctx = Mock()
            mock_channel = Mock()
            mock_channel.id = 123456789
            mock_ctx.author.voice = Mock()
            mock_ctx.author.voice.channel = mock_channel
            mock_ctx.send = AsyncMock()
            
            # Mock active recording
            mock_recorder = Mock()
            bot.recorders = {123456789: mock_recorder}
            
            # Mock configuration
            bot.config.get_config = Mock(side_effect=lambda key: {
                'OPENAI_API_KEY': 'test-api-key',
                'REDIS_URL': 'redis://localhost:6379'
            }.get(key))
            
            # Mock empty buffer
            mock_buffer_instance = MockBuffer.return_value
            mock_buffer_instance.get_all_audio_chunks = AsyncMock(return_value=[])
            mock_buffer_instance.close = AsyncMock()
            
            # Mock ctx.send for processing message
            mock_processing_msg = Mock()
            mock_processing_msg.edit = AsyncMock()
            mock_ctx.send.return_value = mock_processing_msg
            
            await bot.sofar_command.callback(bot, mock_ctx)
            
            # Should first send processing message, then edit with error
            mock_ctx.send.assert_called_once_with("🤖 議事録を要約中...")
            mock_processing_msg.edit.assert_called_once()
            edit_args = mock_processing_msg.edit.call_args[1]['content']
            assert "音声データ" in edit_args or "データがありません" in edit_args

    @pytest.mark.asyncio
    async def test_sofar_command_handles_openai_error(self):
        """Test /sofar command handles OpenAI API errors gracefully"""
        from application.bot.discord_client import DiscordMinutesBot
        
        with patch('application.bot.discord_client.RedisBufferManager') as MockBuffer, \
             patch('application.bot.discord_client.OpenAIClient') as MockOpenAI:
            
            bot = DiscordMinutesBot()
            mock_ctx = Mock()
            mock_channel = Mock()
            mock_channel.id = 123456789
            mock_ctx.author.voice = Mock()
            mock_ctx.author.voice.channel = mock_channel
            mock_ctx.send = AsyncMock()
            
            # Mock active recording
            mock_recorder = Mock()
            bot.recorders = {123456789: mock_recorder}
            
            # Mock configuration
            bot.config.get_config = Mock(side_effect=lambda key: {
                'OPENAI_API_KEY': 'test-api-key',
                'REDIS_URL': 'redis://localhost:6379'
            }.get(key))
            
            # Mock buffer with data
            mock_buffer_instance = MockBuffer.return_value
            mock_buffer_instance.get_all_audio_chunks = AsyncMock(return_value=["audio_data"])
            mock_buffer_instance.close = AsyncMock()
            
            # Mock OpenAI error
            mock_openai_instance = MockOpenAI.return_value
            mock_response = Mock()
            mock_response.success = False
            mock_response.error_message = "API rate limit exceeded"
            mock_openai_instance.summarize.return_value = mock_response
            
            # Mock ctx.send for processing message
            mock_processing_msg = Mock()
            mock_processing_msg.edit = AsyncMock()
            mock_ctx.send.return_value = mock_processing_msg
            
            await bot.sofar_command.callback(bot, mock_ctx)
            
            # Should first send processing message, then edit with error
            mock_ctx.send.assert_called_once_with("🤖 議事録を要約中...")
            mock_processing_msg.edit.assert_called_once()
            edit_args = mock_processing_msg.edit.call_args[1]['content']
            assert "エラー" in edit_args or "失敗" in edit_args

    @pytest.mark.asyncio
    async def test_sofar_command_configuration_required(self):
        """Test /sofar command requires proper configuration"""
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        mock_ctx = Mock()
        mock_channel = Mock()
        mock_channel.id = 123456789
        mock_ctx.author.voice = Mock()
        mock_ctx.author.voice.channel = mock_channel
        mock_ctx.send = AsyncMock()
        
        # Mock active recording
        mock_recorder = Mock()
        bot.recorders = {123456789: mock_recorder}
        
        # Mock missing configuration
        bot.config.get_config = Mock(return_value=None)
        
        await bot.sofar_command.callback(bot, mock_ctx)
        
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[0][0]
        assert "設定" in call_args or "API" in call_args