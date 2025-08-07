import pytest
from unittest.mock import AsyncMock, Mock, patch
from aioresponses import aioresponses
import aiohttp
from typing import Dict, Any

class TestVibeClient:
    
    def test_vibe_client_initialization_with_url(self):
        from services.transcription.vibe_client import VibeClient
        
        vibe_url = "http://localhost:3022"
        client = VibeClient(vibe_url)
        
        assert client.base_url == vibe_url
        assert client.timeout == 30
        assert client.session is None
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_sends_wav_to_vibe_server(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        wav_data = b"fake_wav_data_for_testing"
        expected_response = {
            "text": "こんにちは、これはテストです。",
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "こんにちは、"},
                {"start": 2.5, "end": 5.0, "text": "これはテストです。"}
            ]
        }
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", payload=expected_response)
            
            result = await client.transcribe_audio(wav_data)
            
            assert result["text"] == expected_response["text"]
            assert len(result["segments"]) == 2
            assert result["segments"][0]["text"] == "こんにちは、"
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_handles_multipart_form_data(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        wav_data = b"fake_wav_data"
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", payload={"text": "テスト"})
            
            result = await client.transcribe_audio(wav_data)
            
            assert result["text"] == "テスト"
            assert len(m.requests) == 1
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_with_language_parameter(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        wav_data = b"fake_wav_data"
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", payload={"text": "Hello world"})
            
            result = await client.transcribe_audio(wav_data, language="en")
            
            assert result["text"] == "Hello world"
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_with_model_parameter(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        wav_data = b"fake_wav_data"
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", payload={"text": "テスト音声"})
            
            result = await client.transcribe_audio(wav_data, model="large-v3")
            
            assert result["text"] == "テスト音声"
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_handles_connection_error(self):
        from services.transcription.vibe_client import VibeClient
        from framework.error_code.errors import DetailedError, ErrorCode
        
        client = VibeClient("http://localhost:3022")
        wav_data = b"fake_wav_data"
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", exception=aiohttp.ClientConnectionError())
            
            with pytest.raises(DetailedError) as exc_info:
                await client.transcribe_audio(wav_data)
            
            assert exc_info.value.code == ErrorCode.VIBE_CONNECTION_ERROR
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_handles_timeout_error(self):
        from services.transcription.vibe_client import VibeClient
        from framework.error_code.errors import DetailedError, ErrorCode
        
        client = VibeClient("http://localhost:3022", timeout=1)
        wav_data = b"fake_wav_data"
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", exception=aiohttp.ServerTimeoutError("Timeout"))
            
            with pytest.raises(DetailedError) as exc_info:
                await client.transcribe_audio(wav_data)
            
            # ServerTimeoutError gets caught as ClientConnectionError in aioresponses
            assert exc_info.value.code == ErrorCode.VIBE_CONNECTION_ERROR
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_handles_http_error_status(self):
        from services.transcription.vibe_client import VibeClient
        from framework.error_code.errors import DetailedError, ErrorCode
        
        client = VibeClient("http://localhost:3022")
        wav_data = b"fake_wav_data"
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", status=500, body="Server Error")
            
            with pytest.raises(DetailedError) as exc_info:
                await client.transcribe_audio(wav_data)
            
            assert exc_info.value.code == ErrorCode.VIBE_CONNECTION_ERROR
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_handles_invalid_json_response(self):
        from services.transcription.vibe_client import VibeClient
        from framework.error_code.errors import DetailedError, ErrorCode
        
        client = VibeClient("http://localhost:3022")
        wav_data = b"fake_wav_data"
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", body="invalid json response", content_type="text/plain")
            
            with pytest.raises(DetailedError) as exc_info:
                await client.transcribe_audio(wav_data)
            
            assert exc_info.value.code == ErrorCode.TRANSCRIPTION_ERROR
    
    @pytest.mark.asyncio
    async def test_health_check_returns_server_status(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        expected_status = {
            "status": "healthy",
            "model": "large-v3",
            "version": "1.0.0"
        }
        
        with aioresponses() as m:
            m.get("http://localhost:3022/health", payload=expected_status)
            
            result = await client.health_check()
            
            assert result["status"] == "healthy"
            assert result["model"] == "large-v3"
    
    @pytest.mark.asyncio
    async def test_session_management_creates_and_closes_session(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            async with client:
                assert client.session == mock_session
                mock_session_class.assert_called_once()
            
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_transcribe_processes_multiple_audio_chunks(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        audio_chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        expected_results = [
            {"text": "第一部分の音声"},
            {"text": "第二部分の音声"},
            {"text": "第三部分の音声"}
        ]
        
        with aioresponses() as m:
            for i, expected in enumerate(expected_results):
                m.post("http://localhost:3022/transcribe", payload=expected)
            
            results = await client.batch_transcribe(audio_chunks)
            
            assert len(results) == 3
            assert results[0]["text"] == "第一部分の音声"
            assert results[1]["text"] == "第二部分の音声"
            assert results[2]["text"] == "第三部分の音声"
    
    @pytest.mark.asyncio
    async def test_batch_transcribe_handles_partial_failures(self):
        from services.transcription.vibe_client import VibeClient
        
        client = VibeClient("http://localhost:3022")
        audio_chunks = [b"chunk1", b"chunk2"]
        
        with aioresponses() as m:
            m.post("http://localhost:3022/transcribe", payload={"text": "成功"})
            m.post("http://localhost:3022/transcribe", status=500)
            
            results = await client.batch_transcribe(audio_chunks)
            
            assert len(results) == 2
            assert results[0]["text"] == "成功"
            assert results[1] is None  # Failed transcription returns None