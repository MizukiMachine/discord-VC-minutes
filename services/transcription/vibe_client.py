import aiohttp
import json
from typing import Dict, Any, List, Optional
from io import BytesIO

from framework.error_code.errors import DetailedError, ErrorCode

class VibeClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self.session
    
    async def transcribe_audio(
        self, 
        wav_data: bytes, 
        language: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            session = await self._get_session()
            
            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field('audio', wav_data, filename='audio.wav', content_type='audio/wav')
            
            if language:
                data.add_field('language', language)
            if model:
                data.add_field('model', model)
            
            url = f"{self.base_url}/transcribe"
            
            async with session.post(url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise DetailedError(
                        ErrorCode.VIBE_CONNECTION_ERROR,
                        f"Vibe server returned status {response.status}",
                        f"HTTP {response.status}: {error_text}"
                    )
                
                try:
                    result = await response.json()
                    return result
                except json.JSONDecodeError as e:
                    raise DetailedError(
                        ErrorCode.TRANSCRIPTION_ERROR,
                        "Invalid JSON response from Vibe server",
                        str(e)
                    )
        
        except aiohttp.ClientConnectionError as e:
            raise DetailedError(
                ErrorCode.VIBE_CONNECTION_ERROR,
                "Failed to connect to Vibe server",
                str(e)
            )
        except aiohttp.ServerTimeoutError as e:
            raise DetailedError(
                ErrorCode.NETWORK_ERROR,
                "Timeout connecting to Vibe server",
                str(e)
            )
        except aiohttp.ClientConnectorError as e:
            raise DetailedError(
                ErrorCode.NETWORK_ERROR,
                "Network error connecting to Vibe server",
                str(e)
            )
        except DetailedError:
            raise
        except Exception as e:
            raise DetailedError(
                ErrorCode.TRANSCRIPTION_ERROR,
                "Unexpected error during transcription",
                str(e)
            )
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            session = await self._get_session()
            url = f"{self.base_url}/health"
            
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"status": "unhealthy", "http_status": response.status}
        
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def batch_transcribe(self, audio_chunks: List[bytes]) -> List[Optional[Dict[str, Any]]]:
        results = []
        
        for chunk in audio_chunks:
            try:
                result = await self.transcribe_audio(chunk)
                results.append(result)
            except DetailedError:
                results.append(None)  # Failed transcription
        
        return results
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None