"""
Unit tests for PerformanceMonitor - Layer 3 Market Data Processing

Test Coverage:
- Latency tracking and statistics
- Throughput measurement and calculation
- SLA compliance checking
- Performance reporting
- Multi-component monitoring
- Thread safety and concurrent access
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock

from injective_bot.data.performance_monitor import PerformanceMonitor, PerformanceMetrics, LatencyStats


class TestPerformanceMonitor:
    """Test suite for PerformanceMonitor class."""

    @pytest.fixture
    def monitor(self):
        """Create PerformanceMonitor instance for testing."""
        return PerformanceMonitor(history_size=100)

    def test_monitor_initialization(self, monitor):
        """Test PerformanceMonitor initialization."""
        assert monitor is not None
        assert monitor.history_size == 100
        assert len(monitor._latency_stats) == 0
        assert len(monitor._throughput_counters) == 0
        
        # Check default thresholds
        assert monitor._latency_thresholds["aggregator"] == 50.0
        assert monitor._latency_thresholds["orderbook_processor"] == 5.0
        assert monitor._latency_thresholds["data_validator"] == 10.0
        assert monitor._latency_thresholds["circular_buffer"] == 1.0

    def test_timer_functionality(self, monitor):
        """Test start_timer and end_timer functionality."""
        component = "test_component"
        
        # Start timer
        start_time = monitor.start_timer(component)
        assert isinstance(start_time, float)
        assert start_time > 0
        
        # Simulate some work
        time.sleep(0.01)  # 10ms
        
        # End timer
        elapsed_ms = monitor.end_timer(component, start_time)
        assert elapsed_ms >= 10  # Should be at least 10ms
        assert elapsed_ms < 100  # Should be reasonable
        
        # Check that latency was recorded
        stats = monitor.get_latency_stats(component)
        assert stats is not None
        assert stats.count == 1
        assert stats.avg_ms >= 10

    def test_latency_recording(self, monitor):
        """Test latency recording and statistics calculation."""
        component = "test_latency"
        latencies = [10.0, 20.0, 15.0, 25.0, 12.0]
        
        # Record multiple latencies
        for latency in latencies:
            monitor.record_latency(component, latency)
        
        stats = monitor.get_latency_stats(component)
        assert stats is not None
        assert stats.count == 5
        assert stats.avg_ms == sum(latencies) / len(latencies)  # 16.4
        assert stats.min_ms == min(latencies)  # 10.0
        assert stats.max_ms == max(latencies)  # 25.0
        assert len(stats.samples) == 5

    def test_percentile_calculations(self, monitor):
        """Test P95 and P99 percentile calculations."""
        component = "percentile_test"
        
        # Record enough samples for percentile calculation
        latencies = list(range(1, 101))  # 1-100ms
        for latency in latencies:
            monitor.record_latency(component, float(latency))
        
        stats = monitor.get_latency_stats(component)
        assert stats is not None
        # P95 of 1-100 should be 96 (95% of 100 items = index 95, which is value 96)
        assert stats.p95_ms == 96.0  # 95th percentile
        assert stats.p99_ms == 100.0  # 99th percentile

    def test_throughput_measurement(self, monitor):
        """Test throughput recording and calculation."""
        component = "throughput_test"
        
        # Record throughput over time
        monitor.record_throughput(component, 10)
        time.sleep(0.1)  # 100ms
        monitor.record_throughput(component, 20)
        time.sleep(0.1)  # Another 100ms
        monitor.record_throughput(component, 30)
        
        throughput = monitor.get_current_throughput(component)
        assert throughput > 0
        # Should be roughly 60 operations in ~200ms = 300 ops/sec
        assert throughput > 200  # Allow for timing variance

    def test_sla_compliance_checking(self, monitor):
        """Test SLA compliance validation."""
        component = "sla_test"
        
        # Test compliant case
        monitor.record_latency(component, 5.0)  # Under threshold
        monitor.record_latency(component, 8.0)
        monitor.record_latency(component, 6.0)
        
        compliance = monitor.check_sla_compliance(component)
        assert compliance["compliant"] is True
        assert len(compliance["violations"]) == 0
        assert compliance["avg_latency_ms"] < 10

    def test_sla_violations_detection(self, monitor):
        """Test SLA violation detection."""
        component = "violation_test"
        
        # Record high latencies that violate SLA
        for _ in range(10):
            monitor.record_latency(component, 200.0)  # Way over threshold
        
        compliance = monitor.check_sla_compliance(component)
        assert compliance["compliant"] is False
        assert len(compliance["violations"]) > 0
        assert "Average latency" in compliance["violations"][0]

    def test_no_data_sla_compliance(self, monitor):
        """Test SLA compliance when no data is available."""
        component = "no_data_test"
        
        compliance = monitor.check_sla_compliance(component)
        assert compliance["compliant"] is True
        assert compliance["reason"] == "No data available"

    def test_custom_latency_thresholds(self, monitor):
        """Test setting custom latency thresholds."""
        component = "custom_threshold_test"
        custom_threshold = 25.0
        
        # Set custom threshold
        monitor.set_latency_threshold(component, custom_threshold)
        
        # Record latency above default but below custom threshold
        monitor.record_latency(component, 20.0)
        
        compliance = monitor.check_sla_compliance(component)
        assert compliance["compliant"] is True
        assert compliance["threshold_ms"] == custom_threshold

    def test_system_performance_overview(self, monitor):
        """Test system-wide performance overview."""
        components = ["comp1", "comp2", "comp3"]
        
        # Record data for multiple components
        for i, comp in enumerate(components):
            for _ in range(5):
                monitor.record_latency(comp, 10.0 + i * 5)
                monitor.record_throughput(comp, 10)
        
        system_perf = monitor.get_system_performance()
        assert "uptime_seconds" in system_perf
        assert "total_operations" in system_perf
        assert "overall_sla_compliant" in system_perf
        assert "components" in system_perf
        assert len(system_perf["components"]) == 3
        
        # Check component details
        for comp in components:
            assert comp in system_perf["components"]
            comp_stats = system_perf["components"][comp]
            assert "latency_avg_ms" in comp_stats
            assert "throughput_per_sec" in comp_stats
            assert "operations_count" in comp_stats

    def test_performance_report_generation(self, monitor):
        """Test comprehensive performance report generation."""
        component = "report_test"
        
        # Record some performance data
        for _ in range(10):
            monitor.record_latency(component, 15.0)
            monitor.record_throughput(component, 5)
        
        report = monitor.get_performance_report()
        assert "summary" in report
        assert "details" in report
        assert "generated_at" in report
        
        summary = report["summary"]
        assert "performance_grade" in summary
        assert "overall_avg_latency_ms" in summary
        assert "total_throughput_per_sec" in summary
        assert "uptime_hours" in summary
        assert "sla_compliant" in summary
        
        # Performance grade should be A or B for good performance
        assert summary["performance_grade"] in ["A", "B", "C"]

    def test_performance_grade_calculation(self, monitor):
        """Test performance grade calculation logic."""
        # Test Grade A (excellent performance)
        good_comp = "good_component"
        for _ in range(10):
            monitor.record_latency(good_comp, 5.0)  # Low latency
            monitor.record_throughput(good_comp, 20)  # Good throughput
        
        report = monitor.get_performance_report()
        assert report["summary"]["performance_grade"] == "A"
        
        # Test Grade B (higher latency)
        monitor.reset_metrics()
        avg_comp = "avg_component"
        for _ in range(10):
            monitor.record_latency(avg_comp, 30.0)  # Higher latency but compliant
            monitor.record_throughput(avg_comp, 15)
        
        report = monitor.get_performance_report()
        assert report["summary"]["performance_grade"] == "B"

    def test_metrics_reset_functionality(self, monitor):
        """Test metrics reset for individual and all components."""
        comp1, comp2 = "comp1", "comp2"
        
        # Record data for both components
        monitor.record_latency(comp1, 10.0)
        monitor.record_latency(comp2, 15.0)
        monitor.record_throughput(comp1, 5)
        monitor.record_throughput(comp2, 8)
        
        # Reset single component
        monitor.reset_metrics(comp1)
        assert monitor.get_latency_stats(comp1) is None
        assert monitor.get_latency_stats(comp2) is not None
        
        # Reset all components
        monitor.reset_metrics()
        assert monitor.get_latency_stats(comp2) is None
        assert len(monitor._latency_stats) == 0
        assert len(monitor._throughput_counters) == 0

    def test_thread_safety(self, monitor):
        """Test thread safety of performance monitoring."""
        component = "thread_test"
        num_threads = 10
        operations_per_thread = 100
        results = []
        errors = []
        
        def worker():
            try:
                for i in range(operations_per_thread):
                    # Simulate latency recording
                    monitor.record_latency(component, 10.0 + i % 10)
                    monitor.record_throughput(component, 1)
                results.append("success")
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors and correct data
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == num_threads
        
        stats = monitor.get_latency_stats(component)
        assert stats.count == num_threads * operations_per_thread
        
        throughput = monitor.get_current_throughput(component)
        assert throughput > 0

    def test_performance_requirement_validation(self, monitor):
        """Test that performance monitor meets <50ms requirement."""
        component = "performance_test"
        num_operations = 1000
        
        start_time = time.perf_counter()
        
        # Perform many operations to test performance
        for i in range(num_operations):
            monitor.record_latency(component, float(i % 50))
            if i % 10 == 0:
                monitor.record_throughput(component, 10)
            
            # Periodic checks
            if i % 100 == 0:
                monitor.get_latency_stats(component)
                monitor.check_sla_compliance(component)
        
        end_time = time.perf_counter()
        total_time_ms = (end_time - start_time) * 1000
        avg_time_per_op = total_time_ms / num_operations
        
        # Should process operations very quickly
        assert avg_time_per_op < 1.0, f"Average time per operation {avg_time_per_op:.3f}ms too slow"
        
        # Final system report should generate quickly
        report_start = time.perf_counter()
        report = monitor.get_performance_report()
        report_time = (time.perf_counter() - report_start) * 1000
        
        assert report_time < 50, f"Performance report generation took {report_time:.2f}ms > 50ms"

    def test_memory_efficiency_under_load(self, monitor):
        """Test memory efficiency with large datasets."""
        import sys
        
        component = "memory_test"
        
        # Get initial memory usage
        initial_size = sys.getsizeof(monitor._latency_stats)
        
        # Add lots of data
        for i in range(2000):  # Exceed history_size
            monitor.record_latency(component, float(i % 100))
            monitor.record_throughput(component, 1)
        
        # Check that circular buffer limits are respected
        stats = monitor.get_latency_stats(component)
        assert len(stats.samples) <= 1000  # maxlen in LatencyStats
        
        # Memory should not grow excessively
        final_size = sys.getsizeof(monitor._latency_stats)
        growth_ratio = final_size / initial_size if initial_size > 0 else 1
        assert growth_ratio < 10, f"Memory grew {growth_ratio}x, possible memory leak"

    def test_edge_case_handling(self, monitor):
        """Test edge cases and error handling."""
        # Test with zero latency
        monitor.record_latency("zero_test", 0.0)
        stats = monitor.get_latency_stats("zero_test")
        assert stats.min_ms == 0.0
        assert stats.avg_ms == 0.0
        
        # Test with very high latency
        monitor.record_latency("high_test", 10000.0)
        stats = monitor.get_latency_stats("high_test")
        assert stats.max_ms == 10000.0
        
        # Test throughput with zero elapsed time (edge case)
        monitor.record_throughput("instant_test", 100)
        throughput = monitor.get_current_throughput("instant_test")
        assert throughput >= 0  # Should handle gracefully
        
        # Test SLA check with very small thresholds
        monitor.set_latency_threshold("tiny_test", 0.1)
        monitor.record_latency("tiny_test", 1.0)
        compliance = monitor.check_sla_compliance("tiny_test")
        assert compliance["compliant"] is False

    def test_concurrent_component_monitoring(self, monitor):
        """Test monitoring multiple components concurrently."""
        components = [f"comp_{i}" for i in range(20)]
        
        def monitor_component(comp_name):
            for i in range(50):
                latency = 5.0 + (hash(comp_name) % 10)  # Deterministic variance
                monitor.record_latency(comp_name, latency)
                monitor.record_throughput(comp_name, 2)
        
        # Monitor multiple components in parallel
        threads = [threading.Thread(target=monitor_component, args=(comp,)) 
                  for comp in components]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all components were tracked
        system_perf = monitor.get_system_performance()
        assert len(system_perf["components"]) == len(components)
        
        # Each component should have recorded data
        for comp in components:
            stats = monitor.get_latency_stats(comp)
            assert stats is not None
            assert stats.count == 50
            
        # Total operations should sum correctly
        total_ops = sum(stats.count for stats in monitor._latency_stats.values())
        assert total_ops == len(components) * 50
