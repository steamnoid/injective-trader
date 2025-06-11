#!/usr/bin/env python3
"""
Minimal test to debug multiple market subscription issue.
This script uses the exact pattern from official injective-py examples.
"""

import asyncio
import logging
from typing import List
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Market IDs to test
MARKET_IDS = [
    "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce",  # BTC/USDT
    "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034",  # WETH/USDT
]

class MinimalSubscriptionTest:
    def __init__(self):
        self.message_count = 0
        self.market_data = {}
    
    def orderbook_event_processor(self, event):
        """Callback function to process orderbook events - matches official examples"""
        try:
            self.message_count += 1
            
            # Log the event structure to understand what we're receiving
            if hasattr(event, 'orderbook') and event.orderbook:
                market_id = event.orderbook.market_id
                if market_id not in self.market_data:
                    self.market_data[market_id] = 0
                self.market_data[market_id] += 1
                
                logger.info(f"Message #{self.message_count} - Market: {market_id[:8]}...")
                logger.info(f"Market data counts: {self.market_data}")
            else:
                logger.warning(f"Message #{self.message_count} - Unexpected event structure: {type(event)}")
                
        except Exception as e:
            logger.error(f"Error processing orderbook event: {e}")
    
    async def test_single_market(self):
        """Test single market subscription - this should work"""
        logger.info("=== Testing Single Market Subscription ===")
        
        network = Network.mainnet()
        client = AsyncClient(network)
        
        self.message_count = 0
        self.market_data = {}
        
        try:
            # Test with just the first market
            single_market = [MARKET_IDS[0]]
            logger.info(f"Subscribing to single market: {single_market[0][:8]}...")
            
            # Start subscription
            task = asyncio.create_task(
                client.listen_spot_orderbook_updates(
                    market_ids=single_market,
                    callback=self.orderbook_event_processor
                )
            )
            
            # Wait for messages
            await asyncio.sleep(10)
            task.cancel()
            
            logger.info(f"Single market test result: {self.message_count} messages received")
            logger.info(f"Market data: {self.market_data}")
            
        except Exception as e:
            logger.error(f"Single market test failed: {e}")
        finally:
            await client.close_client()
    
    async def test_multiple_markets(self):
        """Test multiple market subscription - this is failing"""
        logger.info("=== Testing Multiple Market Subscription ===")
        
        network = Network.mainnet()
        client = AsyncClient(network)
        
        self.message_count = 0
        self.market_data = {}
        
        try:
            logger.info(f"Subscribing to {len(MARKET_IDS)} markets:")
            for i, market_id in enumerate(MARKET_IDS):
                logger.info(f"  {i+1}. {market_id[:8]}...")
            
            # Start subscription - using exact same pattern as official examples
            task = asyncio.create_task(
                client.listen_spot_orderbook_updates(
                    market_ids=MARKET_IDS,
                    callback=self.orderbook_event_processor
                )
            )
            
            # Wait for messages
            await asyncio.sleep(10)
            task.cancel()
            
            logger.info(f"Multiple market test result: {self.message_count} messages received")
            logger.info(f"Market data: {self.market_data}")
            
            # Check if all markets received data
            active_markets = len(self.market_data)
            total_markets = len(MARKET_IDS)
            coverage = (active_markets / total_markets) * 100 if total_markets > 0 else 0
            
            logger.info(f"Market coverage: {coverage:.1f}% ({active_markets}/{total_markets})")
            
        except Exception as e:
            logger.error(f"Multiple market test failed: {e}")
        finally:
            await client.close_client()
    
    async def test_official_example_markets(self):
        """Test with the exact market IDs from official examples"""
        logger.info("=== Testing Official Example Markets ===")
        
        # These are from the official GitHub examples
        official_markets = [
            "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # From example
            "0x7a57e705bb4e09c88aecfc295569481dbf2fe1d5efe364651fbe72385938e9b0",  # From example
        ]
        
        network = Network.mainnet()
        client = AsyncClient(network)
        
        self.message_count = 0
        self.market_data = {}
        
        try:
            logger.info(f"Testing with official example markets:")
            for i, market_id in enumerate(official_markets):
                logger.info(f"  {i+1}. {market_id[:8]}...")
            
            # Start subscription
            task = asyncio.create_task(
                client.listen_spot_orderbook_updates(
                    market_ids=official_markets,
                    callback=self.orderbook_event_processor
                )
            )
            
            # Wait for messages
            await asyncio.sleep(10)
            task.cancel()
            
            logger.info(f"Official markets test result: {self.message_count} messages received")
            logger.info(f"Market data: {self.market_data}")
            
        except Exception as e:
            logger.error(f"Official markets test failed: {e}")
        finally:
            await client.close_client()

async def main():
    """Run all tests"""
    tester = MinimalSubscriptionTest()
    
    # Test 1: Single market (should work)
    await tester.test_single_market()
    await asyncio.sleep(2)
    
    # Test 2: Multiple markets (currently failing)
    await tester.test_multiple_markets()
    await asyncio.sleep(2)
    
    # Test 3: Official example markets
    await tester.test_official_example_markets()

if __name__ == "__main__":
    asyncio.run(main())
