# Network utilities for robust Injective Protocol connectivity
"""
Network utilities to handle connectivity issues, endpoint fallbacks, and robust connection strategies.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from pyinjective import AsyncClient
from pyinjective.core.network import Network

logger = logging.getLogger(__name__)


class NetworkConnectivityManager:
    """Manages network connectivity with fallback strategies"""
    
    # Available node types for injective-py Network class
    MAINNET_NODES = ["lb", "sentry", "k8s"]  # Load balancer, sentry, kubernetes
    TESTNET_NODES = ["lb", "sentry", "k8s"]  # Same options for testnet
    
    @staticmethod
    async def create_robust_client(network: str = "mainnet", max_retries: int = 3) -> Tuple[AsyncClient, str]:
        """
        Create a robust AsyncClient with fallback node types
        
        Returns:
            Tuple of (client, node_type) if successful
            
        Raises:
            ConnectionError if all nodes fail
        """
        nodes = NetworkConnectivityManager.MAINNET_NODES if network == "mainnet" else NetworkConnectivityManager.TESTNET_NODES
        
        last_error = None
        
        for node_type in nodes:
            for retry in range(max_retries):
                try:
                    logger.info(f"Attempting to connect to {network} using {node_type} node (attempt {retry + 1}/{max_retries})")
                    
                    # Create network configuration with specific node
                    if network == "mainnet":
                        network_config = Network.mainnet(node=node_type)
                    else:
                        network_config = Network.testnet(node=node_type)
                    
                    # Create client
                    client = AsyncClient(network_config)
                    
                    # Test connectivity with a simple call
                    await asyncio.wait_for(client.get_chain_id(), timeout=10.0)
                    
                    logger.info(f"✅ Successfully connected to {network} using {node_type} node")
                    return client, node_type
                    
                except asyncio.TimeoutError:
                    last_error = f"Timeout connecting to {node_type} node"
                    logger.warning(f"⏱️ Timeout connecting to {node_type} node (attempt {retry + 1})")
                    
                except Exception as e:
                    last_error = f"Error with {node_type} node: {e}"
                    logger.warning(f"⚠️ Failed to connect to {node_type} node: {e}")
                    
                    # If it's a 502 or network error, try next node immediately
                    if "502" in str(e) or "UNAVAILABLE" in str(e):
                        break
                
                # Brief delay before retry
                if retry < max_retries - 1:
                    await asyncio.sleep(1.0)
        
        raise ConnectionError(f"Failed to connect to all {network} nodes. Last error: {last_error}")
    
    @staticmethod
    async def test_streaming_capability(client: AsyncClient) -> bool:
        """Test if the client can handle streaming operations"""
        try:
            # Test basic market data fetch
            spot_markets = await asyncio.wait_for(client.fetch_spot_markets(), timeout=15.0)
            
            if not spot_markets.markets:
                logger.warning("No spot markets found - streaming may not be available")
                return False
            
            # Test orderbook fetch as proxy for streaming capability
            test_market = spot_markets.markets[0]
            orderbook = await asyncio.wait_for(
                client.fetch_spot_orderbook_v2(market_id=test_market.market_id), 
                timeout=10.0
            )
            
            has_data = (
                (orderbook.buys and len(orderbook.buys) > 0) or 
                (orderbook.sells and len(orderbook.sells) > 0)
            )
            
            logger.info(f"✅ Streaming capability test passed - orderbook has {len(orderbook.buys)} bids, {len(orderbook.sells)} asks")
            return has_data
            
        except Exception as e:
            logger.error(f"❌ Streaming capability test failed: {e}")
            return False
    
    @staticmethod
    async def get_high_volume_markets(client: AsyncClient, limit: int = 10) -> List[Dict[str, Any]]:
        """Get high volume markets for testing"""
        try:
            spot_markets = await client.fetch_spot_markets()
            
            # Convert to list and sort by volume if available
            markets_list = []
            for market in spot_markets.markets:
                market_info = {
                    'market_id': market.market_id,
                    'ticker': market.ticker,
                    'base_denom': market.base_denom,
                    'quote_denom': market.quote_denom,
                    'status': getattr(market, 'status', 'unknown')
                }
                markets_list.append(market_info)
            
            # Filter for active USDT markets (typically higher volume)
            usdt_markets = [m for m in markets_list if 'USDT' in m['ticker'] and m['status'] == 'active']
            
            # Return top markets (sorted by ticker for now, as volume data might not be directly available)
            popular_tokens = ['BTC', 'ETH', 'INJ', 'ATOM', 'OSMO', 'TIA', 'WMATIC', 'USDC']
            prioritized = []
            others = []
            
            for market in usdt_markets:
                ticker = market['ticker']
                if any(token in ticker for token in popular_tokens):
                    prioritized.append(market)
                else:
                    others.append(market)
            
            result = prioritized[:limit] + others[:max(0, limit - len(prioritized))]
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get markets: {e}")
            return []


class NetworkAwareInjectiveClient:
    """Injective client with network awareness and fallback strategies"""
    
    def __init__(self, network: str = "mainnet"):
        self.network = network
        self.client: Optional[AsyncClient] = None
        self.endpoint_name: Optional[str] = None
        self._connection_tested = False
    
    async def connect(self) -> bool:
        """Connect with robust node fallback"""
        try:
            self.client, self.endpoint_name = await NetworkConnectivityManager.create_robust_client(
                network=self.network,
                max_retries=3
            )
            
            # Test streaming capability
            streaming_ok = await NetworkConnectivityManager.test_streaming_capability(self.client)
            if not streaming_ok:
                logger.warning("⚠️ Streaming capability test failed - connection may be limited")
            
            self._connection_tested = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to establish robust connection: {e}")
            return False
    
    async def get_markets(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get high volume markets for testing"""
        if not self.client:
            raise RuntimeError("Client not connected")
        
        return await NetworkConnectivityManager.get_high_volume_markets(self.client, limit)
    
    def is_ready(self) -> bool:
        """Check if client is ready for streaming operations"""
        return self.client is not None and self._connection_tested


__all__ = [
    "NetworkConnectivityManager",
    "NetworkAwareInjectiveClient"
]
