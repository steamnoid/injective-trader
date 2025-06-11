#!/usr/bin/env python3
"""
Multi-Market Performance Tester - Tests system performance with increasing numbers of high-volume markets
"""

import asyncio
import logging
import time
import psutil
import gc
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from collections import defaultdict

from injective_bot.connection import ConnectionState, MessageType, WebSocketMessage, MessageHandler
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.config import WebSocketConfig
from market_volume_analyzer import MarketVolumeAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for multi-market testing"""
    market_count: int
    test_duration: int
    total_messages: int
    messages_per_second: float
    cpu_usage_avg: float
    memory_usage_mb: float
    latency_avg_ms: float
    connection_stability: float
    errors_count: int
    success_rate: float

class PerformanceCollector(MessageHandler):
    """Collects performance data during multi-market testing"""
    
    def __init__(self):
        self.messages = []
        self.start_time = None
        self.end_time = None
        self.message_timestamps = []
        self.markets_seen = set()
        self.message_types = defaultdict(int)
        self.errors = []
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
            
        timestamp = datetime.now(timezone.utc)
        self.messages.append(message)
        self.message_timestamps.append(timestamp)
        
        if message.market_id:
            self.markets_seen.add(message.market_id)
            
        self.message_types[message.message_type] += 1
        
        # Log every 100 messages to track progress
        if len(self.messages) % 100 == 0:
            logger.info(f"📊 Received {len(self.messages)} messages from {len(self.markets_seen)} markets")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics"""
        if not self.messages:
            return {}
            
        self.end_time = datetime.now(timezone.utc)
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Calculate latencies (simplified - time between messages)
        latencies = []
        for i in range(1, len(self.message_timestamps)):
            latency = (self.message_timestamps[i] - self.message_timestamps[i-1]).total_seconds() * 1000
            latencies.append(latency)
        
        return {
            'total_messages': len(self.messages),
            'duration_seconds': duration,
            'messages_per_second': len(self.messages) / duration if duration > 0 else 0,
            'markets_seen': len(self.markets_seen),
            'average_latency_ms': sum(latencies) / len(latencies) if latencies else 0,
            'message_types': dict(self.message_types),
            'errors_count': len(self.errors)
        }

class SystemMonitor:
    """Monitors system resources during testing"""
    
    def __init__(self):
        self.cpu_readings = []
        self.memory_readings = []
        self.process = psutil.Process()
        self.monitoring = False
        
    async def start_monitoring(self):
        """Start system monitoring"""
        self.monitoring = True
        self.cpu_readings = []
        self.memory_readings = []
        
        while self.monitoring:
            try:
                # CPU usage
                cpu_percent = self.process.cpu_percent()
                self.cpu_readings.append(cpu_percent)
                
                # Memory usage
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                self.memory_readings.append(memory_mb)
                
                await asyncio.sleep(1)  # Sample every second
                
            except Exception as e:
                logger.warning(f"Monitoring error: {e}")
                await asyncio.sleep(1)
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
    
    def get_metrics(self) -> Dict[str, float]:
        """Get system performance metrics"""
        return {
            'cpu_avg': sum(self.cpu_readings) / len(self.cpu_readings) if self.cpu_readings else 0,
            'cpu_max': max(self.cpu_readings) if self.cpu_readings else 0,
            'memory_avg_mb': sum(self.memory_readings) / len(self.memory_readings) if self.memory_readings else 0,
            'memory_max_mb': max(self.memory_readings) if self.memory_readings else 0,
            'memory_current_mb': self.process.memory_info().rss / 1024 / 1024
        }

