#!/usr/bin/env python3
"""
Debug multiple market subscriptions to identify the issue
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

class SimpleDebugCollector(MessageHandler):
    def __init__(self):
        self.messages = []
        self.start_time = None
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
        self.messages.append(message)
        logger.info(f"📨 Message #{len(self.messages)}: {message.message_type.value} for {message.market_id}")

async def test_subscription_scenarios():
    """Test different subscription scenarios"""
    
    config = WebSocketConfig(connection_timeout=30.0)
    
    scenarios = [
        ("Single Market - Orderbook Only", ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"], ["orderbook"]),
        ("Single Market - Trades Only", ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"], ["trades"]),
        ("Single Market - Both", ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"], ["orderbook", "trades"]),
        ("Two Markets - Orderbook Only", [
            "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa",
            "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"
        ], ["orderbook"]),
        ("Two Markets - Both", [
            "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa",
            "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"
        ], ["orderbook", "trades"]),
    ]
    
    for scenario_name, markets, subscription_types in scenarios:
        logger.info(f"\n🧪 Testing: {scenario_name}")
        logger.info(f"   Markets: {len(markets)}")
        logger.info(f"   Subscriptions: {subscription_types}")
        
        client = InjectiveStreamClient(config=config, network="mainnet")
        collector = SimpleDebugCollector()
        client.register_handler(collector)
        
        try:
            # Connect
            connected = await client.connect()
            if not connected:
                logger.error(f"❌ Failed to connect for {scenario_name}")
                continue
                
            logger.info(f"✅ Connected for {scenario_name}")
            
            # Subscribe based on scenario
            if "orderbook" in subscription_types:
                await client.subscribe_spot_orderbook_updates(markets)
                logger.info(f"📊 Subscribed to orderbook for {len(markets)} markets")
                
            if "trades" in subscription_types:
                await client.subscribe_spot_trades_updates(markets)
                logger.info(f"💱 Subscribed to trades for {len(markets)} markets")
            
            # Wait for data
            logger.info(f"⏰ Waiting 15 seconds for data...")
            await asyncio.sleep(15)
            
            # Results
            message_count = len(collector.messages)
            logger.info(f"📊 RESULT: {message_count} messages received")
            
            if message_count > 0:
                markets_seen = set()
                message_types = set()
                for msg in collector.messages:
                    if msg.market_id:
                        markets_seen.add(msg.market_id)
                    message_types.add(msg.message_type)
                
                logger.info(f"   Markets with data: {len(markets_seen)}/{len(markets)}")
                logger.info(f"   Message types: {[mt.value for mt in message_types]}")
                logger.info(f"   Success rate: {message_count/15:.1f} msg/sec")
            else:
                logger.warning(f"❌ No messages received for {scenario_name}")
                
        except Exception as e:
            logger.error(f"❌ Error in {scenario_name}: {e}")
            
        finally:
            if client.get_connection_state() == ConnectionState.CONNECTED:
                await client.disconnect()
                
        logger.info(f"✅ Completed {scenario_name}")

if __name__ == "__main__":
    asyncio.run(test_subscription_scenarios())
