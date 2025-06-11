#!/usr/bin/env python3
"""
Test with minimal setup to isolate the issue
"""

import asyncio
import logging
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_minimal_subscription():
    """Test minimal subscription setup"""
    try:
        # Use mainnet as per user preference
        logger.info("Creating mainnet client...")
        client = AsyncClient(Network.mainnet())
        
        # Known INJ/USDT market ID from mainnet (from our test)
        market_id = "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"
        
        logger.info(f"Testing with market ID: {market_id}")
        
        callback_count = 0
        
        def simple_callback(data):
            nonlocal callback_count
            callback_count += 1
            logger.info(f"CALLBACK #{callback_count}: {type(data)}")
            if isinstance(data, dict):
                logger.info(f"  Data keys: {list(data.keys())[:5]}")  # Show first 5 keys
            if callback_count >= 3:  # Stop after 3 callbacks
                logger.info("Got enough data, callback working!")
        
        logger.info("Starting orderbook subscription...")
        
        # Create subscription task
        task = asyncio.create_task(
            client.listen_spot_orderbook_updates(
                market_ids=[market_id],
                callback=simple_callback
            )
        )
        
        # Wait for 20 seconds
        logger.info("Waiting 20 seconds for callbacks...")
        await asyncio.sleep(20)
        
        logger.info("Cancelling subscription...")
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Task cancelled successfully")
        
        logger.info(f"Total callbacks received: {callback_count}")
        
        if callback_count == 0:
            logger.warning("❌ NO CALLBACKS RECEIVED - Something is wrong with the subscription")
        else:
            logger.info(f"✅ SUCCESS - Received {callback_count} callbacks")
            
        return callback_count
        
    except Exception as e:
        logger.error(f"Error in minimal test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0

if __name__ == "__main__":
    result = asyncio.run(test_minimal_subscription())
    print(f"\nFinal callback count: {result}")
