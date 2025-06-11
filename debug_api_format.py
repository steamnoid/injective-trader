#!/usr/bin/env python3
"""
Simple script to understand the Injective API response format
"""

import asyncio
import logging
import json
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def inspect_api_response():
    """Inspect the actual API response format"""
    try:
        # Try mainnet first
        client = AsyncClient(Network.mainnet())
        
        logger.info("Fetching spot markets...")
        markets_response = await client.fetch_spot_markets()
        
        logger.info(f"Response type: {type(markets_response)}")
        
        if hasattr(markets_response, '__dict__'):
            logger.info(f"Response attributes: {list(markets_response.__dict__.keys())}")
            
        if isinstance(markets_response, dict):
            logger.info(f"Response keys: {list(markets_response.keys())}")
            for key, value in list(markets_response.items())[:3]:  # Show first 3 items
                logger.info(f"  {key}: {type(value)} - {str(value)[:100]}...")
        
        # Try to extract markets in different ways
        possible_markets = None
        if hasattr(markets_response, 'markets'):
            possible_markets = markets_response.markets
            logger.info(f"Found markets attribute: {type(possible_markets)}")
        elif isinstance(markets_response, dict):
            for key in ['markets', 'market', 'data', 'result']:
                if key in markets_response:
                    possible_markets = markets_response[key]
                    logger.info(f"Found markets in key '{key}': {type(possible_markets)}")
                    break
        
        if possible_markets:
            logger.info(f"Markets type: {type(possible_markets)}")
            if isinstance(possible_markets, list) and len(possible_markets) > 0:
                first_market = possible_markets[0]
                logger.info(f"First market type: {type(first_market)}")
                if hasattr(first_market, '__dict__'):
                    logger.info(f"First market attributes: {list(first_market.__dict__.keys())}")
                elif isinstance(first_market, dict):
                    logger.info(f"First market keys: {list(first_market.keys())}")
                    logger.info(f"Sample market: {json.dumps(first_market, indent=2, default=str)[:500]}...")
        else:
            logger.warning("Could not find markets in response")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(inspect_api_response())
