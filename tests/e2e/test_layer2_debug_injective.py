# Debug test for Layer 2 real Injective connection
"""
Debug test to understand why we're not receiving messages from real Injective Protocol
"""

import pytest
import asyncio
import logging
from datetime import datetime, timezone

from injective_bot.connection import (
    ConnectionState, MessageType, WebSocketMessage, MessageHandler,
    ConnectionError, ReconnectionError, RateLimitError
)
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.config import WebSocketConfig
from pyinjective import AsyncClient
from pyinjective.core.network import Network

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DebugMessageCollector(MessageHandler):
    """Debug message collector with detailed logging"""
    
    def __init__(self):
        self.messages = []
        self.callback_count = 0
        
    def get_supported_message_types(self):
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        """Handle message with debug logging"""
        logger.info(f"RECEIVED MESSAGE: {message.message_type.value} for {message.market_id}")
        self.messages.append(message)


class TestLayer2DebugInjective:
    """Debug tests for Layer 2 real Injective connection"""
    
    @pytest.mark.asyncio
    async def test_debug_available_markets(self):
        """Debug test to see what markets are available"""
        logger.info("Starting market discovery test...")
        
        # Test both testnet and mainnet
        networks = [
            ("testnet", Network.testnet()),
            ("mainnet", Network.mainnet())
        ]
        
        for network_name, network_config in networks:
            logger.info(f"\n=== Testing {network_name} ===")
            
            try:
                client = AsyncClient(network_config)
                
                # Get available markets
                logger.info(f"Getting spot markets for {network_name}...")
                spot_markets = await client.fetch_spot_markets()
                
                # Handle response format - it might be a dict
                if hasattr(spot_markets, 'markets'):
                    markets = spot_markets.markets
                elif isinstance(spot_markets, dict) and 'markets' in spot_markets:
                    markets = spot_markets['markets']
                elif isinstance(spot_markets, dict) and 'market' in spot_markets:
                    markets = spot_markets['market']
                else:
                    logger.info(f"Spot markets response structure: {type(spot_markets)}")
                    if isinstance(spot_markets, dict):
                        logger.info(f"Keys: {list(spot_markets.keys())}")
                    markets = []
                
                logger.info(f"Found {len(markets)} spot markets on {network_name}")
                
                # Show first few markets
                for i, market in enumerate(markets[:5]):
                    if hasattr(market, 'ticker'):
                        logger.info(f"  {i+1}. {market.ticker} - ID: {market.market_id}")
                        logger.info(f"      Base: {market.base_token.symbol}, Quote: {market.quote_token.symbol}")
                    elif isinstance(market, dict):
                        logger.info(f"  {i+1}. {market.get('ticker', 'N/A')} - ID: {market.get('market_id', 'N/A')}")
                
                # Find INJ/USDT specifically
                inj_usdt_markets = []
                for market in markets:
                    ticker = market.ticker if hasattr(market, 'ticker') else market.get('ticker', '')
                    if "INJ" in ticker and "USDT" in ticker:
                        inj_usdt_markets.append(market)
                        
                if inj_usdt_markets:
                    market = inj_usdt_markets[0]
                    market_id = market.market_id if hasattr(market, 'market_id') else market.get('market_id')
                    ticker = market.ticker if hasattr(market, 'ticker') else market.get('ticker')
                    logger.info(f"Found INJ/USDT market: {ticker} - ID: {market_id}")
                else:
                    logger.warning(f"No INJ/USDT market found on {network_name}")
                    
            except Exception as e:
                logger.error(f"Error accessing {network_name}: {e}")
    
    @pytest.mark.asyncio
    async def test_debug_simple_connection(self):
        """Debug test for simple connection to mainnet"""
        logger.info("Starting simple connection test...")
        
        config = WebSocketConfig(
            max_reconnect_attempts=1,
            connection_timeout=30.0,
            ping_interval=30.0,
            max_message_rate=1000
        )
        
        client = InjectiveStreamClient(config=config, network="mainnet")
        collector = DebugMessageCollector()
        client.register_handler(collector)
        
        try:
            # Connect
            logger.info("Attempting to connect to mainnet...")
            result = await asyncio.wait_for(client.connect(), timeout=30.0)
            
            if not result:
                logger.error("Failed to connect")
                return
                
            logger.info("Connected successfully!")
            logger.info(f"Connection state: {client.get_connection_state()}")
            
            # Get a real market ID
            spot_markets = await raw_client.fetch_spot_markets()
            
            # Handle response format
            if hasattr(spot_markets, 'markets'):
                markets = spot_markets.markets
            elif isinstance(spot_markets, dict) and 'markets' in spot_markets:
                markets = spot_markets['markets']
            elif isinstance(spot_markets, dict) and 'market' in spot_markets:
                markets = spot_markets['market']
            else:
                logger.error(f"Unexpected spot markets format: {type(spot_markets)}")
                return
            
            # Find a high-activity market
            inj_usdt_markets = []
            for market in markets:
                ticker = market.ticker if hasattr(market, 'ticker') else market.get('ticker', '')
                if "INJ" in ticker and "USDT" in ticker:
                    inj_usdt_markets.append(market)
                    
            if not inj_usdt_markets:
                logger.error("No INJ/USDT market found")
                return
            
            market = inj_usdt_markets[0]
            market_id = market.market_id if hasattr(market, 'market_id') else market.get('market_id')
            ticker = market.ticker if hasattr(market, 'ticker') else market.get('ticker')
            logger.info(f"Using market: {ticker} - ID: {market_id}")
            
            # Subscribe to orderbook with debug logging
            logger.info("Subscribing to orderbook updates...")
            await client.subscribe_spot_orderbook_updates([market_id])
            
            logger.info("Subscribing to trade updates...")
            await client.subscribe_spot_trades_updates([market_id])
            
            # Wait and see if we get any messages
            logger.info("Waiting 30 seconds for messages...")
            await asyncio.sleep(30)
            
            logger.info(f"Received {len(collector.messages)} messages")
            
            if collector.messages:
                for msg in collector.messages[:3]:  # Show first 3 messages
                    logger.info(f"Message: {msg.message_type.value} - {msg.market_id}")
            else:
                logger.warning("No messages received - debugging subscription...")
                
                # Check if subscriptions are active
                metrics = client.get_metrics()
                logger.info(f"Metrics: {metrics}")
                
                # Check active subscriptions
                logger.info(f"Active subscriptions: {client._active_subscriptions}")
                logger.info(f"Subscription tasks: {list(client._subscription_tasks.keys())}")
                
        except Exception as e:
            logger.error(f"Error in debug test: {e}")
            raise
        finally:
            if client.get_connection_state() == ConnectionState.CONNECTED:
                await client.disconnect()
    
    @pytest.mark.asyncio 
    async def test_debug_direct_injective_streaming(self):
        """Debug test using injective-py directly"""
        logger.info("Testing direct injective-py streaming...")
        
        class DirectCallback:
            def __init__(self):
                self.call_count = 0
                
            def __call__(self, data):
                self.call_count += 1
                logger.info(f"DIRECT CALLBACK #{self.call_count}: {type(data)}")
                if hasattr(data, 'orderbook'):
                    logger.info(f"  Orderbook data received")
                if hasattr(data, 'trade'):
                    logger.info(f"  Trade data received")
        
        try:
            client = AsyncClient(Network.mainnet())
            callback = DirectCallback()
            
            # Get a real market ID
            spot_markets = await client.fetch_spot_markets()
            inj_usdt_markets = [m for m in spot_markets.markets if "INJ" in m.ticker and "USDT" in m.ticker]
            
            if not inj_usdt_markets:
                logger.error("No INJ/USDT market found")
                return
                
            market_id = inj_usdt_markets[0].market_id
            logger.info(f"Using market ID: {market_id}")
            
            # Test direct subscription
            logger.info("Starting direct orderbook subscription...")
            task = asyncio.create_task(
                client.listen_spot_orderbook_updates(
                    market_ids=[market_id],
                    callback=callback
                )
            )
            
            # Wait a bit
            logger.info("Waiting 30 seconds for direct callbacks...")
            await asyncio.sleep(30)
            
            logger.info(f"Direct callback was called {callback.call_count} times")
            
            # Cancel the task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"Error in direct test: {e}")
            raise
