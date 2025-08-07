from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import timedelta

class TransactionalOperation(ABC):
    """Marker interface for transactional operations"""
    
    @abstractmethod
    def requires_transaction(self) -> bool:
        pass

class CacheableOperation(ABC):
    """Marker interface for cacheable operations"""
    
    @abstractmethod
    def get_cache_key(self, *params) -> str:
        pass
    
    @abstractmethod
    def get_cache_ttl(self) -> timedelta:
        pass
    
    @abstractmethod
    def is_cache_skip(self) -> bool:
        pass

class AuditableOperation(ABC):
    """Marker interface for auditable operations"""
    
    @abstractmethod
    def get_audit_info(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def should_audit(self) -> bool:
        pass