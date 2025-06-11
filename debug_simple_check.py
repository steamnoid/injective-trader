#!/usr/bin/env python3
"""
Simple debug check to isolate the issue
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from injective_bot.connection import ConnectionState, MessageType, WebSocketMessage, MessageHandler
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.config import WebSocketConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleCollector(MessageHandler):
    def __init__(self):
        self.messages = []
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        self.messages.append(message)
        print(f"✅ Message #{len(self.messages)}: {message.message_type.value} for {message.market_id}")

async def test_simple_scenarios():
    """Test simple scenarios"""
    
    config = WebSocketConfig(connection_timeout=30.0)
    btc_usdt = "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"
    eth_usdt = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"
    
    print("\n=== TEST 1: Single Market Orderbook ===")
    client1 = InjectiveStreamClient(config=config, network="mainnet")
    collector1 = SimpleCollector()
    client1.register_handler(collector1)
    
    try:
        connected = await client1.connect()
        print(f"Connected: {connected}")
        
        if connected:
            await client1.subscribe_spot_orderbook_updates([btc_usdt])
            print("Subscribed to BTC-USDT orderbook")
            
            print("Waiting 10 seconds...")
            await asyncio.sleep(10)
            
            print(f"Messages received: {len(collector1.messages)}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client1.get_connection_state() == ConnectionState.CONNECTED:
            await client1.disconnect()
    
    print("\n=== TEST 2: Single Market Trades ===")
    client2 = InjectiveStreamClient(config=config, network="mainnet")
    collector2 = SimpleCollector()
    client2.register_handler(collector2)
    
    try:
        connected = await client2.connect()
        print(f"Connected: {connected}")
        
        if connected:
            await client2.subscribe_spot_trades_updates([btc_usdt])
            print("Subscribed to BTC-USDT trades")
            
            print("Waiting 10 seconds...")
            await asyncio.sleep(10)
            
            print(f"Messages received: {len(collector2.messages)}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client2.get_connection_state() == ConnectionState.CONNECTED:
            await client2.disconnect()
    
    print("\n=== TEST 3: Two Markets Orderbook ===")
    client3 = InjectiveStreamClient(config=config, network="mainnet")
    collector3 = SimpleCollector()
    client3.register_handler(collector3)
    
    try:
        connected = await client3.connect()
        print(f"Connected: {connected}")
        
        if connected:
            await client3.subscribe_spot_orderbook_updates([btc_usdt, eth_usdt])
            print("Subscribed to BTC-USDT + ETH-USDT orderbook")
            
            print("Waiting 10 seconds...")
            await asyncio.sleep(10)
            
            print(f"Messages received: {len(collector3.messages)}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if client3.get_connection_state() == ConnectionState.CONNECTED:
            await client3.disconnect()

if __name__ == "__main__":
    asyncio.run(test_simple_scenarios())
