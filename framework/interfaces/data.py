from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from datetime import datetime

T = TypeVar('T', bound='Entity')

class Entity(ABC):
    """Base entity interface"""
    
    @abstractmethod
    def get_id(self) -> str:
        pass
    
    @abstractmethod
    def get_created_at(self) -> datetime:
        pass
    
    @abstractmethod
    def get_updated_at(self) -> datetime:
        pass

class Repository(ABC, Generic[T]):
    """Generic repository interface"""
    
    @abstractmethod
    async def create(self, entity: T) -> T:
        pass
    
    @abstractmethod
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> T:
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        pass
    
    @abstractmethod
    async def find(self, criteria: Dict[str, Any]) -> List[T]:
        pass
    
    @abstractmethod
    async def count(self, criteria: Dict[str, Any]) -> int:
        pass