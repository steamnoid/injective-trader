# Layer 2: WebSocket Connection Layer
"""
WebSocket connection management for Injective Protocol
"""

from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from datetime import datetime, timezone
import asyncio
import logging
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


class ConnectionState(str, Enum):
    """WebSocket connection state enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class MessageType(str, Enum):
    """WebSocket message type enumeration"""
    MARKET_DATA = "market_data"
    ORDERBOOK = "orderbook"
    TRADES = "trades"
    ACCOUNT = "account"
    DERIVATIVE_MARKETS = "derivative_markets"
    MARKET_METADATA = "market_metadata"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ConnectionMetrics(BaseModel):
    """Connection performance metrics"""
    
    connection_attempts: int = Field(default=0, ge=0)
    successful_connections: int = Field(default=0, ge=0)
    failed_connections: int = Field(default=0, ge=0)
    total_messages_received: int = Field(default=0, ge=0)
    total_messages_sent: int = Field(default=0, ge=0)
    
    # Latency metrics
    avg_latency_ms: float = Field(default=0.0, ge=0)
    max_latency_ms: float = Field(default=0.0, ge=0)
    min_latency_ms: float = Field(default=0.0, ge=0)
    
    # Connection quality
    uptime_seconds: float = Field(default=0.0, ge=0)
    downtime_seconds: float = Field(default=0.0, ge=0)
    reconnection_count: int = Field(default=0, ge=0)
    
    # Performance tracking
    last_message_time: Optional[datetime] = Field(default=None)
    last_heartbeat_time: Optional[datetime] = Field(default=None)
    connection_start_time: Optional[datetime] = Field(default=None)
    
    @property
    def uptime_percentage(self) -> float:
        """Calculate connection uptime percentage"""
        total_time = self.uptime_seconds + self.downtime_seconds
        if total_time > 0:
            return (self.uptime_seconds / total_time) * 100
        return 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate connection success rate"""
        if self.connection_attempts > 0:
            return (self.successful_connections / self.connection_attempts) * 100
        return 0.0
    
    @property
    def messages_per_second(self) -> float:
        """Calculate average messages per second"""
        if self.uptime_seconds > 0:
            return self.total_messages_received / self.uptime_seconds
        return 0.0
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class WebSocketMessage(BaseModel):
    """WebSocket message wrapper"""
    
    message_id: str = Field(..., min_length=1)
    message_type: MessageType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Message content
    data: Dict[str, Any] = Field(default_factory=dict)
    raw_data: Optional[bytes] = Field(default=None)
    
    # Metadata
    market_id: Optional[str] = Field(default=None)
    sequence_number: Optional[int] = Field(default=None, ge=0)
    
    # Performance tracking
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_latency_ms: Optional[float] = Field(default=None, ge=0)
    
    @property
    def age_ms(self) -> float:
        """Calculate message age in milliseconds"""
        now = datetime.now(timezone.utc)
        return (now - self.timestamp).total_seconds() * 1000
    
    def is_stale(self, max_age_ms: float = 1000) -> bool:
        """Check if message is stale"""
        return self.age_ms > max_age_ms
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ConnectionError(Exception):
    """Base connection error"""
    pass


class ReconnectionError(ConnectionError):
    """Reconnection failed error"""
    pass


class MessageParsingError(ConnectionError):
    """Message parsing error"""
    pass


class RateLimitError(ConnectionError):
    """Rate limit exceeded error"""
    pass


# Abstract base classes for dependency injection

class MessageHandler(ABC):
    """Abstract message handler interface"""
    
    @abstractmethod
    async def handle_message(self, message: WebSocketMessage) -> None:
        """Handle incoming WebSocket message"""
        pass
    
    @abstractmethod
    def get_supported_message_types(self) -> List[MessageType]:
        """Get list of supported message types"""
        pass


class ConnectionManager(ABC):
    """Abstract connection manager interface"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close WebSocket connection"""
        pass
    
    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send message through WebSocket"""
        pass
    
    @abstractmethod
    def get_connection_state(self) -> ConnectionState:
        """Get current connection state"""
        pass
    
    @abstractmethod
    def get_metrics(self) -> ConnectionMetrics:
        """Get connection metrics"""
        pass
    
    @abstractmethod
    def register_handler(self, handler: MessageHandler) -> None:
        """Register message handler"""
        pass


__all__ = [
    "ConnectionState",
    "MessageType", 
    "ConnectionMetrics",
    "WebSocketMessage",
    "ConnectionError",
    "ReconnectionError", 
    "MessageParsingError",
    "RateLimitError",
    "MessageHandler",
    "ConnectionManager"
]

# Import network utilities for easier access
try:
    from .network_utils import NetworkConnectivityManager, NetworkAwareInjectiveClient
    __all__.extend(["NetworkConnectivityManager", "NetworkAwareInjectiveClient"])
except ImportError:
    # Network utilities are optional
    pass
