#!/usr/bin/env python3
"""
Debug script to list active Injective markets and test subscriptions
"""

import asyncio
import logging
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_active_markets():
    """Get list of active spot markets"""
    networks = [
        ("mainnet", Network.mainnet()),
        ("testnet", Network.testnet())
    ]
    
    for network_name, network in networks:
        logger.info(f"\n=== {network_name.upper()} MARKETS ===")
        
        try:
            client = AsyncClient(network)
            
            # Get spot markets
            markets_response = await client.fetch_spot_markets()
            logger.info(f"Markets response type: {type(markets_response)}")
            logger.info(f"Markets response keys: {list(markets_response.keys()) if hasattr(markets_response, 'keys') else 'No keys'}")
            
            # Handle different response formats
            if hasattr(markets_response, 'markets'):
                markets = markets_response.markets
            elif isinstance(markets_response, dict) and 'markets' in markets_response:
                markets = markets_response['markets']
            elif isinstance(markets_response, list):
                markets = markets_response
            else:
                logger.error(f"Unknown markets response format: {type(markets_response)}")
                continue
            
            logger.info(f"Found {len(markets)} spot markets on {network_name}")
            
            # Show first 10 active markets
            active_markets = []
            for i, market in enumerate(markets[:10]):
                market_info = {
                    "id": market.market_id,
                    "ticker": market.ticker,
                    "base": market.base_token.symbol,
                    "quote": market.quote_token.symbol,
                    "status": market.market_status,
                }
                active_markets.append(market_info)
                logger.info(f"  {i+1}. {market.ticker} ({market.market_id[:16]}...) - {market.market_status}")
            
            # Test subscription on first active market
            if active_markets:
                test_market = active_markets[0]
                logger.info(f"\nTesting subscription on {test_market['ticker']} ({test_market['id']})")
                
                callback_count = 0
                
                def test_callback(data):
                    nonlocal callback_count
                    callback_count += 1
                    logger.info(f"CALLBACK #{callback_count}: Received data on {network_name} - {type(data)}")
                    if hasattr(data, 'keys'):
                        logger.info(f"  Keys: {list(data.keys())}")
                    
                # Test orderbook subscription
                task = asyncio.create_task(
                    client.listen_spot_orderbook_updates(
                        market_ids=[test_market['id']],
                        callback=test_callback
                    )
                )
                
                # Wait for data
                logger.info(f"Waiting 10 seconds for data on {test_market['ticker']}...")
                await asyncio.sleep(10)
                
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                logger.info(f"Result: {callback_count} callbacks received")
                
                if callback_count > 0:
                    return network_name, test_market, callback_count
        
        except Exception as e:
            logger.error(f"Error with {network_name}: {e}")
    
    return None, None, 0

if __name__ == "__main__":
    result = asyncio.run(get_active_markets())
    print(f"\nFinal result: {result}")
