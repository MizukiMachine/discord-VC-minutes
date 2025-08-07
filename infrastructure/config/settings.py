import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from framework.interfaces import ConfigProvider

load_dotenv()

class EnvironmentConfig(ConfigProvider):
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        self._cache = {
            'DISCORD_BOT_TOKEN': os.getenv('DISCORD_BOT_TOKEN', ''),
            'VIBE_URL': os.getenv('VIBE_URL', 'http://localhost:3022'),
            'REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379'),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
            'MAX_CONCURRENT_RECORDINGS': int(os.getenv('MAX_CONCURRENT_RECORDINGS', '4')),
            'RECORDING_CHUNK_SECONDS': int(os.getenv('RECORDING_CHUNK_SECONDS', '15')),
            'REDIS_TTL_SECONDS': int(os.getenv('REDIS_TTL_SECONDS', '1800')),
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
            'ENVIRONMENT': os.getenv('ENVIRONMENT', 'development')
        }
    
    def get_config(self, key: str) -> Optional[Any]:
        return self._cache.get(key)
    
    def set_config(self, key: str, value: Any) -> None:
        self._cache[key] = value
    
    def get_all_config(self) -> Dict[str, Any]:
        return self._cache.copy()
    
    def validate(self) -> None:
        required = ['DISCORD_BOT_TOKEN', 'OPENAI_API_KEY']
        for key in required:
            if not self.get_config(key):
                raise ValueError(f"{key} is required")
    
    def is_development(self) -> bool:
        return self.get_config('ENVIRONMENT') == 'development'
    
    def is_production(self) -> bool:
        return self.get_config('ENVIRONMENT') == 'production'