#!/usr/bin/env python3
"""
Performance Scalability Test - Test system with increasing numbers of high-volume markets
Tests performance limits and determines optimal market count configuration
"""

import asyncio
import logging
import time
import psutil
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
from datetime import datetime, timezone

from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for a test run"""
    market_count: int
    messages_received: int
    test_duration: float
    messages_per_second: float
    cpu_usage_percent: float
    memory_usage_mb: float
    connection_setup_time: float
    success_rate: float
    errors_count: int
    peak_memory_mb: float
    average_message_size: float

class PerformanceScalabilityTest:
    """Tests system performance with increasing numbers of markets"""
    
    def __init__(self, network: str = "mainnet"):
        self.network = Network.mainnet() if network == "mainnet" else Network.testnet()
        self.client: Optional[AsyncClient] = None
        self.process = psutil.Process(os.getpid())
        
        # High-volume USD markets (from our debug analysis)
        self.high_volume_markets = [
            "0xe8bf0467208c24209c1cf0fd64833fa43eb6e8035869f9d043dbff815ab76d01",  # UNI/USDT
            "0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # INJ/USDT
            "0x28f3c9897e23750bf653889224f93390c467b83c86d736af79431958fff833d1",  # MATIC/USDT
            "0x26413a70c9b78a495023e5ab8003c9cf963ef963f6755f8b57255feb5744bf31",  # LINK/USDT
            "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034",  # WETH/USDT
            "0x01edfab47f124748dc89998eb33144af734484ba07099014594321729a0ca16b",  # AAVE/USDT
            "0x29255e99290ff967bc8b351ce5b1cb08bc76a9a9d012133fb242bdf92cd28d89",  # GRT/USDT
            "0x0c9f98c99b23e89dbf6a60bec05372790b39e03da0f86dd0208fc8e28751bd8c",  # SUSHI/USDT
            "0x51092ddec80dfd0d41fee1a7d93c8465de47cd33966c8af8ee66c14fe341a545",  # SNX/USDT
            "0xbe9d4a0a768c7e8efb6740be76af955928f93c247e0b3a1a106184c6cf3216a7",  # QNT/USDT
        ]
        
    async def get_more_markets(self) -> List[str]:
        """Fetch additional USD markets for extended testing"""
        try:
            client = AsyncClient(self.network)
            markets_response = await client.fetch_spot_markets()
            
            additional_markets = []
            if isinstance(markets_response, dict) and 'markets' in markets_response:
                for market in markets_response['markets']:
                    if isinstance(market, dict):
                        ticker = market.get('ticker', '')
                        market_id = market.get('marketId', '')
                        quote_denom = market.get('quoteDenom', '')
                        
                        # Find USD markets not already in our list
                        if (('USD' in ticker or 'USD' in quote_denom or 
                             'usdt' in quote_denom.lower() or 'usdc' in quote_denom.lower()) and
                            market_id not in self.high_volume_markets and
                            market.get('marketStatus') == 'active'):
                            additional_markets.append(market_id)
                            
            return additional_markets[:40]  # Return up to 40 additional markets
            
        except Exception as e:
            logger.error(f"Error fetching additional markets: {e}")
            return []
    
    async def setup_client(self) -> bool:
        """Setup Injective client"""
        try:
            self.client = AsyncClient(self.network)
            logger.info(f"✅ Connected to Injective {self.network.chain_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Injective: {e}")
            return False
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            return self.process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            return self.process.cpu_percent()
        except:
            return 0.0
    
    async def test_market_count(self, market_count: int, test_duration: int = 30) -> PerformanceMetrics:
        """Test performance with specific number of markets"""
        if not self.client:
            raise RuntimeError("Client not connected")
        
        # Get markets to test
        test_markets = self.high_volume_markets[:market_count]
        if len(test_markets) < market_count:
            # Get additional markets if needed
            additional = await self.get_more_markets()
            test_markets.extend(additional[:market_count - len(test_markets)])
        
        test_markets = test_markets[:market_count]  # Ensure exact count
        
        logger.info(f"🧪 Testing {len(test_markets)} markets for {test_duration}s")
        
        # Performance tracking
        messages_received = 0
        errors_count = 0
        message_sizes = []
        peak_memory = self.get_memory_usage()
        
        def message_callback(data):
            nonlocal messages_received, peak_memory
            messages_received += 1
            
            # Track message size
            try:
                message_size = len(str(data))
                message_sizes.append(message_size)
            except:
                pass
            
            # Track peak memory
            current_memory = self.get_memory_usage()
            if current_memory > peak_memory:
                peak_memory = current_memory
        
        # Measure connection setup time
        setup_start = time.time()
        subscription_tasks = []
        
        try:
            # Create separate subscription for each market (as per our fixed approach)
            for market_id in test_markets:
                try:
                    task = asyncio.create_task(
                        self.client.listen_spot_orderbook_updates(
                            market_ids=[market_id],
                            callback=message_callback
                        )
                    )
                    subscription_tasks.append(task)
                except Exception as e:
                    logger.warning(f"Failed to subscribe to {market_id}: {e}")
                    errors_count += 1
            
            connection_setup_time = time.time() - setup_start
            logger.info(f"📡 Setup {len(subscription_tasks)} subscriptions in {connection_setup_time:.2f}s")
            
            # Measure initial system state
            initial_memory = self.get_memory_usage()
            initial_cpu = self.get_cpu_usage()
            
            # Wait for data collection
            test_start = time.time()
            await asyncio.sleep(test_duration)
            test_end = time.time()
            
            actual_duration = test_end - test_start
            
            # Measure final system state
            final_memory = self.get_memory_usage()
            final_cpu = self.get_cpu_usage()
            
            # Clean up subscriptions
            for task in subscription_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Calculate metrics
            messages_per_second = messages_received / actual_duration if actual_duration > 0 else 0
            success_rate = ((len(subscription_tasks) - errors_count) / len(test_markets)) * 100 if test_markets else 0
            average_message_size = sum(message_sizes) / len(message_sizes) if message_sizes else 0
            
            return PerformanceMetrics(
                market_count=len(test_markets),
                messages_received=messages_received,
                test_duration=actual_duration,
                messages_per_second=messages_per_second,
                cpu_usage_percent=(initial_cpu + final_cpu) / 2,
                memory_usage_mb=final_memory,
                connection_setup_time=connection_setup_time,
                success_rate=success_rate,
                errors_count=errors_count,
                peak_memory_mb=peak_memory,
                average_message_size=average_message_size
            )
            
        except Exception as e:
            logger.error(f"Error during test: {e}")
            # Clean up on error
            for task in subscription_tasks:
                task.cancel()
                try:
                    await task
                except:
                    pass
            raise
    
    async def run_scalability_test(self, max_markets: int = 30, test_duration: int = 20) -> List[PerformanceMetrics]:
        """Run complete scalability test with increasing market counts"""
        if not await self.setup_client():
            return []
        
        # Get all available markets
        all_markets = self.high_volume_markets + await self.get_more_markets()
        max_testable = min(max_markets, len(all_markets))
        
        logger.info(f"🎯 Starting scalability test with up to {max_testable} markets")
        logger.info(f"📊 Test duration: {test_duration}s per configuration")
        logger.info("=" * 80)
        
        results = []
        
        # Test configurations: 1, 2, 3, 5, 10, 15, 20, 25, 30, etc.
        test_counts = [1, 2, 3, 5, 10, 15, 20, 25, 30, 40, 50]
        test_counts = [count for count in test_counts if count <= max_testable]
        
        for market_count in test_counts:
            try:
                logger.info(f"\n🧪 Testing {market_count} markets...")
                
                metrics = await self.test_market_count(market_count, test_duration)
                results.append(metrics)
                
                # Log results
                logger.info(f"✅ Results for {market_count} markets:")
                logger.info(f"   Messages/sec: {metrics.messages_per_second:.1f}")
                logger.info(f"   Success rate: {metrics.success_rate:.1f}%")
                logger.info(f"   Memory usage: {metrics.memory_usage_mb:.1f} MB")
                logger.info(f"   CPU usage: {metrics.cpu_usage_percent:.1f}%")
                logger.info(f"   Setup time: {metrics.connection_setup_time:.2f}s")
                
                # Check for degradation
                if len(results) > 1:
                    prev_metrics = results[-2]
                    if (metrics.success_rate < 90 or 
                        metrics.messages_per_second < prev_metrics.messages_per_second * 0.5):
                        logger.warning(f"⚠️  Performance degradation detected at {market_count} markets")
                
                # Brief pause between tests
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Test failed for {market_count} markets: {e}")
                break
        
        return results
    
    def analyze_results(self, results: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Analyze test results and provide recommendations"""
        if not results:
            return {"error": "No results to analyze"}
        
        # Find optimal configuration
        optimal_count = 1
        best_efficiency = 0
        
        for metrics in results:
            if metrics.success_rate >= 95:  # Only consider highly successful configurations
                efficiency = metrics.messages_per_second / metrics.memory_usage_mb
                if efficiency > best_efficiency:
                    best_efficiency = efficiency
                    optimal_count = metrics.market_count
        
        # Performance trends
        max_throughput = max(results, key=lambda x: x.messages_per_second)
        max_markets_successful = max([r for r in results if r.success_rate >= 95], 
                                   key=lambda x: x.market_count, default=results[0])
        
        analysis = {
            "total_configurations_tested": len(results),
            "optimal_market_count": optimal_count,
            "max_throughput_config": {
                "market_count": max_throughput.market_count,
                "messages_per_second": max_throughput.messages_per_second,
                "success_rate": max_throughput.success_rate
            },
            "max_stable_markets": max_markets_successful.market_count,
            "performance_trends": {
                "throughput_per_market": [r.messages_per_second / r.market_count for r in results],
                "memory_scaling": [r.memory_usage_mb for r in results],
                "cpu_scaling": [r.cpu_usage_percent for r in results],
                "success_rates": [r.success_rate for r in results]
            },
            "recommendations": self._generate_recommendations(results, optimal_count)
        }
        
        return analysis
    
    def _generate_recommendations(self, results: List[PerformanceMetrics], optimal_count: int) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        recommendations.append(f"🎯 Recommended market count: {optimal_count} for optimal efficiency")
        
        # Memory usage recommendations
        avg_memory = sum(r.memory_usage_mb for r in results) / len(results)
        if avg_memory > 500:
            recommendations.append("⚠️  High memory usage detected - consider memory optimization")
        
        # Success rate analysis
        poor_success_configs = [r for r in results if r.success_rate < 90]
        if poor_success_configs:
            min_poor = min(poor_success_configs, key=lambda x: x.market_count)
            recommendations.append(f"⚠️  Success rate drops below 90% at {min_poor.market_count} markets")
        
        # Throughput analysis
        if len(results) > 2:
            throughput_trend = []
            for i in range(1, len(results)):
                if results[i-1].messages_per_second > 0:  # Avoid division by zero
                    trend = results[i].messages_per_second / results[i-1].messages_per_second
                    throughput_trend.append(trend)
            
            if throughput_trend:  # Only if we have valid trends
                avg_trend = sum(throughput_trend) / len(throughput_trend)
                if avg_trend < 0.8:
                    recommendations.append("📉 Throughput scaling is poor - consider connection optimization")
        
        return recommendations
    
    def save_results(self, results: List[PerformanceMetrics], analysis: Dict[str, Any], 
                    filename: str = "performance_test_results.json"):
        """Save test results to file"""
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_configuration": {
                "network": self.network.chain_id,
                "markets_tested": len(self.high_volume_markets)
            },
            "results": [
                {
                    "market_count": r.market_count,
                    "messages_received": r.messages_received,
                    "test_duration": r.test_duration,
                    "messages_per_second": r.messages_per_second,
                    "cpu_usage_percent": r.cpu_usage_percent,
                    "memory_usage_mb": r.memory_usage_mb,
                    "connection_setup_time": r.connection_setup_time,
                    "success_rate": r.success_rate,
                    "errors_count": r.errors_count,
                    "peak_memory_mb": r.peak_memory_mb,
                    "average_message_size": r.average_message_size
                }
                for r in results
            ],
            "analysis": analysis
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"💾 Results saved to {filename}")

async def main():
    """Main performance test function"""
    tester = PerformanceScalabilityTest(network="mainnet")
    
    try:
        logger.info("🚀 Starting Injective Performance Scalability Test")
        logger.info("=" * 80)
        
        # Run scalability test
        results = await tester.run_scalability_test(max_markets=25, test_duration=20)
        
        if not results:
            logger.error("❌ No test results obtained")
            return
        
        # Analyze results
        analysis = tester.analyze_results(results)
        
        # Display summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 PERFORMANCE SCALABILITY TEST SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"✅ Tested {analysis['total_configurations_tested']} configurations")
        logger.info(f"🎯 Optimal market count: {analysis['optimal_market_count']}")
        logger.info(f"🚀 Max throughput: {analysis['max_throughput_config']['messages_per_second']:.1f} msg/sec "
                   f"at {analysis['max_throughput_config']['market_count']} markets")
        logger.info(f"🏆 Max stable markets: {analysis['max_stable_markets']} (≥95% success)")
        
        logger.info("\n📋 RECOMMENDATIONS:")
        for rec in analysis['recommendations']:
            logger.info(f"   {rec}")
        
        # Save results
        tester.save_results(results, analysis)
        
        logger.info("\n✅ Performance scalability test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
