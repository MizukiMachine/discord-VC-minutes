from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
import structlog

class ConfigProvider(ABC):
    """Configuration provider interface"""
    
    @abstractmethod
    def get_config(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    def set_config(self, key: str, value: Any) -> None:
        pass
    
    @abstractmethod
    def get_all_config(self) -> Dict[str, Any]:
        pass

class LogProvider(ABC):
    """Logging provider interface"""
    
    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        pass
    
    @abstractmethod
    def error(self, message: str, error: Optional[Exception] = None, **kwargs) -> None:
        pass
    
    @abstractmethod
    def debug(self, message: str, **kwargs) -> None:
        pass
    
    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        pass

class ErrorProvider(ABC):
    """Error handling provider interface"""
    
    @abstractmethod
    def error_response(self, code: int, message: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def wrap_error(self, code: int, error: Exception) -> Dict[str, Any]:
        pass

class CoreService(ConfigProvider, LogProvider, ErrorProvider):
    """Combined core service interface"""
    pass