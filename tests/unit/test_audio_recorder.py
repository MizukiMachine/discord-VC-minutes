import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import asyncio
import discord
from io import BytesIO
import numpy as np

class TestAudioRecorder:
    
    def test_recorder_initialization_with_channel_and_voice_client(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        channel.id = 12345
        channel.name = "テスト会議室"
        
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        assert recorder.channel == channel
        assert recorder.voice_client == voice_client
        assert recorder.is_recording is False
        assert recorder.task is None
        assert recorder.audio_buffer == []
        assert recorder.chunk_duration == 15
    
    @pytest.mark.asyncio
    async def test_start_recording_begins_audio_capture(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        with patch.object(recorder, '_recording_loop', new_callable=AsyncMock) as mock_loop:
            with patch('asyncio.create_task') as mock_create_task:
                mock_task = Mock()
                mock_create_task.return_value = mock_task
                
                await recorder.start()
                
                assert recorder.is_recording is True
                assert recorder.task == mock_task
                mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_recording_ends_audio_capture(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        recorder.is_recording = True
        
        mock_task = AsyncMock()
        recorder.task = mock_task
        
        await recorder.stop()
        
        assert recorder.is_recording is False
        mock_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recording_loop_processes_15_second_chunks(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        mock_audio_data = b'fake_audio_data' * 1000
        
        with patch.object(recorder, '_capture_audio_chunk', return_value=mock_audio_data):
            with patch.object(recorder, '_process_audio_chunk', new_callable=AsyncMock) as mock_process:
                with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                    # Set to True initially, then False after first iteration
                    call_count = 0
                    def side_effect():
                        nonlocal call_count
                        call_count += 1
                        if call_count >= 2:  # After first process and sleep
                            recorder.is_recording = False
                    
                    mock_sleep.side_effect = lambda x: side_effect()
                    recorder.is_recording = True
                    
                    await recorder._recording_loop()
                    
                    mock_process.assert_called_with(mock_audio_data)
                    mock_sleep.assert_called_with(15)
    
    def test_capture_audio_chunk_collects_opus_data(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        # Mock members with voice states
        member1 = Mock()
        member1.voice = Mock()
        member1.voice.channel = channel
        member2 = Mock()
        member2.voice = Mock() 
        member2.voice.channel = channel
        
        channel.members = [member1, member2]
        
        # Mock audio data from members
        mock_opus_data1 = b'opus_data_member1'
        mock_opus_data2 = b'opus_data_member2'
        
        with patch.object(voice_client, 'receive_audio_frame') as mock_receive:
            mock_receive.side_effect = [mock_opus_data1, mock_opus_data2, None]  # None ends the loop
            
            result = recorder._capture_audio_chunk()
            
            assert isinstance(result, bytes)
            assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_process_audio_chunk_converts_opus_to_pcm_and_stores(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        opus_data = b'fake_opus_data'
        expected_pcm = np.array([1, 2, 3, 4], dtype=np.int16)
        expected_wav = b'fake_wav_data'
        
        with patch.object(recorder, '_opus_to_pcm', return_value=expected_pcm) as mock_convert:
            with patch.object(recorder, '_pcm_to_wav', return_value=expected_wav) as mock_wav:
                await recorder._process_audio_chunk(opus_data)
                
                mock_convert.assert_called_once_with(opus_data)
                mock_wav.assert_called_once_with(expected_pcm)
                assert expected_wav in recorder.audio_buffer
    
    def test_opus_to_pcm_conversion_uses_pydub(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        opus_data = b'fake_opus_data'
        expected_pcm = np.array([1, 2, 3, 4], dtype=np.int16)
        
        with patch('pydub.AudioSegment.from_file') as mock_from_file:
            mock_audio = Mock()
            mock_audio.raw_data = expected_pcm.tobytes()
            mock_audio.frame_rate = 48000
            mock_audio.channels = 2
            mock_from_file.return_value = mock_audio
            
            result = recorder._opus_to_pcm(opus_data)
            
            mock_from_file.assert_called_once()
            assert isinstance(result, np.ndarray)
    
    def test_pcm_to_wav_conversion_creates_wav_format(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        pcm_data = np.array([1, 2, 3, 4], dtype=np.int16)
        
        result = recorder._pcm_to_wav(pcm_data)
        
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result.startswith(b'RIFF')  # WAV file header
    
    def test_get_recent_audio_returns_last_n_chunks(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        # Add test audio chunks
        test_chunks = [b'chunk1', b'chunk2', b'chunk3', b'chunk4', b'chunk5']
        recorder.audio_buffer = test_chunks
        
        # Get last 3 chunks
        result = recorder.get_recent_audio(duration_minutes=3)
        
        expected_chunks = int(3 * 60 / 15)  # 3 minutes / 15 seconds per chunk = 12 chunks
        expected_result = test_chunks[-expected_chunks:] if expected_chunks < len(test_chunks) else test_chunks
        
        assert result == expected_result
    
    def test_clear_old_audio_removes_chunks_beyond_ttl(self):
        from services.audio.recorder import AudioRecorder
        
        channel = Mock(spec=discord.VoiceChannel)
        voice_client = Mock()
        
        recorder = AudioRecorder(channel, voice_client)
        
        # Add audio chunks beyond 30 minute limit
        max_chunks = int(30 * 60 / 15)  # 30 minutes / 15 seconds = 120 chunks
        test_chunks = [f'chunk{i}'.encode() for i in range(max_chunks + 10)]  # 10 extra chunks
        recorder.audio_buffer = test_chunks
        
        recorder._clear_old_audio()
        
        assert len(recorder.audio_buffer) == max_chunks
        assert recorder.audio_buffer[0] == b'chunk10'  # First 10 chunks should be removed