#!/usr/bin/env python3
"""
Detailed debug to understand subscription behavior
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List

from injective_bot.connection import ConnectionState, MessageType, WebSocketMessage, MessageHandler
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.config import WebSocketConfig

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DetailedCollector(MessageHandler):
    def __init__(self, name):
        self.name = name
        self.messages = []
        self.start_time = None
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
        self.messages.append(message)
        logger.info(f"[{self.name}] Message #{len(self.messages)}: {message.message_type.value} for {message.market_id}")
        logger.debug(f"[{self.name}] Data keys: {list(message.data.keys()) if hasattr(message.data, 'keys') else 'No keys'}")

async def detailed_debug():
    """Detailed debugging with step-by-step analysis"""
    
    config = WebSocketConfig(connection_timeout=30.0)
    btc_usdt = "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"
    eth_usdt = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"
    
    print("\n" + "="*60)
    print("DETAILED SUBSCRIPTION DEBUG")
    print("="*60)
    
    # Test 1: Single Market Orderbook (Known working)
    print("\n🧪 TEST 1: Single Market Orderbook (Reference)")
    client1 = InjectiveStreamClient(config=config, network="mainnet")
    collector1 = DetailedCollector("SingleOrderbook")
    client1.register_handler(collector1)
    
    try:
        await client1.connect()
        logger.info("Connected for single orderbook test")
        
        await client1.subscribe_spot_orderbook_updates([btc_usdt])
        logger.info("Subscribed to single market orderbook")
        
        await asyncio.sleep(8)
        print(f"✅ Result: {len(collector1.messages)} messages")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if client1.get_connection_state() == ConnectionState.CONNECTED:
            await client1.disconnect()
    
    # Test 2: Single Market Trades (Should work now)
    print("\n🧪 TEST 2: Single Market Trades")
    client2 = InjectiveStreamClient(config=config, network="mainnet")
    collector2 = DetailedCollector("SingleTrades")
    client2.register_handler(collector2)
    
    try:
        await client2.connect()
        logger.info("Connected for single trades test")
        
        await client2.subscribe_spot_trades_updates([btc_usdt])
        logger.info("Subscribed to single market trades")
        
        await asyncio.sleep(8)
        print(f"📊 Result: {len(collector2.messages)} messages")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if client2.get_connection_state() == ConnectionState.CONNECTED:
            await client2.disconnect()
    
    # Test 3: Two Markets Orderbook (Problematic)
    print("\n🧪 TEST 3: Two Markets Orderbook")
    client3 = InjectiveStreamClient(config=config, network="mainnet")
    collector3 = DetailedCollector("MultiOrderbook")
    client3.register_handler(collector3)
    
    try:
        await client3.connect()
        logger.info("Connected for multi orderbook test")
        
        # Check subscription tasks before
        logger.info(f"Active subscriptions before: {len(client3._active_subscriptions)}")
        logger.info(f"Subscription tasks before: {len(client3._subscription_tasks)}")
        
        await client3.subscribe_spot_orderbook_updates([btc_usdt, eth_usdt])
        logger.info("Subscribed to two markets orderbook")
        
        # Check subscription tasks after
        logger.info(f"Active subscriptions after: {len(client3._active_subscriptions)}")
        logger.info(f"Subscription tasks after: {len(client3._subscription_tasks)}")
        logger.info(f"Subscription IDs: {list(client3._active_subscriptions)}")
        
        await asyncio.sleep(8)
        print(f"📊 Result: {len(collector3.messages)} messages")
        
        if len(collector3.messages) == 0:
            logger.warning("No messages received - checking subscription task status")
            for sub_id, task in client3._subscription_tasks.items():
                logger.info(f"Task {sub_id}: done={task.done()}, cancelled={task.cancelled()}")
                if task.done():
                    try:
                        result = task.result()
                        logger.info(f"Task {sub_id} result: {result}")
                    except Exception as task_e:
                        logger.error(f"Task {sub_id} exception: {task_e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Full error details:")
    finally:
        if client3.get_connection_state() == ConnectionState.CONNECTED:
            await client3.disconnect()
    
    # Test 4: Sequential single market subscriptions 
    print("\n🧪 TEST 4: Sequential Single Market Subscriptions")
    client4 = InjectiveStreamClient(config=config, network="mainnet")
    collector4 = DetailedCollector("Sequential")
    client4.register_handler(collector4)
    
    try:
        await client4.connect()
        logger.info("Connected for sequential test")
        
        # Subscribe to first market
        await client4.subscribe_spot_orderbook_updates([btc_usdt])
        logger.info("Subscribed to BTC-USDT")
        await asyncio.sleep(3)
        
        # Subscribe to second market  
        await client4.subscribe_spot_orderbook_updates([eth_usdt])
        logger.info("Subscribed to ETH-USDT")
        await asyncio.sleep(5)
        
        print(f"📊 Result: {len(collector4.messages)} messages")
        
        # Check which markets we got data from
        markets_seen = set()
        for msg in collector4.messages:
            if msg.market_id:
                markets_seen.add(msg.market_id)
        logger.info(f"Markets with data: {markets_seen}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if client4.get_connection_state() == ConnectionState.CONNECTED:
            await client4.disconnect()

if __name__ == "__main__":
    asyncio.run(detailed_debug())
