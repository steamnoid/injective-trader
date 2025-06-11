"""
Circular Buffer Implementation - Layer 3 Market Data Processing

Memory-efficient circular buffer for historical market data storage.
Provides fixed-size ring buffer with overflow handling and thread safety.
"""

from typing import Optional, List, Any, Generic, TypeVar, Iterator, Dict
from datetime import datetime
from threading import RLock
import threading

T = TypeVar('T')


class BufferFullError(Exception):
    """Raised when attempting to add to a full buffer with overflow=False"""
    pass


class BufferEmptyError(Exception):
    """Raised when attempting to read from an empty buffer"""
    pass


class CircularBuffer(Generic[T]):
    """
    Thread-safe circular buffer implementation for market data storage.
    
    Features:
    - Fixed size with configurable overflow handling
    - Thread-safe operations with minimal locking
    - Time-based indexing for historical data access
    - Memory efficient with object reuse
    - O(1) read/write operations
    """
    
    def __init__(self, capacity: int, data_type: str = "generic", allow_overflow: bool = True):
        """
        Initialize circular buffer.
        
        Args:
            capacity: Maximum number of items to store
            data_type: Type identifier for the data stored
            allow_overflow: If True, old items are overwritten when full
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
            
        self._capacity = capacity
        self._data_type = data_type
        self._allow_overflow = allow_overflow
        self._buffer: List[Optional[T]] = [None] * capacity
        self._head = 0  # Next write position
        self._tail = 0  # Next read position  
        self._size = 0  # Current number of items
        self._lock = RLock()
        
    @property
    def capacity(self) -> int:
        """Get buffer capacity"""
        return self._capacity
        
    @property
    def data_type(self) -> str:
        """Get buffer data type"""
        return self._data_type
        
    @property
    def size(self) -> int:
        """Get current buffer size"""
        with self._lock:
            return self._size
            
    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        return self.size == 0
        
    def is_full(self) -> bool:
        """Check if buffer is full"""
        return self.size == self._capacity
        
    def append(self, item: T) -> None:
        """
        Add item to buffer.
        
        Args:
            item: Item to add
            
        Raises:
            BufferFullError: If buffer is full and overflow not allowed
        """
        with self._lock:
            if self.is_full() and not self._allow_overflow:
                raise BufferFullError("Buffer is full and overflow not allowed")
                
            self._buffer[self._head] = item
            self._head = (self._head + 1) % self._capacity
            
            if self.is_full():
                # Buffer is full, move tail (overwrite oldest)
                self._tail = (self._tail + 1) % self._capacity
            else:
                # Buffer not full, increase size
                self._size += 1
                
    def get(self, index: int) -> T:
        """
        Get item at index (0 = oldest, -1 = newest).
        
        Args:
            index: Index to retrieve
            
        Returns:
            Item at index
            
        Raises:
            BufferEmptyError: If buffer is empty
            IndexError: If index out of range
        """
        with self._lock:
            if self.is_empty():
                raise BufferEmptyError("Buffer is empty")
                
            if index < 0:
                index = self._size + index
                
            if index < 0 or index >= self._size:
                raise IndexError(f"Index {index} out of range [0, {self._size})")
                
            actual_index = (self._tail + index) % self._capacity
            return self._buffer[actual_index]
            
    def get_latest(self, count: Optional[int] = None) -> T | List[T]:
        """
        Get latest N items (newest first) or single latest item.
        
        Args:
            count: Number of items to retrieve. If None, returns single latest item.
            
        Returns:
            Single latest item if count is None, otherwise list of latest items
        """
        with self._lock:
            if self.is_empty():
                raise BufferEmptyError("Buffer is empty")
                
            if count is None:
                # Return single latest item
                return self.get(self._size - 1)
            
            if count <= 0:
                return []
                
            count = min(count, self._size)
            result = []
            
            for i in range(count):
                index = self._size - 1 - i  # Start from newest
                result.append(self.get(index))
                
            return result
            
    def get_oldest(self) -> T:
        """
        Get oldest item in buffer.
        
        Returns:
            Oldest item
            
        Raises:
            BufferEmptyError: If buffer is empty
        """
        if self.is_empty():
            raise BufferEmptyError("Buffer is empty")
        return self.get(0)  # First item is oldest
        
    def get_range(self, count: int) -> List[T]:
        """
        Get most recent N items (oldest first in returned list).
        
        Args:
            count: Number of items to retrieve
            
        Returns:
            List of most recent items in chronological order (oldest to newest)
        """
        with self._lock:
            if count <= 0:
                return []
                
            count = min(count, self._size)
            result = []
            
            # Get the last 'count' items and return in chronological order
            for i in range(count):
                index = self._size - count + i  # Start from count items back
                result.append(self.get(index))
                
            return result
        
    def get_by_timestamp_range(self, start_time: datetime, end_time: datetime) -> List[T]:
        """
        Get items within timestamp range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of items within time range
            
        Note:
            Assumes items have a 'timestamp' attribute
        """
        with self._lock:
            result = []
            for i in range(self._size):
                item = self.get(i)
                # Try to get timestamp from item
                if hasattr(item, 'timestamp'):
                    item_time = item.timestamp
                elif isinstance(item, dict) and 'timestamp' in item:
                    item_time = item['timestamp']
                else:
                    continue  # Skip items without timestamp
                    
                if start_time <= item_time <= end_time:
                    result.append(item)
            return result
            
    def clear(self) -> None:
        """Clear all items from buffer"""
        with self._lock:
            self._buffer = [None] * self._capacity
            self._head = 0
            self._tail = 0
            self._size = 0
            
    def to_list(self) -> List[T]:
        """Convert buffer to list (oldest to newest)"""
        with self._lock:
            return [self.get(i) for i in range(self._size)]
            
    def __len__(self) -> int:
        """Get buffer size"""
        return self.size
        
    def __iter__(self) -> Iterator[T]:
        """Iterate over buffer items (oldest to newest)"""
        with self._lock:
            for i in range(self._size):
                yield self.get(i)
                
    def __getitem__(self, index: int) -> T:
        """Get item by index"""
        return self.get(index)
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics and metrics"""
        with self._lock:
            utilization = self._size / self._capacity if self._capacity > 0 else 0
            return {
                "size": self._size,
                "capacity": self._capacity,
                "utilization": utilization,
                "data_type": self._data_type,
                "is_empty": self.is_empty(),
                "is_full": self.is_full()
            }
            
    def serialize(self) -> Dict[str, Any]:
        """Serialize buffer state for persistence"""
        with self._lock:
            return {
                "capacity": self._capacity,
                "data_type": self._data_type,
                "allow_overflow": self._allow_overflow,
                "data": self.to_list(),
                "metadata": {
                    "size": self._size,
                    "head": self._head,
                    "tail": self._tail
                }
            }
            
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'CircularBuffer':
        """Deserialize buffer from saved state"""
        buffer = cls(
            capacity=data["capacity"],
            data_type=data["data_type"],
            allow_overflow=data.get("allow_overflow", True)
        )
        
        # Restore data
        for item in data["data"]:
            buffer.append(item)
            
        return buffer
