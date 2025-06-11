#!/usr/bin/env python3
"""
Get active markets with highest volume for testing and trading
"""

import asyncio
import logging
from typing import List, Dict, Any
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_top_volume_markets(network_name: str = "mainnet", limit: int = 10) -> List[Dict[str, Any]]:
    """Get markets with highest 24h volume"""
    
    try:
        network = Network.mainnet() if network_name == "mainnet" else Network.testnet()
        client = AsyncClient(network)
        
        # Get spot markets
        markets_response = await client.fetch_spot_markets()
        logger.info(f"Fetched markets from {network_name}")
        
        # Handle response format
        if isinstance(markets_response, dict) and 'markets' in markets_response:
            markets = markets_response['markets']
        else:
            markets = markets_response
            
        # Convert to list of dicts for easier processing
        market_data = []
        for market in markets:
            try:
                # Handle different market object types
                if hasattr(market, 'market_id'):
                    market_info = {
                        'market_id': market.market_id,
                        'ticker': market.ticker,
                        'base_token': market.base_token.symbol if hasattr(market.base_token, 'symbol') else str(market.base_token),
                        'quote_token': market.quote_token.symbol if hasattr(market.quote_token, 'symbol') else str(market.quote_token),
                        'status': market.market_status if hasattr(market, 'market_status') else 'unknown'
                    }
                elif isinstance(market, dict):
                    market_info = {
                        'market_id': market.get('marketId', market.get('market_id', '')),
                        'ticker': market.get('ticker', ''),
                        'base_token': market.get('baseToken', {}).get('symbol', ''),
                        'quote_token': market.get('quoteToken', {}).get('symbol', ''),
                        'status': market.get('marketStatus', 'unknown')
                    }
                else:
                    continue
                    
                # Only include USD pairs that are active
                if (market_info['quote_token'] in ['USDT', 'USDC', 'USD'] and 
                    market_info['status'] == 'active'):
                    market_data.append(market_info)
                    
            except Exception as e:
                logger.debug(f"Error processing market: {e}")
                continue
        
        logger.info(f"Found {len(market_data)} active USD markets")
        
        # Try to get volume data for ranking
        try:
            # Get market summaries for volume data
            market_summaries = await client.fetch_spot_market_summaries()
            
            # Create volume lookup
            volume_lookup = {}
            if isinstance(market_summaries, dict) and 'market_summaries' in market_summaries:
                summaries = market_summaries['market_summaries']
            else:
                summaries = market_summaries
                
            for summary in summaries:
                try:
                    if hasattr(summary, 'market_id'):
                        market_id = summary.market_id
                        volume = float(summary.volume) if hasattr(summary, 'volume') else 0.0
                    elif isinstance(summary, dict):
                        market_id = summary.get('marketId', summary.get('market_id', ''))
                        volume = float(summary.get('volume', 0))
                    else:
                        continue
                        
                    volume_lookup[market_id] = volume
                except Exception as e:
                    logger.debug(f"Error processing market summary: {e}")
                    continue
            
            # Add volume data to markets
            for market in market_data:
                market['volume_24h'] = volume_lookup.get(market['market_id'], 0.0)
            
            # Sort by volume (descending)
            market_data.sort(key=lambda x: x['volume_24h'], reverse=True)
            
        except Exception as e:
            logger.warning(f"Could not fetch volume data: {e}")
            # If volume data unavailable, just return the markets
        
        # Return top markets
        top_markets = market_data[:limit]
        
        logger.info(f"Top {len(top_markets)} volume markets:")
        for i, market in enumerate(top_markets, 1):
            volume = market.get('volume_24h', 0)
            logger.info(f"  {i}. {market['ticker']} ({market['market_id'][:16]}...) - Volume: ${volume:,.0f}")
        
        return top_markets
        
    except Exception as e:
        logger.error(f"Error fetching markets from {network_name}: {e}")
        return []

async def test_top_markets_subscription(top_markets: List[Dict[str, Any]], test_count: int = 3):
    """Test subscription on top volume markets"""
    
    if not top_markets:
        logger.error("No markets available for testing")
        return False
        
    test_markets = top_markets[:test_count]
    market_ids = [m['market_id'] for m in test_markets]
    
    logger.info(f"\n🧪 Testing subscription on top {test_count} volume markets:")
    for market in test_markets:
        logger.info(f"  - {market['ticker']} (Volume: ${market.get('volume_24h', 0):,.0f})")
    
    try:
        network = Network.mainnet()
        client = AsyncClient(network)
        
        message_count = 0
        
        def test_callback(data):
            nonlocal message_count
            message_count += 1
            logger.info(f"📨 Message #{message_count}: {type(data)}")
        
        # Test orderbook subscription
        task = asyncio.create_task(
            client.listen_spot_orderbook_updates(
                market_ids=market_ids,
                callback=test_callback
            )
        )
        
        logger.info(f"⏰ Testing for 15 seconds...")
        await asyncio.sleep(15)
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        logger.info(f"✅ Result: {message_count} messages received")
        logger.info(f"   Success rate: {message_count/15:.1f} msg/sec")
        
        return message_count > 0
        
    except Exception as e:
        logger.error(f"Error testing markets: {e}")
        return False

async def main():
    """Main function to get active markets and test them"""
    
    # Get top volume markets from mainnet
    top_markets = await get_top_volume_markets("mainnet", limit=10)
    
    if not top_markets:
        logger.error("❌ No active markets found")
        return
    
    # Test subscription on top markets
    success = await test_top_markets_subscription(top_markets, test_count=3)
    
    if success:
        logger.info("\n✅ SUCCESS: Market subscription working with high-volume markets")
        
        # Export the top market IDs for use in tests
        top_market_ids = [m['market_id'] for m in top_markets[:5]]
        logger.info("\n📋 Top 5 market IDs for tests:")
        for i, market_id in enumerate(top_market_ids, 1):
            ticker = top_markets[i-1]['ticker']
            logger.info(f"  {i}. {ticker}: {market_id}")
            
        return top_markets
    else:
        logger.error("❌ FAILED: Market subscription not working")
        return None

if __name__ == "__main__":
    result = asyncio.run(main())
