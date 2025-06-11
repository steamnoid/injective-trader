# Simple debug test for Layer 2 real Injective connection
"""
Simple debug test to understand injective-py API
"""

import pytest
import asyncio
import logging
from pyinjective import AsyncClient
from pyinjective.core.network import Network

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSimpleInjectiveDebug:
    """Simple debug tests for Injective connection"""
    
    @pytest.mark.asyncio
    async def test_simple_market_lookup(self):
        """Simple test to see market data structure"""
        logger.info("Testing simple market lookup...")
        
        try:
            client = AsyncClient(Network.mainnet())
            
            # Get spot markets
            logger.info("Fetching spot markets...")
            result = await client.fetch_spot_markets()
            
            logger.info(f"Result type: {type(result)}")
            
            if hasattr(result, '__dict__'):
                logger.info(f"Result attributes: {list(result.__dict__.keys())}")
            elif isinstance(result, dict):
                logger.info(f"Result keys: {list(result.keys())}")
            
            # Try to access markets in different ways
            markets = None
            if hasattr(result, 'markets'):
                markets = result.markets
                logger.info(f"Found {len(markets)} markets via .markets attribute")
            elif isinstance(result, list):
                markets = result
                logger.info(f"Result is directly a list of {len(markets)} markets")
            elif isinstance(result, dict):
                for key in ['markets', 'market', 'data']:
                    if key in result:
                        markets = result[key]
                        logger.info(f"Found {len(markets)} markets via .{key} key")
                        break
            
            if markets and len(markets) > 0:
                first_market = markets[0]
                logger.info(f"First market type: {type(first_market)}")
                
                if hasattr(first_market, '__dict__'):
                    logger.info(f"First market attributes: {list(first_market.__dict__.keys())}")
                elif isinstance(first_market, dict):
                    logger.info(f"First market keys: {list(first_market.keys())}")
                
                # Look for INJ/USDT
                for i, market in enumerate(markets[:10]):  # Check first 10
                    if hasattr(market, 'ticker'):
                        ticker = market.ticker
                    elif isinstance(market, dict):
                        ticker = market.get('ticker', 'N/A')
                    else:
                        ticker = str(market)
                    
                    logger.info(f"Market {i+1}: {ticker}")
                    
                    if "INJ" in ticker and "USDT" in ticker:
                        logger.info(f"Found INJ/USDT market!")
                        if hasattr(market, 'market_id'):
                            logger.info(f"Market ID: {market.market_id}")
                        elif isinstance(market, dict):
                            logger.info(f"Market ID: {market.get('market_id', 'N/A')}")
                        break
            else:
                logger.error("No markets found")
                
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    @pytest.mark.asyncio
    async def test_simple_streaming(self):
        """Test simple streaming with known working market"""
        logger.info("Testing simple streaming...")
        
        class SimpleCallback:
            def __init__(self):
                self.count = 0
                
            def __call__(self, data):
                self.count += 1
                logger.info(f"Callback #{self.count}: Received data type {type(data)}")
                
        try:
            client = AsyncClient(Network.mainnet())
            callback = SimpleCallback()
            
            # Use a known active market ID (this is a real mainnet INJ/USDT market)
            market_id = "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"
            logger.info(f"Testing with market ID: {market_id}")
            
            # Start streaming
            logger.info("Starting orderbook stream...")
            task = asyncio.create_task(
                client.listen_spot_orderbook_updates(
                    market_ids=[market_id],
                    callback=callback
                )
            )
            
            # Wait for callbacks
            logger.info("Waiting 20 seconds for callbacks...")
            await asyncio.sleep(20)
            
            logger.info(f"Received {callback.count} callbacks")
            
            # Cancel
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Task cancelled successfully")
                
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            import traceback
            traceback.print_exc()
