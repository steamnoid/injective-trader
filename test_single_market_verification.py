#!/usr/bin/env python3
"""
Test single market to verify our connection and data flow work correctly
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from src.injective_bot.connection import ConnectionState, MessageType, WebSocketMessage, MessageHandler
from src.injective_bot.connection.injective_client import InjectiveStreamClient
from src.injective_bot.config import WebSocketConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SingleMarketCollector(MessageHandler):
    def __init__(self):
        self.messages = []
        self.orderbook_count = 0
        self.trades_count = 0
        self.start_time = None
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
        self.messages.append(message)
        
        if message.message_type == MessageType.ORDERBOOK:
            self.orderbook_count += 1
        elif message.message_type == MessageType.TRADES:
            self.trades_count += 1
            
        logger.info(f"📨 Message #{len(self.messages)}: {message.message_type.value} for market {message.market_id}")

async def test_single_market():
    """Test single market subscription to verify basic functionality"""
    
    config = WebSocketConfig(connection_timeout=30.0)
    
    # Test with the most active market - BTC/USDT
    btc_market = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"
    
    client = InjectiveStreamClient(config=config, network="mainnet")
    collector = SingleMarketCollector()
    client.register_handler(collector)
    
    try:
        # Connect
        logger.info("🔌 Connecting to Injective Protocol...")
        connected = await client.connect()
        if not connected:
            logger.error("❌ Failed to connect")
            return False
            
        logger.info("✅ Connected successfully")
        
        # Test single market subscription
        logger.info(f"📊 Subscribing to orderbook updates for BTC/USDT...")
        await client.subscribe_spot_orderbook_updates([btc_market])
        
        logger.info(f"💱 Subscribing to trades updates for BTC/USDT...")
        await client.subscribe_spot_trades_updates([btc_market])
        
        # Wait for data
        logger.info("⏰ Waiting 15 seconds for data...")
        await asyncio.sleep(15)
        
        # Results
        message_count = len(collector.messages)
        
        logger.info(f"\n📈 SINGLE MARKET RESULTS:")
        logger.info(f"   Total messages: {message_count}")
        logger.info(f"   Orderbook messages: {collector.orderbook_count}")
        logger.info(f"   Trade messages: {collector.trades_count}")
        logger.info(f"   Message rate: {message_count/15:.1f} msg/sec")
        
        if message_count > 0:
            logger.info("🎉 SUCCESS: Single market subscription works!")
            return True
        else:
            logger.error("❌ FAILURE: No messages received from single market")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        if client.get_connection_state() == ConnectionState.CONNECTED:
            await client.disconnect()
            logger.info("🔌 Disconnected")

if __name__ == "__main__":
    result = asyncio.run(test_single_market())
    print(f"\n🏁 Single market test result: {'PASS' if result else 'FAIL'}")
