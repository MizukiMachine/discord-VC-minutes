import redis.asyncio as redis
from typing import List, Optional, Union
from framework.interfaces.core import CoreService
from abc import ABC, abstractmethod


class BufferManager(ABC):
    """Abstract interface for audio buffer management"""
    
    @abstractmethod
    async def add_audio_chunk(self, vc_id: str, audio_data: str) -> bool:
        """Add audio chunk to buffer"""
        pass
    
    @abstractmethod
    async def get_all_audio_chunks(self, vc_id: str) -> List[str]:
        """Get all audio chunks from buffer"""
        pass
    
    @abstractmethod
    async def get_recent_audio_chunks(self, vc_id: str, limit: int) -> List[str]:
        """Get recent audio chunks from buffer"""
        pass
    
    @abstractmethod
    async def clear_buffer(self, vc_id: str) -> bool:
        """Clear entire buffer"""
        pass
    
    @abstractmethod
    async def get_buffer_size(self, vc_id: str) -> int:
        """Get current buffer size"""
        pass
    
    @abstractmethod
    async def get_ttl_remaining(self, vc_id: str) -> int:
        """Get remaining TTL for buffer"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close connections and cleanup resources"""
        pass


class RedisBufferManager(BufferManager):
    """Redis-based ring buffer manager for voice channel audio data
    
    Implements a ring buffer with TTL for storing audio chunks from Discord voice channels.
    Each voice channel gets its own buffer with a maximum size and 30-minute TTL.
    
    Redis Key Pattern: vc:<channel_id>:raw
    TTL: 1800 seconds (30 minutes)
    Max Buffer Size: 120 chunks (30 minutes * 4 chunks/minute)
    """
    
    DEFAULT_TTL_SECONDS: int = 1800  # 30 minutes
    DEFAULT_MAX_BUFFER_SIZE: int = 120  # 30min * 4 chunks/min = 120 chunks (15s per chunk)
    
    def __init__(
        self, 
        core_service: CoreService, 
        redis_url: str,
        ttl_seconds: Optional[int] = None,
        max_buffer_size: Optional[int] = None
    ) -> None:
        """Initialize Redis buffer manager
        
        Args:
            core_service: Core service for logging and configuration
            redis_url: Redis connection URL
            ttl_seconds: TTL for buffers in seconds (default: 1800)
            max_buffer_size: Maximum buffer size in chunks (default: 120)
        """
        self.core_service = core_service
        self.redis_client: redis.Redis = redis.from_url(redis_url, decode_responses=False)
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self.max_buffer_size = max_buffer_size or self.DEFAULT_MAX_BUFFER_SIZE
    
    def _get_key(self, vc_id: str) -> str:
        """Generate Redis key for VC buffer
        
        Args:
            vc_id: Voice channel ID
            
        Returns:
            Redis key in format: vc:<channel_id>:raw
        """
        return f"vc:{vc_id}:raw"
    
    async def add_audio_chunk(self, vc_id: str, audio_data: str) -> bool:
        """Add audio chunk to ring buffer with TTL and size management
        
        Args:
            vc_id: Voice channel ID
            audio_data: Audio data as string
            
        Returns:
            True if successful, False if error occurred
            
        Raises:
            No exceptions raised - errors logged via core_service.error
        """
        try:
            key = self._get_key(vc_id)
            
            # Check if key exists (for TTL management)
            key_exists = await self.redis_client.exists(key)
            
            # Add to buffer (right push for FIFO order)
            await self.redis_client.rpush(key, audio_data)
            
            # Set TTL only for new keys to avoid resetting TTL on existing data
            if not key_exists:
                await self.redis_client.expire(key, self.ttl_seconds)
                self.core_service.debug("Set TTL for new buffer", vc_id=vc_id, ttl=self.ttl_seconds)
            
            # Enforce ring buffer size limit (remove oldest if exceeds max)
            buffer_size = await self.redis_client.llen(key)
            if buffer_size > self.max_buffer_size:
                old_chunk = await self.redis_client.lpop(key)
                self.core_service.debug("Removed old chunk from ring buffer", 
                                      vc_id=vc_id, buffer_size=buffer_size)
            
            return True
            
        except Exception as e:
            self.core_service.error("Failed to add audio chunk to buffer", e, 
                                  vc_id=vc_id, audio_data_len=len(audio_data))
            return False
    
    async def get_all_audio_chunks(self, vc_id: str) -> List[str]:
        """Get all audio chunks from buffer in chronological order
        
        Args:
            vc_id: Voice channel ID
            
        Returns:
            List of audio chunks as strings (oldest first)
        """
        try:
            key = self._get_key(vc_id)
            chunks = await self.redis_client.lrange(key, 0, -1)
            result = [chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk for chunk in chunks]
            self.core_service.debug("Retrieved all audio chunks", vc_id=vc_id, count=len(result))
            return result
        except Exception as e:
            self.core_service.error("Failed to get all audio chunks", e, vc_id=vc_id)
            return []
    
    async def get_recent_audio_chunks(self, vc_id: str, limit: int) -> List[str]:
        """Get recent audio chunks from buffer (last N items)
        
        Args:
            vc_id: Voice channel ID
            limit: Maximum number of recent chunks to retrieve
            
        Returns:
            List of recent audio chunks as strings (newest last)
        """
        try:
            key = self._get_key(vc_id)
            chunks = await self.redis_client.lrange(key, -limit, -1)
            result = [chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk for chunk in chunks]
            self.core_service.debug("Retrieved recent audio chunks", 
                                  vc_id=vc_id, requested_limit=limit, actual_count=len(result))
            return result
        except Exception as e:
            self.core_service.error("Failed to get recent audio chunks", e, 
                                  vc_id=vc_id, limit=limit)
            return []
    
    async def clear_buffer(self, vc_id: str) -> bool:
        """Clear entire buffer for a voice channel
        
        Args:
            vc_id: Voice channel ID
            
        Returns:
            True if buffer was cleared, False if error or buffer didn't exist
        """
        try:
            key = self._get_key(vc_id)
            result = await self.redis_client.delete(key)
            success = result > 0
            if success:
                self.core_service.info("Cleared audio buffer", vc_id=vc_id)
            else:
                self.core_service.debug("Buffer was already empty", vc_id=vc_id)
            return success
        except Exception as e:
            self.core_service.error("Failed to clear buffer", e, vc_id=vc_id)
            return False
    
    async def get_buffer_size(self, vc_id: str) -> int:
        """Get current buffer size in number of chunks
        
        Args:
            vc_id: Voice channel ID
            
        Returns:
            Number of chunks in buffer (0 if empty or error)
        """
        try:
            key = self._get_key(vc_id)
            size = await self.redis_client.llen(key)
            return size
        except Exception as e:
            self.core_service.error("Failed to get buffer size", e, vc_id=vc_id)
            return 0
    
    async def get_ttl_remaining(self, vc_id: str) -> int:
        """Get remaining TTL for buffer in seconds
        
        Args:
            vc_id: Voice channel ID
            
        Returns:
            Remaining TTL in seconds (-1 if no TTL, -2 if key doesn't exist)
        """
        try:
            key = self._get_key(vc_id)
            ttl = await self.redis_client.ttl(key)
            return ttl
        except Exception as e:
            self.core_service.error("Failed to get TTL remaining", e, vc_id=vc_id)
            return -1
    
    async def close(self) -> None:
        """Close Redis connection and cleanup resources
        
        Should be called when the buffer manager is no longer needed
        to properly release resources.
        """
        try:
            await self.redis_client.close()
            self.core_service.info("Redis buffer manager connection closed")
        except Exception as e:
            self.core_service.error("Failed to close Redis connection", e)