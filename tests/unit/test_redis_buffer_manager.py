import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import List, Optional

from services.redis.buffer_manager import RedisBufferManager
from framework.interfaces.core import CoreService


class TestRedisBufferManager:
    """Redis Buffer Manager test suite"""

    @pytest.fixture
    def mock_core_service(self) -> Mock:
        mock = Mock(spec=CoreService)
        mock.get_config.return_value = None
        mock.info = Mock()
        mock.error = Mock()
        mock.debug = Mock()
        mock.warning = Mock()
        return mock

    @pytest.fixture
    def mock_redis_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def buffer_manager(self, mock_core_service, mock_redis_client) -> RedisBufferManager:
        with patch('services.redis.buffer_manager.redis.from_url', return_value=mock_redis_client):
            return RedisBufferManager(core_service=mock_core_service, redis_url="redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_add_audio_chunk_creates_list_and_sets_ttl(self, buffer_manager, mock_redis_client):
        """Test adding first audio chunk creates list and sets TTL"""
        vc_id = "123456789"
        audio_data = "test_audio_data"
        
        mock_redis_client.exists.return_value = False
        mock_redis_client.rpush.return_value = 1
        mock_redis_client.expire.return_value = True
        mock_redis_client.llen.return_value = 1  # Add this to avoid comparison error
        
        result = await buffer_manager.add_audio_chunk(vc_id, audio_data)
        
        assert result is True
        mock_redis_client.exists.assert_called_once_with(f"vc:{vc_id}:raw")
        mock_redis_client.rpush.assert_called_once_with(f"vc:{vc_id}:raw", audio_data)
        mock_redis_client.expire.assert_called_once_with(f"vc:{vc_id}:raw", 1800)

    @pytest.mark.asyncio
    async def test_add_audio_chunk_to_existing_list(self, buffer_manager, mock_redis_client):
        """Test adding audio chunk to existing list doesn't reset TTL"""
        vc_id = "123456789"
        audio_data = "test_audio_data"
        
        mock_redis_client.exists.return_value = True
        mock_redis_client.rpush.return_value = 2
        mock_redis_client.llen.return_value = 2  # Add this to avoid comparison error
        
        result = await buffer_manager.add_audio_chunk(vc_id, audio_data)
        
        assert result is True
        mock_redis_client.exists.assert_called_once_with(f"vc:{vc_id}:raw")
        mock_redis_client.rpush.assert_called_once_with(f"vc:{vc_id}:raw", audio_data)
        mock_redis_client.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_all_audio_chunks(self, buffer_manager, mock_redis_client):
        """Test retrieving all audio chunks from buffer"""
        vc_id = "123456789"
        expected_chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        mock_redis_client.lrange.return_value = expected_chunks
        
        result = await buffer_manager.get_all_audio_chunks(vc_id)
        
        assert result == [chunk.decode('utf-8') for chunk in expected_chunks]
        mock_redis_client.lrange.assert_called_once_with(f"vc:{vc_id}:raw", 0, -1)

    @pytest.mark.asyncio
    async def test_get_recent_audio_chunks(self, buffer_manager, mock_redis_client):
        """Test retrieving recent audio chunks from buffer"""
        vc_id = "123456789"
        limit = 10
        expected_chunks = [b"chunk1", b"chunk2"]
        
        mock_redis_client.lrange.return_value = expected_chunks
        
        result = await buffer_manager.get_recent_audio_chunks(vc_id, limit)
        
        assert result == [chunk.decode('utf-8') for chunk in expected_chunks]
        mock_redis_client.lrange.assert_called_once_with(f"vc:{vc_id}:raw", -limit, -1)

    @pytest.mark.asyncio
    async def test_clear_buffer(self, buffer_manager, mock_redis_client):
        """Test clearing entire buffer for a VC"""
        vc_id = "123456789"
        
        mock_redis_client.delete.return_value = 1
        
        result = await buffer_manager.clear_buffer(vc_id)
        
        assert result is True
        mock_redis_client.delete.assert_called_once_with(f"vc:{vc_id}:raw")

    @pytest.mark.asyncio
    async def test_get_buffer_size(self, buffer_manager, mock_redis_client):
        """Test getting buffer size"""
        vc_id = "123456789"
        expected_size = 25
        
        mock_redis_client.llen.return_value = expected_size
        
        result = await buffer_manager.get_buffer_size(vc_id)
        
        assert result == expected_size
        mock_redis_client.llen.assert_called_once_with(f"vc:{vc_id}:raw")

    @pytest.mark.asyncio
    async def test_get_ttl_remaining(self, buffer_manager, mock_redis_client):
        """Test getting remaining TTL for buffer"""
        vc_id = "123456789"
        expected_ttl = 1200
        
        mock_redis_client.ttl.return_value = expected_ttl
        
        result = await buffer_manager.get_ttl_remaining(vc_id)
        
        assert result == expected_ttl
        mock_redis_client.ttl.assert_called_once_with(f"vc:{vc_id}:raw")

    @pytest.mark.asyncio
    async def test_ring_buffer_max_size_enforcement(self, buffer_manager, mock_redis_client):
        """Test ring buffer removes old data when max size is reached"""
        vc_id = "123456789"
        audio_data = "new_chunk"
        max_size = 121  # One more than MAX_BUFFER_SIZE to trigger lpop
        
        mock_redis_client.exists.return_value = True
        mock_redis_client.llen.return_value = max_size
        mock_redis_client.rpush.return_value = max_size
        mock_redis_client.lpop.return_value = b"old_chunk"
        
        result = await buffer_manager.add_audio_chunk(vc_id, audio_data)
        
        assert result is True
        mock_redis_client.llen.assert_called_once_with(f"vc:{vc_id}:raw")
        mock_redis_client.rpush.assert_called_once_with(f"vc:{vc_id}:raw", audio_data)
        mock_redis_client.lpop.assert_called_once_with(f"vc:{vc_id}:raw")

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self, buffer_manager, mock_redis_client):
        """Test handling Redis connection errors"""
        vc_id = "123456789"
        audio_data = "test_data"
        
        mock_redis_client.exists.side_effect = Exception("Connection failed")
        
        result = await buffer_manager.add_audio_chunk(vc_id, audio_data)
        
        assert result is False
        buffer_manager.core_service.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_vc_buffers_independence(self, buffer_manager, mock_redis_client):
        """Test multiple VC buffers operate independently"""
        vc_id_1 = "111111111"
        vc_id_2 = "222222222"
        audio_data = "test_data"
        
        mock_redis_client.exists.return_value = False
        mock_redis_client.rpush.return_value = 1
        mock_redis_client.expire.return_value = True
        mock_redis_client.llen.return_value = 1  # Add this to avoid comparison error
        
        result_1 = await buffer_manager.add_audio_chunk(vc_id_1, audio_data)
        result_2 = await buffer_manager.add_audio_chunk(vc_id_2, audio_data)
        
        assert result_1 is True
        assert result_2 is True
        
        expected_calls = [
            ((f"vc:{vc_id_1}:raw", audio_data),),
            ((f"vc:{vc_id_2}:raw", audio_data),)
        ]
        assert mock_redis_client.rpush.call_args_list == expected_calls