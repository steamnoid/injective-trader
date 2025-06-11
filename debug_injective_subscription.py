#!/usr/bin/env python3
"""
Debug script to test Injective Protocol WebSocket subscriptions directly
This will help us understand why callbacks aren't being triggered
"""

import asyncio
import logging
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_direct_injective_subscription():
    """Test direct injective-py subscription to understand callback behavior"""
    
    # Try both testnet and mainnet
    networks = [
        ("mainnet", Network.mainnet(), [
            "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa",  # INJ/USDT mainnet
            "0x4ca0f92fc28be0c9761326016b5a1a2177dd6375558365116b5bdda9abc229ce",  # BTC/USDT mainnet
        ]),
        ("testnet", Network.testnet(), [
            "0x54d4505adef6a5cef26bc403a33d595620ded4e15b9e2bc3dd489b714813366a",  # INJ/USDT testnet
        ])
    ]
    
    for network_name, network, market_ids in networks:
        logger.info(f"\n=== Testing {network_name.upper()} ===")
        
        try:
            # Create AsyncClient
            client = AsyncClient(network)
            
            # Callback counters
            orderbook_count = 0
            trades_count = 0
            
            def orderbook_callback(data):
                nonlocal orderbook_count
                orderbook_count += 1
                logger.info(f"[{network_name}] Orderbook callback #{orderbook_count}: {type(data)} - {list(data.keys()) if hasattr(data, 'keys') else 'non-dict data'}")
                if hasattr(data, 'keys') and 'orderbook' in data:
                    logger.info(f"[{network_name}] Orderbook market: {data.get('market_id', 'unknown')}")
            
            def trades_callback(data):
                nonlocal trades_count
                trades_count += 1
                logger.info(f"[{network_name}] Trades callback #{trades_count}: {type(data)} - {list(data.keys()) if hasattr(data, 'keys') else 'non-dict data'}")
                if hasattr(data, 'keys') and 'trade' in data:
                    logger.info(f"[{network_name}] Trade market: {data.get('market_id', 'unknown')}")
            
            logger.info(f"[{network_name}] Starting subscriptions for markets: {market_ids}")
            
            # Start subscriptions as background tasks
            orderbook_task = asyncio.create_task(
                client.listen_spot_orderbook_updates(
                    market_ids=market_ids,
                    callback=orderbook_callback
                )
            )
            
            trades_task = asyncio.create_task(
                client.listen_spot_trades_updates(
                    market_ids=market_ids,
                    callback=trades_callback
                )
            )
            
            # Wait for data for 15 seconds
            logger.info(f"[{network_name}] Waiting for 15 seconds...")
            await asyncio.sleep(15)
            
            # Cancel subscriptions
            orderbook_task.cancel()
            trades_task.cancel()
            
            try:
                await asyncio.gather(orderbook_task, trades_task, return_exceptions=True)
            except:
                pass
            
            logger.info(f"[{network_name}] Results: {orderbook_count} orderbook updates, {trades_count} trades")
            
            # If we got data on this network, we're done
            if orderbook_count > 0 or trades_count > 0:
                logger.info(f"[{network_name}] SUCCESS! Received data from {network_name}")
                return network_name, orderbook_count, trades_count
            else:
                logger.warning(f"[{network_name}] No data received from {network_name}")
                
        except Exception as e:
            logger.error(f"[{network_name}] Error testing {network_name}: {e}")
            
    return None, 0, 0

if __name__ == "__main__":
    result = asyncio.run(test_direct_injective_subscription())
    print(f"\nFinal result: {result}")
