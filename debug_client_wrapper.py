#!/usr/bin/env python3
"""
Test our InjectiveStreamClient with debugging to find the callback issue
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from injective_bot.connection import ConnectionState, MessageType, WebSocketMessage, MessageHandler
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.config import WebSocketConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DebugMessageCollector(MessageHandler):
    """Debug message collector with detailed logging"""
    
    def __init__(self):
        self.messages = []
        self.callback_count = 0
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        self.callback_count += 1
        self.messages.append(message)
        logger.info(f"🎉 HANDLER RECEIVED MESSAGE #{self.callback_count}: {message.message_type.value} for {message.market_id}")

async def test_debug_injective_client():
    """Test with detailed debugging"""
    
    # Create client
    config = WebSocketConfig(
        max_reconnect_attempts=3,
        reconnect_delay_base=1.0,
        connection_timeout=30.0
    )
    
    client = InjectiveStreamClient(config=config, network="mainnet")
    collector = DebugMessageCollector()
    
    try:
        # Register handler
        logger.info("🔧 Registering message handler...")
        client.register_handler(collector)
        
        # Connect
        logger.info("🔗 Connecting to mainnet...")
        connected = await client.connect()
        
        if not connected:
            logger.error("❌ Failed to connect")
            return 0
            
        logger.info("✅ Connected successfully")
        
        # Add debug patch to the client to see callback activity
        original_callback = None
        callback_count = 0
        
        def debug_callback_wrapper(original_callback_func):
            def wrapped_callback(data):
                nonlocal callback_count
                callback_count += 1
                logger.info(f"🔥 RAW CALLBACK #{callback_count}: {type(data)} - {list(data.keys()) if hasattr(data, 'keys') else 'no keys'}")
                
                # Call original callback
                try:
                    result = original_callback_func(data)
                    logger.info(f"✅ Original callback executed successfully")
                    return result
                except Exception as e:
                    logger.error(f"❌ Error in original callback: {e}")
                    raise
                    
            return wrapped_callback
        
        # Patch the subscription method to wrap callbacks
        original_subscribe = client.subscribe_spot_orderbook_updates
        
        async def debug_subscribe(market_ids):
            logger.info(f"🎯 DEBUG: Subscribing to {market_ids}")
            return await original_subscribe(market_ids)
        
        client.subscribe_spot_orderbook_updates = debug_subscribe
        
        # Subscribe to markets
        market_ids = ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"]
        logger.info(f"📡 Subscribing to markets: {market_ids}")
        
        await client.subscribe_spot_orderbook_updates(market_ids)
        
        # Wait and monitor
        logger.info("⏰ Waiting 15 seconds for messages...")
        
        for i in range(15):
            await asyncio.sleep(1)
            logger.info(f"⏳ {i+1}s - Callbacks: {callback_count}, Handler messages: {collector.callback_count}")
            
        logger.info("🏁 Test complete")
        
        # Results
        logger.info(f"📊 RESULTS:")
        logger.info(f"  Raw callbacks received: {callback_count}")
        logger.info(f"  Handler messages received: {collector.callback_count}")
        logger.info(f"  Connection state: {client.get_connection_state()}")
        
        return collector.callback_count
        
    except Exception as e:
        logger.error(f"❌ Test error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0
        
    finally:
        if client.get_connection_state() == ConnectionState.CONNECTED:
            await client.disconnect()

if __name__ == "__main__":
    result = asyncio.run(test_debug_injective_client())
    print(f"\nFinal handler message count: {result}")
