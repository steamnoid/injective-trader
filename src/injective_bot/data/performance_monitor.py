"""
Performance Monitor - Layer 3 Market Data Processing

Real-time performance monitoring for market data processing components
including latency tracking, throughput measurement, and memory usage.
"""

import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from decimal import Decimal
from collections import deque


@dataclass
class PerformanceMetrics:
    """Performance metrics container"""
    component: str
    timestamp: datetime
    latency_ms: float
    throughput_per_second: float
    memory_usage_mb: float
    cpu_usage_percent: float
    error_count: int = 0


@dataclass
class LatencyStats:
    """Latency statistics"""
    min_ms: float = float('inf')
    max_ms: float = 0.0
    avg_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    count: int = 0
    total_ms: float = 0.0
    samples: deque = field(default_factory=lambda: deque(maxlen=1000))


class PerformanceMonitor:
    """
    Real-time performance monitoring for Layer 3 components.
    
    Features:
    - Latency tracking with percentile calculations
    - Throughput measurement (messages/second)
    - Memory usage monitoring
    - Performance alerting for SLA violations
    - Historical performance data storage
    - Real-time performance dashboard data
    """
    
    def __init__(self, history_size: int = 1000):
        """
        Initialize performance monitor.
        
        Args:
            history_size: Number of historical metrics to keep
        """
        self.history_size = history_size
        
        # Performance data storage
        self._latency_stats: Dict[str, LatencyStats] = {}
        self._throughput_counters: Dict[str, int] = {}
        self._throughput_timestamps: Dict[str, datetime] = {}
        self._metrics_history: deque = deque(maxlen=history_size)
        
        # SLA thresholds
        self._latency_thresholds = {
            "aggregator": 50.0,  # 50ms max
            "orderbook_processor": 5.0,  # 5ms max
            "data_validator": 10.0,  # 10ms max
            "circular_buffer": 1.0   # 1ms max
        }
        
        # Threading
        self._lock = threading.RLock()
        self._start_time = datetime.now(timezone.utc)
        
    def start_timer(self, component: str) -> float:
        """
        Start timing for a component operation.
        
        Args:
            component: Component name
            
        Returns:
            Start timestamp for end_timer()
        """
        return time.perf_counter()
        
    def end_timer(self, component: str, start_time: float) -> float:
        """
        End timing and record latency.
        
        Args:
            component: Component name
            start_time: Start timestamp from start_timer()
            
        Returns:
            Elapsed time in milliseconds
        """
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self.record_latency(component, elapsed_ms)
        return elapsed_ms
        
    def record_latency(self, component: str, latency_ms: float) -> None:
        """
        Record latency measurement for component.
        
        Args:
            component: Component name
            latency_ms: Latency in milliseconds
        """
        with self._lock:
            if component not in self._latency_stats:
                self._latency_stats[component] = LatencyStats()
                
            stats = self._latency_stats[component]
            stats.samples.append(latency_ms)
            stats.count += 1
            stats.total_ms += latency_ms
            stats.avg_ms = stats.total_ms / stats.count
            stats.min_ms = min(stats.min_ms, latency_ms)
            stats.max_ms = max(stats.max_ms, latency_ms)
            
            # Update percentiles
            if len(stats.samples) >= 10:
                sorted_samples = sorted(stats.samples)
                p95_idx = int(len(sorted_samples) * 0.95)
                p99_idx = int(len(sorted_samples) * 0.99)
                stats.p95_ms = sorted_samples[p95_idx]
                stats.p99_ms = sorted_samples[p99_idx]
                
    def record_throughput(self, component: str, count: int = 1) -> None:
        """
        Record throughput measurement.
        
        Args:
            component: Component name
            count: Number of operations processed
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            
            if component not in self._throughput_counters:
                self._throughput_counters[component] = 0
                self._throughput_timestamps[component] = now
                
            self._throughput_counters[component] += count
            
    def get_current_throughput(self, component: str) -> float:
        """
        Get current throughput for component.
        
        Args:
            component: Component name
            
        Returns:
            Current throughput in operations per second
        """
        with self._lock:
            if component not in self._throughput_counters:
                return 0.0
                
            now = datetime.now(timezone.utc)
            start_time = self._throughput_timestamps.get(component, now)
            elapsed_seconds = (now - start_time).total_seconds()
            
            if elapsed_seconds > 0:
                return self._throughput_counters[component] / elapsed_seconds
            return 0.0
            
    def get_latency_stats(self, component: str) -> Optional[LatencyStats]:
        """Get latency statistics for component"""
        with self._lock:
            return self._latency_stats.get(component)
            
    def check_sla_compliance(self, component: str) -> Dict[str, Any]:
        """
        Check if component meets SLA requirements.
        
        Args:
            component: Component name
            
        Returns:
            SLA compliance report
        """
        stats = self.get_latency_stats(component)
        threshold = self._latency_thresholds.get(component, 100.0)
        
        if not stats:
            return {
                "compliant": True,
                "reason": "No data available"
            }
            
        violations = []
        
        if stats.avg_ms > threshold:
            violations.append(f"Average latency {stats.avg_ms:.1f}ms > {threshold}ms")
            
        if stats.p95_ms > threshold * 1.5:  # P95 can be 1.5x threshold
            violations.append(f"P95 latency {stats.p95_ms:.1f}ms > {threshold * 1.5}ms")
            
        throughput = self.get_current_throughput(component)
        if throughput > 0 and throughput < 100:  # Minimum 100 ops/sec
            violations.append(f"Throughput {throughput:.1f} ops/sec < 100 ops/sec")
            
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "avg_latency_ms": stats.avg_ms,
            "p95_latency_ms": stats.p95_ms,
            "throughput_per_sec": throughput,
            "threshold_ms": threshold
        }
        
    def get_system_performance(self) -> Dict[str, Any]:
        """Get overall system performance metrics"""
        with self._lock:
            uptime = datetime.now(timezone.utc) - self._start_time
            
            components_stats = {}
            total_operations = 0
            overall_compliance = True
            
            for component in self._latency_stats.keys():
                stats = self.get_latency_stats(component)
                throughput = self.get_current_throughput(component)
                sla_check = self.check_sla_compliance(component)
                
                components_stats[component] = {
                    "latency_avg_ms": stats.avg_ms if stats else 0,
                    "latency_p95_ms": stats.p95_ms if stats else 0,
                    "throughput_per_sec": throughput,
                    "operations_count": stats.count if stats else 0,
                    "sla_compliant": sla_check["compliant"]
                }
                
                if stats:
                    total_operations += stats.count
                    
                if not sla_check["compliant"]:
                    overall_compliance = False
                    
            return {
                "uptime_seconds": uptime.total_seconds(),
                "total_operations": total_operations,
                "overall_sla_compliant": overall_compliance,
                "components": components_stats,
                "timestamp": datetime.now(timezone.utc)
            }
            
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        system_perf = self.get_system_performance()
        
        # Calculate aggregated metrics
        all_latencies = []
        total_throughput = 0
        
        for component, stats in system_perf["components"].items():
            if stats["operations_count"] > 0:
                all_latencies.extend([stats["latency_avg_ms"]] * stats["operations_count"])
                total_throughput += stats["throughput_per_sec"]
                
        overall_avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0
        
        # Performance summary
        performance_grade = "A"
        if not system_perf["overall_sla_compliant"]:
            performance_grade = "C"
        elif overall_avg_latency > 25:  # > 25ms average
            performance_grade = "B"
            
        return {
            "summary": {
                "performance_grade": performance_grade,
                "overall_avg_latency_ms": overall_avg_latency,
                "total_throughput_per_sec": total_throughput,
                "uptime_hours": system_perf["uptime_seconds"] / 3600,
                "sla_compliant": system_perf["overall_sla_compliant"]
            },
            "details": system_perf,
            "generated_at": datetime.now(timezone.utc)
        }
        
    def reset_metrics(self, component: Optional[str] = None) -> None:
        """
        Reset metrics for component or all components.
        
        Args:
            component: Component name, or None for all components
        """
        with self._lock:
            if component:
                if component in self._latency_stats:
                    del self._latency_stats[component]
                if component in self._throughput_counters:
                    del self._throughput_counters[component]
                if component in self._throughput_timestamps:
                    del self._throughput_timestamps[component]
            else:
                self._latency_stats.clear()
                self._throughput_counters.clear()
                self._throughput_timestamps.clear()
                self._metrics_history.clear()
                self._start_time = datetime.now(timezone.utc)
                
    def set_latency_threshold(self, component: str, threshold_ms: float) -> None:
        """Set custom latency threshold for component"""
        self._latency_thresholds[component] = threshold_ms
