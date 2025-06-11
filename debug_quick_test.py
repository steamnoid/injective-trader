#!/usr/bin/env python3
"""
Simple test to verify what subscription patterns work
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

class QuickCollector(MessageHandler):
    def __init__(self):
        self.count = 0
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        self.count += 1
        logger.info(f"✅ Message {self.count}: {message.message_type.value} - {message.market_id}")

async def quick_test():
    """Quick test of what we know works vs what doesn't"""
    
    config = WebSocketConfig(connection_timeout=30.0)
    
    logger.info("🧪 QUICK TEST: Known Working Pattern")
    
    client = InjectiveStreamClient(config=config, network="mainnet")
    collector = QuickCollector()
    client.register_handler(collector)
    
    try:
        # Connect
        logger.info("🔗 Connecting...")
        connected = await client.connect()
        if not connected:
            logger.error("❌ Connection failed")
            return
            
        logger.info("✅ Connected")
        
        # Test the exact pattern we know works (from successful single market test)
        single_market = ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"]
        
        logger.info("📊 Subscribing to orderbook updates...")
        await client.subscribe_spot_orderbook_updates(single_market)
        
        logger.info("💱 Subscribing to trade updates...")
        await client.subscribe_spot_trades_updates(single_market)
        
        logger.info("⏰ Waiting 10 seconds...")
        await asyncio.sleep(10)
        
        logger.info(f"📊 RESULT: {collector.count} messages received")
        
        if collector.count > 0:
            logger.info("✅ SUCCESS - Single market with both subscriptions works")
        else:
            logger.error("❌ FAILURE - Even known working pattern failed")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        
    finally:
        if client.get_connection_state() == ConnectionState.CONNECTED:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(quick_test())
