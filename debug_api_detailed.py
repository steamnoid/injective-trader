#!/usr/bin/env python3
"""
Debug the actual API calls and responses to understand the multiple market issue
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from src.injective_bot.connection import ConnectionState, MessageType, WebSocketMessage, MessageHandler
from src.injective_bot.connection.injective_client import InjectiveStreamClient
from src.injective_bot.config import WebSocketConfig

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also enable injective-py logging
logging.getLogger('pyinjective').setLevel(logging.DEBUG)

class DetailedCollector(MessageHandler):
    def __init__(self):
        self.messages = []
        self.markets_seen = set()
        self.start_time = None
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
        self.messages.append(message)
        if message.market_id:
            self.markets_seen.add(message.market_id)
        logger.info(f"📨 Message #{len(self.messages)}: {message.message_type.value} for {message.market_id}")
        
        # Log a sample of the data structure
        if len(self.messages) <= 3:
            logger.debug(f"Message data keys: {list(message.data.keys()) if hasattr(message.data, 'keys') else 'Not a dict'}")

async def debug_api_calls():
    """Debug the actual API calls to understand what's happening"""
    
    config = WebSocketConfig(connection_timeout=30.0)
    
    # Start with just 1 market to establish baseline
    single_market = ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"]
    two_markets = [
        "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa",
        "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"
    ]
    
    logger.info("=== TESTING SINGLE MARKET FIRST ===")
    
    client = InjectiveStreamClient(config=config, network="mainnet")
    collector = DetailedCollector()
    client.register_handler(collector)
    
    try:
        # Connect
        logger.info("🔌 Connecting to Injective Protocol...")
        connected = await client.connect()
        if not connected:
            logger.error("❌ Failed to connect")
            return
            
        logger.info("✅ Connected successfully")
        
        # Test single market first
        logger.info("📊 Testing single market orderbook subscription...")
        await client.subscribe_spot_orderbook_updates(single_market)
        
        logger.info("⏰ Waiting 10 seconds for single market data...")
        await asyncio.sleep(10)
        
        single_market_messages = len(collector.messages)
        logger.info(f"Single market result: {single_market_messages} messages")
        
        if single_market_messages == 0:
            logger.error("❌ Even single market is not working - fundamental issue")
            return
        
        # Reset collector
        collector.messages.clear()
        collector.markets_seen.clear()
        
        # Now test two markets
        logger.info("\n=== TESTING TWO MARKETS ===")
        logger.info("📊 Testing two market orderbook subscription...")
        await client.subscribe_spot_orderbook_updates(two_markets)
        
        logger.info("⏰ Waiting 15 seconds for two market data...")
        await asyncio.sleep(15)
        
        two_market_messages = len(collector.messages)
        markets_with_data = len(collector.markets_seen)
        
        logger.info(f"Two market result: {two_market_messages} messages from {markets_with_data} markets")
        logger.info(f"Markets seen: {list(collector.markets_seen)}")
        
        # Analysis
        if two_market_messages > 0:
            logger.info("🎉 Multiple market subscription IS working!")
            if markets_with_data >= 2:
                logger.info("✅ Both markets are sending data")
            else:
                logger.warning("⚠️ Only one market is active")
        else:
            logger.error("❌ Multiple market subscription failed completely")
            
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
        
    finally:
        if client.get_connection_state() == ConnectionState.CONNECTED:
            await client.disconnect()
            logger.info("🔌 Disconnected")

if __name__ == "__main__":
    asyncio.run(debug_api_calls())
