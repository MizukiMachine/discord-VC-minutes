from enum import IntEnum
from typing import Optional, Dict, Any

class ErrorCode(IntEnum):
    """Hierarchical error code system"""
    
    # System errors (99000-99999)
    UNKNOWN_ERROR = 99999
    FRAMEWORK_ERROR = 99998
    CONFIGURATION_ERROR = 99997
    
    # Infrastructure errors (90000-98999)
    DATABASE_ERROR = 95000
    REDIS_ERROR = 94900
    NETWORK_ERROR = 94000
    FILE_SYSTEM_ERROR = 93000
    VIBE_CONNECTION_ERROR = 93500
    
    # Business logic errors (10000-89999)
    VALIDATION_ERROR = 40000
    AUTHENTICATION_ERROR = 41000
    AUTHORIZATION_ERROR = 42000
    BUSINESS_RULE_ERROR = 50000
    
    # Discord specific errors (30000-39999)
    DISCORD_CONNECTION_ERROR = 30000
    VOICE_CHANNEL_ERROR = 30100
    RECORDING_ERROR = 30200
    TRANSCRIPTION_ERROR = 30300
    SUMMARY_ERROR = 30400

class DetailedError(Exception):
    """Structured error with detailed information"""
    
    def __init__(
        self,
        code: ErrorCode,
        user_message: str,
        developer_message: Optional[str] = None,
        internal_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.code = code
        self.user_message = user_message
        self.developer_message = developer_message or user_message
        self.internal_message = internal_message or developer_message or user_message
        self.context = context or {}
        self.cause = cause
        super().__init__(self.user_message)
    
    def is_retryable(self) -> bool:
        """Check if error is retryable"""
        return self.code in [
            ErrorCode.NETWORK_ERROR,
            ErrorCode.VIBE_CONNECTION_ERROR,
            ErrorCode.REDIS_ERROR
        ]
    
    def is_fatal(self) -> bool:
        """Check if error is fatal"""
        return self.code in [
            ErrorCode.FRAMEWORK_ERROR,
            ErrorCode.CONFIGURATION_ERROR
        ]