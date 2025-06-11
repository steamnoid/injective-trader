#!/usr/bin/env python3
"""
Discovery Phase: Explore all available listen_* methods in injective-py
to understand which methods provide the best data streaming for our trading bot.

This script will:
1. Enumerate all available listen_* methods
2. Test each method individually with our target markets
3. Compare message rates and data quality
4. Identify the optimal methods for real-time trading
"""

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class MethodResult:
    """Track results for each listen method"""
    method_name: str
    success: bool = False
    message_count: int = 0
    error: Optional[str] = None
    markets_with_data: Set[str] = field(default_factory=set)
    first_message_time: Optional[datetime] = None
    last_message_time: Optional[datetime] = None
    message_rate: float = 0.0  # messages per second
    data_types_seen: Set[str] = field(default_factory=set)

class MethodDiscovery:
    """Discover and test all available listen_* methods"""
    
    def __init__(self):
        self.client = None
        self.network = Network.mainnet()
        self.test_markets = [
            "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce",  # BTC/USDT
            "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034",  # WETH/USDT
        ]
        self.results: Dict[str, MethodResult] = {}
        
    async def initialize_client(self) -> bool:
        """Initialize the AsyncClient"""
        try:
            self.client = AsyncClient(self.network)
            logger.info("✅ AsyncClient initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize client: {e}")
            return False
    
    def discover_listen_methods(self) -> List[str]:
        """Find all listen_* methods available in AsyncClient"""
        if not self.client:
            return []
        
        methods = []
        for name in dir(self.client):
            if name.startswith('listen_') and callable(getattr(self.client, name)):
                methods.append(name)
        
        logger.info(f"🔍 Found {len(methods)} listen_* methods:")
        for method in sorted(methods):
            # Get method signature
            method_obj = getattr(self.client, method)
            try:
                sig = inspect.signature(method_obj)
                logger.info(f"  📋 {method}{sig}")
            except Exception:
                logger.info(f"  📋 {method} (signature unavailable)")
        
        return methods
    
    async def test_method(self, method_name: str, timeout: int = 15) -> MethodResult:
        """Test a specific listen method"""
        result = MethodResult(method_name=method_name)
        
        logger.info(f"\n🧪 Testing method: {method_name}")
        
        try:
            method = getattr(self.client, method_name)
            sig = inspect.signature(method)
            
            # Analyze method signature to determine how to call it
            params = sig.parameters
            logger.info(f"  📝 Parameters: {list(params.keys())}")
            
            # Create a message collector for this method
            messages = []
            markets_seen = set()
            data_types = set()
            
            def message_callback(message):
                nonlocal messages, markets_seen, data_types
                messages.append({
                    'timestamp': datetime.now(timezone.utc),
                    'data': message,
                    'type': type(message).__name__
                })
                
                # Try to extract market info
                if hasattr(message, 'market_id'):
                    markets_seen.add(message.market_id)
                elif hasattr(message, 'marketId'):
                    markets_seen.add(message.marketId)
                
                # Track data types
                data_types.add(type(message).__name__)
                
                if len(messages) <= 5:  # Log first few messages
                    logger.info(f"    📨 Message {len(messages)}: {type(message).__name__}")
            
            # Determine how to call the method based on its signature
            call_args = self._prepare_method_call(method_name, params)
            
            if call_args is None:
                result.error = "Unable to determine method call parameters"
                return result
            
            # Add callback to args
            call_args['callback'] = message_callback
            
            logger.info(f"  🚀 Calling {method_name} with args: {list(call_args.keys())}")
            
            # Start the method and wait for messages
            start_time = datetime.now(timezone.utc)
            
            # Create task for the listen method
            listen_task = asyncio.create_task(method(**call_args))
            
            # Wait for timeout or completion
            try:
                await asyncio.wait_for(listen_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.info(f"  ⏰ Method {method_name} timed out after {timeout}s (expected)")
                listen_task.cancel()
            except Exception as e:
                logger.warning(f"  ⚠️ Method {method_name} ended with: {e}")
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            # Analyze results
            result.success = len(messages) > 0
            result.message_count = len(messages)
            result.markets_with_data = markets_seen
            result.data_types_seen = data_types
            result.message_rate = len(messages) / duration if duration > 0 else 0
            
            if messages:
                result.first_message_time = messages[0]['timestamp']
                result.last_message_time = messages[-1]['timestamp']
            
            logger.info(f"  📊 Results: {result.message_count} messages, {len(markets_seen)} markets, rate: {result.message_rate:.2f} msg/s")
            
        except Exception as e:
            logger.error(f"  ❌ Method {method_name} failed: {e}")
            result.error = str(e)
        
        return result
    
    def _prepare_method_call(self, method_name: str, params: Dict) -> Optional[Dict[str, Any]]:
        """Prepare method call arguments based on method signature"""
        args = {}
        
        # Common parameter mappings
        param_names = list(params.keys())
        
        # Skip 'self' parameter
        if 'self' in param_names:
            param_names.remove('self')
        
        logger.info(f"  🔧 Preparing call for parameters: {param_names}")
        
        # Handle market_ids parameter (most common)
        if 'market_ids' in param_names:
            args['market_ids'] = self.test_markets
        elif 'market_id' in param_names:
            args['market_id'] = self.test_markets[0]  # Single market for methods that don't support multiple
        
        # Handle other common parameters
        if 'subaccount_id' in param_names:
            # Skip methods that require subaccount_id for now
            logger.info(f"  ⏩ Skipping {method_name} - requires subaccount_id")
            return None
        
        if 'order_side' in param_names:
            # Skip methods that require specific order side
            logger.info(f"  ⏩ Skipping {method_name} - requires order_side")
            return None
        
        if 'execution_side' in param_names:
            # Skip methods that require execution side
            logger.info(f"  ⏩ Skipping {method_name} - requires execution_side")
            return None
        
        # Note: 'callback' will be added by the caller
        
        return args
    
    async def run_discovery(self) -> Dict[str, MethodResult]:
        """Run complete discovery process"""
        logger.info("🔎 Starting Injective Listen Methods Discovery")
        
        # Initialize client
        if not await self.initialize_client():
            return {}
        
        # Discover all methods
        methods = self.discover_listen_methods()
        
        if not methods:
            logger.error("❌ No listen methods found")
            return {}
        
        # Test each method
        logger.info(f"\n🧪 Testing {len(methods)} methods...")
        
        for method_name in sorted(methods):
            result = await self.test_method(method_name)
            self.results[method_name] = result
            
            # Brief pause between tests
            await asyncio.sleep(2)
        
        # Generate report
        self._generate_report()
        
        return self.results
    
    def _generate_report(self):
        """Generate discovery report"""
        logger.info("\n" + "="*80)
        logger.info("📊 INJECTIVE LISTEN METHODS DISCOVERY REPORT")
        logger.info("="*80)
        
        successful_methods = [r for r in self.results.values() if r.success]
        failed_methods = [r for r in self.results.values() if not r.success]
        
        logger.info(f"✅ Successful methods: {len(successful_methods)}")
        logger.info(f"❌ Failed methods: {len(failed_methods)}")
        
        if successful_methods:
            logger.info("\n🏆 TOP PERFORMING METHODS:")
            # Sort by message rate
            top_methods = sorted(successful_methods, key=lambda x: x.message_rate, reverse=True)
            
            for i, result in enumerate(top_methods[:10], 1):
                logger.info(f"  {i}. {result.method_name}")
                logger.info(f"     💬 {result.message_count} messages ({result.message_rate:.2f} msg/s)")
                logger.info(f"     🏪 {len(result.markets_with_data)} markets with data")
                logger.info(f"     📊 Data types: {', '.join(result.data_types_seen)}")
        
        if failed_methods:
            logger.info("\n❌ FAILED METHODS:")
            for result in failed_methods:
                logger.info(f"  • {result.method_name}: {result.error}")
        
        logger.info("\n🎯 RECOMMENDATIONS:")
        if successful_methods:
            best_method = max(successful_methods, key=lambda x: x.message_rate)
            logger.info(f"  🥇 Best overall: {best_method.method_name} ({best_method.message_rate:.2f} msg/s)")
            
            # Find methods that support multiple markets
            multi_market_methods = [r for r in successful_methods if len(r.markets_with_data) > 1]
            if multi_market_methods:
                best_multi = max(multi_market_methods, key=lambda x: x.message_rate)
                logger.info(f"  🏪 Best multi-market: {best_multi.method_name} ({len(best_multi.markets_with_data)} markets)")
        
        logger.info("="*80)

async def main():
    """Main discovery function"""
    discovery = MethodDiscovery()
    results = await discovery.run_discovery()
    
    # Save results to file for analysis
    import json
    report_data = {}
    for method_name, result in results.items():
        report_data[method_name] = {
            'success': result.success,
            'message_count': result.message_count,
            'message_rate': result.message_rate,
            'markets_with_data': list(result.markets_with_data),
            'data_types_seen': list(result.data_types_seen),
            'error': result.error
        }
    
    with open('injective_methods_discovery.json', 'w') as f:
        json.dump(report_data, f, indent=2)
    
    logger.info("\n💾 Results saved to injective_methods_discovery.json")

if __name__ == "__main__":
    asyncio.run(main())