class MultiMarketPerformanceTester:
    """Tests performance with increasing numbers of markets"""
    
    def __init__(self):
        self.config = WebSocketConfig(
            connection_timeout=30.0,
            max_reconnect_attempts=3,
            message_queue_size=10000  # Larger queue for high throughput
        )
        
    async def get_top_volume_markets(self, count: int = 50) -> List[str]:
        """Get top volume markets for testing"""
        logger.info(f"🔍 Fetching top {count} volume markets...")
        
        analyzer = MarketVolumeAnalyzer()
        all_markets = await analyzer.fetch_all_spot_markets()
        top_markets = analyzer.get_top_volume_markets(all_markets, count)
        
        market_ids = [market.market_id for market in top_markets]
        
        logger.info(f"📊 Top {len(market_ids)} markets by volume:")
        for i, market in enumerate(top_markets[:10], 1):  # Show top 10
            logger.info(f"  {i:2d}. {market.ticker} - Volume: ${market.volume_24h}")
            
        return market_ids
    
    async def test_performance_with_n_markets(self, market_ids: List[str], n: int, duration: int = 60) -> PerformanceMetrics:
        """Test performance with N markets"""
        test_markets = market_ids[:n]
        
        logger.info(f"\n🧪 Testing performance with {n} markets for {duration} seconds")
        logger.info(f"   Markets: {[mid[:16] + '...' for mid in test_markets[:5]]}")
        
        # Setup client and collector
        client = InjectiveStreamClient(config=self.config, network="mainnet")
        collector = PerformanceCollector()
        monitor = SystemMonitor()
        
        client.register_handler(collector)
        
        try:
            # Start system monitoring
            monitor_task = asyncio.create_task(monitor.start_monitoring())
            
            # Connect to Injective
            connected = await client.connect()
            if not connected:
                raise Exception("Failed to connect to Injective")
                
            logger.info(f"✅ Connected, subscribing to {n} markets...")
            
            # Subscribe to orderbook updates for all markets
            await client.subscribe_spot_orderbook_updates(test_markets)
            
            # Also subscribe to trades for additional data
            try:
                await client.subscribe_spot_trades_updates(test_markets)
                logger.info(f"✅ Subscribed to both orderbook and trades for {n} markets")
            except Exception as e:
                logger.warning(f"⚠️ Trades subscription failed: {e}")
                logger.info(f"✅ Subscribed to orderbook only for {n} markets")
            
            # Wait for data collection
            logger.info(f"⏰ Collecting data for {duration} seconds...")
            start_time = time.time()
            
            # Monitor for the specified duration
            while time.time() - start_time < duration:
                await asyncio.sleep(5)
                
                # Log progress
                elapsed = time.time() - start_time
                collector_metrics = collector.get_metrics()
                system_metrics = monitor.get_metrics()
                
                logger.info(f"   Progress: {elapsed:.0f}s/{duration}s | "
                          f"Messages: {collector_metrics.get('total_messages', 0)} | "
                          f"Rate: {collector_metrics.get('messages_per_second', 0):.1f}/s | "
                          f"CPU: {system_metrics.get('cpu_avg', 0):.1f}% | "
                          f"RAM: {system_metrics.get('memory_current_mb', 0):.0f}MB")
            
            # Stop monitoring
            monitor.stop_monitoring()
            monitor_task.cancel()
            
            # Collect final metrics
            collector_metrics = collector.get_metrics()
            system_metrics = monitor.get_metrics()
            
            # Calculate performance metrics
            success_rate = 1.0 if collector_metrics.get('total_messages', 0) > 0 else 0.0
            if collector_metrics.get('markets_seen', 0) < n * 0.5:  # Less than 50% markets active
                success_rate *= 0.5
                
            performance = PerformanceMetrics(
                market_count=n,
                test_duration=duration,
                total_messages=collector_metrics.get('total_messages', 0),
                messages_per_second=collector_metrics.get('messages_per_second', 0),
                cpu_usage_avg=system_metrics.get('cpu_avg', 0),
                memory_usage_mb=system_metrics.get('memory_avg_mb', 0),
                latency_avg_ms=collector_metrics.get('average_latency_ms', 0),
                connection_stability=1.0,  # Simplified
                errors_count=collector_metrics.get('errors_count', 0),
                success_rate=success_rate
            )
            
            return performance
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            return PerformanceMetrics(
                market_count=n,
                test_duration=duration,
                total_messages=0,
                messages_per_second=0,
                cpu_usage_avg=0,
                memory_usage_mb=0,
                latency_avg_ms=0,
                connection_stability=0,
                errors_count=1,
                success_rate=0
            )
        finally:
            try:
                monitor.stop_monitoring()
                await client.disconnect()
                # Force garbage collection
                gc.collect()
                await asyncio.sleep(2)  # Cool down between tests
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
    
    async def run_scalability_test(self, max_markets: int = 50, step_size: int = 5, test_duration: int = 30):
        """Run complete scalability test"""
        logger.info(f"🚀 Starting scalability test: 1 to {max_markets} markets (step: {step_size})")
        
        # Get top volume markets
        market_ids = await self.get_top_volume_markets(max_markets)
        
        if not market_ids:
            logger.error("❌ No markets found for testing")
            return
        
        results = []
        
        # Test with increasing number of markets
        test_sizes = list(range(1, min(len(market_ids), max_markets) + 1, step_size))
        if max_markets not in test_sizes and max_markets <= len(market_ids):
            test_sizes.append(max_markets)
        
        for n in test_sizes:
            try:
                performance = await self.test_performance_with_n_markets(
                    market_ids, n, test_duration
                )
                results.append(performance)
                
                # Log results
                logger.info(f"📊 Results for {n} markets:")
                logger.info(f"   Messages/sec: {performance.messages_per_second:.2f}")
                logger.info(f"   CPU Usage: {performance.cpu_usage_avg:.1f}%")
                logger.info(f"   Memory: {performance.memory_usage_mb:.0f}MB")
                logger.info(f"   Success Rate: {performance.success_rate:.1%}")
                
                # Check if we're hitting limits
                if (performance.cpu_usage_avg > 80 or 
                    performance.memory_usage_mb > 400 or 
                    performance.success_rate < 0.5):
                    logger.warning(f"⚠️ Performance degradation detected at {n} markets")
                    if performance.success_rate < 0.2:
                        logger.error(f"❌ Critical failure at {n} markets, stopping test")
                        break
                        
            except Exception as e:
                logger.error(f"❌ Test failed for {n} markets: {e}")
                break
        
        # Print summary
        self._print_summary(results)
        return results
    
    def _print_summary(self, results: List[PerformanceMetrics]):
        """Print test summary"""
        if not results:
            return
            
        logger.info("\n" + "="*80)
        logger.info("🎯 SCALABILITY TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"{'Markets':<8} {'Msg/sec':<10} {'CPU%':<8} {'RAM(MB)':<10} {'Success%':<10}")
        logger.info("-"*80)
        
        for result in results:
            logger.info(f"{result.market_count:<8} "
                       f"{result.messages_per_second:<10.1f} "
                       f"{result.cpu_usage_avg:<8.1f} "
                       f"{result.memory_usage_mb:<10.0f} "
                       f"{result.success_rate*100:<10.1f}")
        
        # Find optimal configuration
        successful_results = [r for r in results if r.success_rate > 0.8]
        if successful_results:
            best = max(successful_results, key=lambda x: x.market_count)
            logger.info(f"\n🏆 RECOMMENDED CONFIGURATION:")
            logger.info(f"   Maximum Markets: {best.market_count}")
            logger.info(f"   Expected Throughput: {best.messages_per_second:.1f} messages/sec")
            logger.info(f"   Resource Usage: {best.cpu_usage_avg:.1f}% CPU, {best.memory_usage_mb:.0f}MB RAM")

async def main():
    """Main performance testing function"""
    tester = MultiMarketPerformanceTester()
    
    # Run quick test first (1-15 markets)
    logger.info("🚀 Running quick scalability test...")
    await tester.run_scalability_test(max_markets=15, step_size=3, test_duration=20)
    
    # Ask user if they want to run extended test
    logger.info("\n" + "="*80)
    logger.info("Quick test completed! Run extended test? (y/n)")
    
    # For automation, run extended test automatically
    logger.info("Running extended test automatically...")
    await asyncio.sleep(2)
    
    # Run extended test (1-50 markets)
    logger.info("🚀 Running extended scalability test...")
    await tester.run_scalability_test(max_markets=50, step_size=5, test_duration=30)

if __name__ == "__main__":
    asyncio.run(main())
