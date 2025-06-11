"""
Unit tests for CircularBuffer - Layer 3 Market Data Processing

Test Coverage:
- Memory-efficient circular buffer implementation
- FIFO (First In, First Out) behavior
- Thread-safe operations
- Memory usage optimization
- Performance requirements
- Overflow handling
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import threading
import time
from unittest.mock import Mock

from injective_bot.data.circular_buffer import CircularBuffer, BufferFullError, BufferEmptyError


class TestCircularBuffer:
    """Test suite for CircularBuffer class."""

    @pytest.fixture
    def buffer(self):
        """Create CircularBuffer instance for testing."""
        return CircularBuffer(capacity=10, data_type="market_data")

    @pytest.fixture
    def sample_data(self):
        """Generate sample data for buffer testing."""
        return [
            {"timestamp": datetime.now() + timedelta(seconds=i), "value": i}
            for i in range(5)
        ]

    def test_buffer_initialization(self, buffer):
        """Test CircularBuffer initialization."""
        assert buffer is not None
        assert buffer.capacity == 10
        assert buffer.size == 0
        assert buffer.is_empty() is True
        assert buffer.is_full() is False
        assert buffer.data_type == "market_data"

    def test_append_single_item(self, buffer):
        """Test appending a single item to buffer."""
        item = {"timestamp": datetime.now(), "value": 1}
        buffer.append(item)
        
        assert buffer.size == 1
        assert buffer.is_empty() is False
        assert buffer.is_full() is False

    def test_append_multiple_items(self, buffer, sample_data):
        """Test appending multiple items to buffer."""
        for item in sample_data:
            buffer.append(item)
        
        assert buffer.size == len(sample_data)
        assert len(buffer) == len(sample_data)

    def test_fifo_behavior(self, buffer):
        """Test First In, First Out behavior."""
        # Fill buffer to capacity
        for i in range(buffer.capacity):
            buffer.append({"id": i, "value": f"item_{i}"})
        
        assert buffer.is_full() is True
        
        # Add one more item (should evict oldest)
        buffer.append({"id": buffer.capacity, "value": f"item_{buffer.capacity}"})
        
        # Buffer should still be full, but oldest item should be gone
        assert buffer.is_full() is True
        oldest_item = buffer.get_oldest()
        assert oldest_item["id"] == 1  # First item (id=0) should be evicted

    def test_get_latest(self, buffer, sample_data):
        """Test retrieving latest item from buffer."""
        for item in sample_data:
            buffer.append(item)
        
        latest = buffer.get_latest()
        assert latest["value"] == sample_data[-1]["value"]

    def test_get_oldest(self, buffer, sample_data):
        """Test retrieving oldest item from buffer."""
        for item in sample_data:
            buffer.append(item)
        
        oldest = buffer.get_oldest()
        assert oldest["value"] == sample_data[0]["value"]

    def test_get_range(self, buffer, sample_data):
        """Test retrieving range of items from buffer."""
        for item in sample_data:
            buffer.append(item)
        
        # Get last 3 items
        recent_items = buffer.get_range(count=3)
        assert len(recent_items) == 3
        assert recent_items[0]["value"] == sample_data[-3]["value"]
        assert recent_items[-1]["value"] == sample_data[-1]["value"]

    def test_get_range_exceeds_size(self, buffer, sample_data):
        """Test getting range larger than buffer size."""
        for item in sample_data:
            buffer.append(item)
        
        # Request more items than available
        all_items = buffer.get_range(count=20)
        assert len(all_items) == len(sample_data)  # Should return all available

    def test_get_by_timestamp_range(self, buffer):
        """Test retrieving items by timestamp range."""
        base_time = datetime.now()
        
        # Add items with specific timestamps
        for i in range(10):
            item = {
                "timestamp": base_time + timedelta(minutes=i),
                "value": i
            }
            buffer.append(item)
        
        # Get items from last 5 minutes
        start_time = base_time + timedelta(minutes=5)
        end_time = base_time + timedelta(minutes=10)
        
        range_items = buffer.get_by_timestamp_range(start_time, end_time)
        assert len(range_items) == 5  # Minutes 5-9

    def test_clear_buffer(self, buffer, sample_data):
        """Test clearing all items from buffer."""
        for item in sample_data:
            buffer.append(item)
        
        assert buffer.size > 0
        
        buffer.clear()
        assert buffer.size == 0
        assert buffer.is_empty() is True

    def test_thread_safety(self, buffer):
        """Test thread-safe operations."""
        errors = []
        
        def append_items(start_id, count):
            try:
                for i in range(count):
                    item = {"id": start_id + i, "timestamp": datetime.now()}
                    buffer.append(item)
            except Exception as e:
                errors.append(e)
        
        def read_items():
            try:
                for _ in range(50):
                    if not buffer.is_empty():
                        buffer.get_latest()
                        buffer.get_oldest()
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads for concurrent operations
        threads = []
        
        # Writer threads
        for i in range(3):
            thread = threading.Thread(target=append_items, args=(i * 100, 50))
            threads.append(thread)
        
        # Reader thread
        reader_thread = threading.Thread(target=read_items)
        threads.append(reader_thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_memory_efficiency(self):
        """Test memory efficiency with large capacity."""
        import sys
        
        # Create large buffer
        large_buffer = CircularBuffer(capacity=10000, data_type="performance_test")
        
        # Measure memory before
        initial_size = sys.getsizeof(large_buffer)
        
        # Fill buffer
        for i in range(large_buffer.capacity):
            large_buffer.append({"id": i, "data": f"item_{i}"})
        
        # Measure memory after
        filled_size = sys.getsizeof(large_buffer)
        
        # Memory growth should be reasonable
        memory_growth = filled_size - initial_size
        assert memory_growth < large_buffer.capacity * 200  # Reasonable upper bound

    def test_performance_requirement(self, buffer):
        """Test performance requirement for buffer operations."""
        import time
        
        # Test append performance
        start_time = time.perf_counter()
        for i in range(1000):
            buffer.append({"id": i, "timestamp": datetime.now()})
        append_time = time.perf_counter() - start_time
        
        # Should handle 1000 appends quickly
        assert append_time < 0.1, f"Append operations took {append_time:.3f}s"
        
        # Test read performance
        start_time = time.perf_counter()
        for _ in range(1000):
            buffer.get_latest()
            buffer.get_oldest()
        read_time = time.perf_counter() - start_time
        
        # Should handle 2000 reads quickly
        assert read_time < 0.05, f"Read operations took {read_time:.3f}s"

    def test_buffer_overflow_handling(self, buffer):
        """Test buffer behavior when exceeding capacity."""
        # Fill buffer beyond capacity
        for i in range(buffer.capacity + 5):
            buffer.append({"id": i, "value": f"item_{i}"})
        
        # Buffer should maintain capacity
        assert buffer.size == buffer.capacity
        assert buffer.is_full() is True
        
        # Oldest items should be evicted
        oldest = buffer.get_oldest()
        assert oldest["id"] == 5  # First 5 items should be evicted

    def test_empty_buffer_operations(self, buffer):
        """Test operations on empty buffer."""
        assert buffer.is_empty() is True
        
        # Getting from empty buffer should raise exception
        with pytest.raises(BufferEmptyError):
            buffer.get_latest()
        
        with pytest.raises(BufferEmptyError):
            buffer.get_oldest()
        
        # Getting range from empty buffer should return empty list
        empty_range = buffer.get_range(count=5)
        assert len(empty_range) == 0

    def test_iterator_support(self, buffer, sample_data):
        """Test iterator support for buffer."""
        for item in sample_data:
            buffer.append(item)
        
        # Test iteration
        iteration_count = 0
        for item in buffer:
            assert "value" in item
            iteration_count += 1
        
        assert iteration_count == len(sample_data)

    def test_buffer_statistics(self, buffer, sample_data):
        """Test buffer statistics and metrics."""
        for item in sample_data:
            buffer.append(item)
        
        stats = buffer.get_statistics()
        
        assert "size" in stats
        assert "capacity" in stats
        assert "utilization" in stats
        assert "data_type" in stats
        
        assert stats["size"] == len(sample_data)
        assert stats["capacity"] == buffer.capacity
        assert stats["utilization"] == len(sample_data) / buffer.capacity

    def test_buffer_with_different_data_types(self):
        """Test buffer with different data types."""
        # String buffer
        string_buffer = CircularBuffer(capacity=5, data_type="strings")
        string_buffer.append("test_string")
        assert string_buffer.get_latest() == "test_string"
        
        # Number buffer
        number_buffer = CircularBuffer(capacity=5, data_type="numbers")
        number_buffer.append(42)
        assert number_buffer.get_latest() == 42
        
        # Complex object buffer
        object_buffer = CircularBuffer(capacity=5, data_type="objects")
        test_object = {"nested": {"data": [1, 2, 3]}}
        object_buffer.append(test_object)
        assert object_buffer.get_latest() == test_object

    def test_buffer_serialization(self, buffer, sample_data):
        """Test buffer serialization for persistence."""
        for item in sample_data:
            buffer.append(item)
        
        # Serialize buffer state
        serialized = buffer.serialize()
        assert isinstance(serialized, dict)
        assert "capacity" in serialized
        assert "data" in serialized
        assert "metadata" in serialized
        
        # Create new buffer from serialized data
        new_buffer = CircularBuffer.deserialize(serialized)
        assert new_buffer.capacity == buffer.capacity
        assert new_buffer.size == buffer.size
        assert new_buffer.get_latest() == buffer.get_latest()

    def test_buffer_memory_pressure(self, buffer):
        """Test buffer behavior under memory pressure."""
        # Simulate memory pressure with large objects
        large_objects = []
        for i in range(buffer.capacity):
            large_obj = {
                "id": i,
                "data": "x" * 1000,  # 1KB string
                "timestamp": datetime.now()
            }
            large_objects.append(large_obj)
            buffer.append(large_obj)
        
        # Buffer should handle large objects efficiently
        assert buffer.is_full() is True
        assert buffer.size == buffer.capacity
        
        # Operations should still be fast
        start_time = time.perf_counter()
        latest = buffer.get_latest()
        oldest = buffer.get_oldest()
        operation_time = time.perf_counter() - start_time
        
        assert operation_time < 0.001  # Should be very fast even with large objects
