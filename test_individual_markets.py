#!/usr/bin/env python3
"""
Individual Market Testing Script
Test BTC and ETH markets separately to validate individual market functionality
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.connection import WebSocketMessage, MessageType, MessageHandler
from injective_bot.config import WebSocketConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('individual_market_test.log')
    ]
)
logger = logging.getLogger(__name__)

class SingleMarketCollector(MessageHandler):
    """Message collector for individual market testing"""
    
    def __init__(self, market_name: str):
        self.market_name = market_name
        self.messages = []
        self.markets_seen = set()
        self.start_time = None
        self.orderbook_messages = 0
        self.trade_messages = 0
        
    def get_supported_message_types(self) -> List[MessageType]:
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
            
        self.messages.append(message)
        
        if message.market_id:
            self.markets_seen.add(message.market_id)
            
        # Count message types
        if message.message_type == MessageType.ORDERBOOK:
            self.orderbook_messages += 1
        elif message.message_type == MessageType.TRADES:
            self.trade_messages += 1
            
        logger.info(f"📨 {self.market_name} Message #{len(self.messages)}: {message.message_type.value} for {message.market_id}")

async def test_btc_market():
    """Test BTC market individually"""
    logger.info("\n" + "="*80)
    logger.info("🚀 TESTING BTC MARKET INDIVIDUALLY")
    logger.info("="*80)
    
    config = WebSocketConfig(connection_timeout=30.0)
    
    # BTC/USDT market ID
    btc_market_id = "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce"
    
    client = InjectiveStreamClient(config=config, network="mainnet")
    collector = SingleMarketCollector("BTC")
    client.register_handler(collector)
    
    try:
        # Connect
        logger.info("🔌 Connecting to Injective Protocol...")
        connected = await client.connect()
        if not connected:
            logger.error("❌ Failed to connect")
            return False
            
        logger.info("✅ Connected successfully")
        
        # Subscribe to BTC market only
        logger.info(f"📊 Subscribing to BTC orderbook updates...")
        await client.subscribe_spot_orderbook_updates([btc_market_id])
        
        logger.info(f"💱 Subscribing to BTC trades updates...")
        await client.subscribe_spot_trades_updates([btc_market_id])
        
        # Wait for data
        logger.info("⏰ Waiting 15 seconds for BTC data...")
        await asyncio.sleep(15)
        
        # Results
        message_count = len(collector.messages)
        markets_with_data = len(collector.markets_seen)
        
        logger.info(f"\n📈 BTC MARKET RESULTS:")
        logger.info(f"   📨 Total messages: {message_count}")
        logger.info(f"   📊 Orderbook messages: {collector.orderbook_messages}")
        logger.info(f"   💱 Trade messages: {collector.trade_messages}")
        logger.info(f"   🏪 Markets with data: {markets_with_data}")
        logger.info(f"   🎯 Expected market: {btc_market_id}")
        logger.info(f"   📋 Markets seen: {list(collector.markets_seen)}")
        
        # Validation
        success = message_count > 0 and markets_with_data > 0
        if success:
            logger.info("✅ BTC MARKET TEST: PASSED")
        else:
            logger.error("❌ BTC MARKET TEST: FAILED")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ BTC test error: {e}")
        return False
        
    finally:
        try:
            await client.disconnect()
            logger.info("🔌 Disconnected from BTC test")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

async def test_eth_market():
    """Test ETH market individually"""
    logger.info("\n" + "="*80)
    logger.info("🚀 TESTING ETH MARKET INDIVIDUALLY")
    logger.info("="*80)
    
    config = WebSocketConfig(connection_timeout=30.0)
    
    # WETH/USDT market ID
    eth_market_id = "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034"
    
    client = InjectiveStreamClient(config=config, network="mainnet")
    collector = SingleMarketCollector("ETH")
    client.register_handler(collector)
    
    try:
        # Connect
        logger.info("🔌 Connecting to Injective Protocol...")
        connected = await client.connect()
        if not connected:
            logger.error("❌ Failed to connect")
            return False
            
        logger.info("✅ Connected successfully")
        
        # Subscribe to ETH market only
        logger.info(f"📊 Subscribing to ETH orderbook updates...")
        await client.subscribe_spot_orderbook_updates([eth_market_id])
        
        logger.info(f"💱 Subscribing to ETH trades updates...")
        await client.subscribe_spot_trades_updates([eth_market_id])
        
        # Wait for data
        logger.info("⏰ Waiting 15 seconds for ETH data...")
        await asyncio.sleep(15)
        
        # Results
        message_count = len(collector.messages)
        markets_with_data = len(collector.markets_seen)
        
        logger.info(f"\n📈 ETH MARKET RESULTS:")
        logger.info(f"   📨 Total messages: {message_count}")
        logger.info(f"   📊 Orderbook messages: {collector.orderbook_messages}")
        logger.info(f"   💱 Trade messages: {collector.trade_messages}")
        logger.info(f"   🏪 Markets with data: {markets_with_data}")
        logger.info(f"   🎯 Expected market: {eth_market_id}")
        logger.info(f"   📋 Markets seen: {list(collector.markets_seen)}")
        
        # Validation
        success = message_count > 0 and markets_with_data > 0
        if success:
            logger.info("✅ ETH MARKET TEST: PASSED")
        else:
            logger.error("❌ ETH MARKET TEST: FAILED")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ ETH test error: {e}")
        return False
        
    finally:
        try:
            await client.disconnect()
            logger.info("🔌 Disconnected from ETH test")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

async def test_both_markets_combined():
    """Test both markets together after individual validation"""
    logger.info("\n" + "="*80)
    logger.info("🚀 TESTING BTC + ETH MARKETS COMBINED")
    logger.info("="*80)
    
    config = WebSocketConfig(connection_timeout=30.0)
    
    # Both market IDs
    test_markets = [
        "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce",  # BTC/USDT
        "0xd1956e20d74eeb1febe31cd37060781ff1cb266f49e0512b446a5fafa9a16034",  # WETH/USDT
    ]
    
    client = InjectiveStreamClient(config=config, network="mainnet")
    collector = SingleMarketCollector("BTC+ETH")
    client.register_handler(collector)
    
    try:
        # Connect
        logger.info("🔌 Connecting to Injective Protocol...")
        connected = await client.connect()
        if not connected:
            logger.error("❌ Failed to connect")
            return False
            
        logger.info("✅ Connected successfully")
        
        # Subscribe to both markets
        logger.info(f"📊 Subscribing to orderbook updates for {len(test_markets)} markets...")
        await client.subscribe_spot_orderbook_updates(test_markets)
        
        logger.info(f"💱 Subscribing to trades updates for {len(test_markets)} markets...")
        await client.subscribe_spot_trades_updates(test_markets)
        
        # Wait for data
        logger.info("⏰ Waiting 20 seconds for combined data...")
        await asyncio.sleep(20)
        
        # Results
        message_count = len(collector.messages)
        markets_with_data = len(collector.markets_seen)
        
        logger.info(f"\n📈 COMBINED MARKETS RESULTS:")
        logger.info(f"   📨 Total messages: {message_count}")
        logger.info(f"   📊 Orderbook messages: {collector.orderbook_messages}")
        logger.info(f"   💱 Trade messages: {collector.trade_messages}")
        logger.info(f"   🏪 Markets with data: {markets_with_data}")
        logger.info(f"   🎯 Expected markets: {len(test_markets)}")
        logger.info(f"   📋 Markets seen: {list(collector.markets_seen)}")
        
        # Calculate coverage
        coverage_percentage = (markets_with_data / len(test_markets)) * 100
        logger.info(f"   📊 Market coverage: {coverage_percentage:.1f}%")
        
        # Validation
        success = message_count > 0 and markets_with_data == len(test_markets)
        if success:
            logger.info("✅ COMBINED MARKETS TEST: PASSED")
        else:
            logger.error("❌ COMBINED MARKETS TEST: FAILED")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Combined test error: {e}")
        return False
        
    finally:
        try:
            await client.disconnect()
            logger.info("🔌 Disconnected from combined test")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

async def main():
    """Run all individual market tests"""
    logger.info("🎯 INDIVIDUAL MARKET TESTING SUITE")
    logger.info(f"📅 Started at: {datetime.now(timezone.utc)}")
    
    # Test results
    results = {
        'btc': False,
        'eth': False,
        'combined': False
    }
    
    # Test BTC individually
    logger.info("\n🔸 Step 1: Testing BTC market individually...")
    results['btc'] = await test_btc_market()
    
    # Wait between tests
    logger.info("\n⏳ Waiting 5 seconds before next test...")
    await asyncio.sleep(5)
    
    # Test ETH individually
    logger.info("\n🔸 Step 2: Testing ETH market individually...")
    results['eth'] = await test_eth_market()
    
    # Wait between tests
    logger.info("\n⏳ Waiting 5 seconds before combined test...")
    await asyncio.sleep(5)
    
    # Test both combined only if individual tests pass
    if results['btc'] and results['eth']:
        logger.info("\n🔸 Step 3: Testing combined markets...")
        results['combined'] = await test_both_markets_combined()
    else:
        logger.warning("\n⚠️ Skipping combined test due to individual test failures")
    
    # Final summary
    logger.info("\n" + "="*80)
    logger.info("📋 FINAL TEST SUMMARY")
    logger.info("="*80)
    logger.info(f"🪙 BTC Market Test: {'✅ PASSED' if results['btc'] else '❌ FAILED'}")
    logger.info(f"💎 ETH Market Test: {'✅ PASSED' if results['eth'] else '❌ FAILED'}")
    logger.info(f"🔗 Combined Test: {'✅ PASSED' if results['combined'] else '❌ FAILED (or skipped)'}")
    
    all_passed = all(results.values())
    logger.info(f"\n🎯 OVERALL RESULT: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        logger.info("🚀 Layer 2 multiple market subscription issue is RESOLVED!")
    else:
        logger.error("🔧 Further investigation needed for failing markets")
    
    return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        exit_code = 0 if result else 1
        print(f"\nExiting with code: {exit_code}")
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n🛑 Test interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"❌ Test suite error: {e}")
        exit(1)
