import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import List
import discord

class TestVoiceChannelHandler:
    
    @pytest.mark.asyncio
    async def test_scan_voice_channels_starts_recording_for_active_channels(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        guild = Mock()
        
        active_vc = Mock(spec=discord.VoiceChannel)
        active_vc.name = "会議室1"
        active_vc.id = 12345
        member1 = Mock()
        member1.bot = False
        member2 = Mock()
        member2.bot = False
        active_vc.members = [member1, member2]
        
        empty_vc = Mock(spec=discord.VoiceChannel)
        empty_vc.members = []
        
        guild.voice_channels = [active_vc, empty_vc]
        
        with patch.object(bot, 'start_auto_recording', new_callable=AsyncMock) as mock_start:
            await bot.scan_voice_channels(guild)
            mock_start.assert_called_once_with(active_vc)
    
    @pytest.mark.asyncio
    async def test_scan_voice_channels_ignores_bot_only_channels(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        guild = Mock()
        
        bot_only_vc = Mock(spec=discord.VoiceChannel)
        bot_only_vc.name = "Bot会議室"
        bot_only_vc.id = 12346
        bot_member = Mock()
        bot_member.bot = True
        bot_only_vc.members = [bot_member]
        
        guild.voice_channels = [bot_only_vc]
        
        with patch.object(bot, 'start_auto_recording', new_callable=AsyncMock) as mock_start:
            await bot.scan_voice_channels(guild)
            mock_start.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_vc_join_starts_recording_for_first_member(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        member = Mock()
        member.name = "TestUser"
        member.bot = False
        
        channel = Mock(spec=discord.VoiceChannel)
        channel.name = "会議室2"
        channel.id = 12347
        human_member = Mock()
        human_member.bot = False
        channel.members = [human_member]  # Only one human member after join
        
        with patch.object(bot, 'start_auto_recording', new_callable=AsyncMock) as mock_start:
            await bot.handle_vc_join(member, channel)
            mock_start.assert_called_once_with(channel)
    
    @pytest.mark.asyncio
    async def test_handle_vc_join_does_not_start_recording_for_second_member(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        member = Mock()
        member.name = "TestUser2"
        member.bot = False
        
        channel = Mock(spec=discord.VoiceChannel)
        channel.name = "会議室3"
        channel.id = 12348
        member1 = Mock()
        member1.bot = False
        member2 = Mock()
        member2.bot = False
        channel.members = [member1, member2]  # Two human members
        
        with patch.object(bot, 'start_auto_recording', new_callable=AsyncMock) as mock_start:
            await bot.handle_vc_join(member, channel)
            mock_start.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_vc_leave_stops_recording_when_last_member_leaves(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        member = Mock()
        member.name = "LastUser"
        member.bot = False
        
        channel = Mock(spec=discord.VoiceChannel)
        channel.name = "会議室4"
        channel.id = 12349
        channel.members = []  # No members after leave
        
        bot.recorders[12349] = Mock()  # Recording exists
        
        with patch.object(bot, 'stop_recording', new_callable=AsyncMock) as mock_stop:
            await bot.handle_vc_leave(member, channel)
            mock_stop.assert_called_once_with(channel)
    
    @pytest.mark.asyncio
    async def test_handle_vc_leave_continues_recording_when_members_remain(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        member = Mock()
        member.name = "LeavingUser"
        member.bot = False
        
        channel = Mock(spec=discord.VoiceChannel)
        channel.name = "会議室5"
        channel.id = 12350
        remaining_member = Mock()
        remaining_member.bot = False
        channel.members = [remaining_member]  # One member remains
        
        with patch.object(bot, 'stop_recording', new_callable=AsyncMock) as mock_stop:
            await bot.handle_vc_leave(member, channel)
            mock_stop.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_start_auto_recording_succeeds_when_scheduler_allows(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        channel = Mock(spec=discord.VoiceChannel)
        channel.id = 12351
        channel.members = [Mock(), Mock()]  # 2 members
        
        with patch.object(bot.scheduler, 'can_add_auto_recording', return_value=True):
            with patch.object(bot, 'start_recording', new_callable=AsyncMock, return_value=True) as mock_start:
                await bot.start_auto_recording(channel)
                mock_start.assert_called_once_with(channel, is_manual=False)
    
    @pytest.mark.asyncio
    async def test_start_auto_recording_skips_when_scheduler_rejects(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        channel = Mock(spec=discord.VoiceChannel)
        channel.id = 12352
        channel.name = "満杯時の会議室"
        channel.members = [Mock(), Mock()]  # 2 members
        
        with patch.object(bot.scheduler, 'can_add_auto_recording', return_value=False):
            with patch.object(bot, 'start_recording', new_callable=AsyncMock) as mock_start:
                await bot.start_auto_recording(channel)
                mock_start.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_start_auto_recording_skips_already_recording_channel(self):
        from application.bot.discord_client import DiscordMinutesBot
        
        bot = DiscordMinutesBot()
        channel = Mock(spec=discord.VoiceChannel)
        channel.id = 12353
        channel.name = "既録音中会議室"
        
        bot.recorders[12353] = Mock()  # Already recording
        
        with patch.object(bot, 'start_recording', new_callable=AsyncMock) as mock_start:
            await bot.start_auto_recording(channel)
            mock_start.assert_not_called()