#!/usr/bin/env python3
"""
Quick debug script to see market data structure
"""
import asyncio
import logging
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_markets():
    """Debug market data structure"""
    client = AsyncClient(Network.mainnet())
    
    try:
        # Fetch markets
        print("Fetching markets...")
        markets_response = await client.fetch_spot_markets()
        
        print(f"Response type: {type(markets_response)}")
        
        # Handle dict response
        if isinstance(markets_response, dict):
            print(f"Dict keys: {list(markets_response.keys())}")
            
            if 'markets' in markets_response:
                markets = markets_response['markets']
            else:
                # Maybe the whole response is the markets list
                markets = markets_response.get('data', [])
                
        elif hasattr(markets_response, 'markets'):
            markets = markets_response.markets
        else:
            print("Could not find markets in response")
            return []
            
        print(f"Found {len(markets)} markets")
         # Show first market structure
        if markets:
            market = markets[0]
            print(f"\nFirst market type: {type(market)}")
            
            if isinstance(market, dict):
                print(f"Dict keys: {list(market.keys())}")
                print(f"Sample market data: {market}")
                
            # Look for USD markets
            usd_count = 0
            sample_usd_markets = []
            
            for market in markets[:50]:  # Check first 50
                try:
                    if isinstance(market, dict):
                        ticker = market.get('ticker', '')
                        quote_denom = market.get('quoteDenom', '')
                        base_denom = market.get('baseDenom', '')
                        market_id = market.get('marketId', '')  # Note: camelCase
                        
                        # Check for USD in various fields
                        if ('USD' in ticker or 'USD' in quote_denom or 
                            'usdt' in quote_denom.lower() or 'usdc' in quote_denom.lower()):
                            usd_count += 1
                            if len(sample_usd_markets) < 10:
                                display_ticker = ticker if ticker else f"{base_denom}/{quote_denom}"
                                sample_usd_markets.append({
                                    'id': market_id,
                                    'ticker': display_ticker,
                                    'quote_denom': quote_denom
                                })
                    elif hasattr(market, 'ticker'):
                        if 'USD' in market.ticker:
                            usd_count += 1
                            if len(sample_usd_markets) < 10:
                                sample_usd_markets.append({
                                    'id': market.market_id,
                                    'ticker': market.ticker
                                })
                except Exception as e:
                    print(f"Error processing market: {e}")
                    
            print(f"\nFound {usd_count} USD-like markets in first 50 checked")
            print("Sample USD markets:")
            for market in sample_usd_markets:
                print(f"  {market['ticker']} - {market['id']}")
                
            return [m['id'] for m in sample_usd_markets]
                        
        return []
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    result = asyncio.run(debug_markets())
    print(f"\nFound {len(result)} USD market IDs for testing")
