#!/usr/bin/env python3
"""
Market Volume Analyzer - Fetches and ranks Injective markets by trading volume
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timezone

from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MarketInfo:
    """Market information with volume metrics"""
    market_id: str
    ticker: str
    base_token: str
    quote_token: str
    volume_24h: Decimal
    volume_7d: Decimal
    price_change_24h: Decimal
    market_status: str
    is_active: bool

class MarketVolumeAnalyzer:
    """Analyzes and ranks Injective markets by trading volume"""
    
    def __init__(self, network: str = "mainnet"):
        self.network = Network.mainnet() if network == "mainnet" else Network.testnet()
        self.client = AsyncClient(self.network)
        
    async def fetch_all_spot_markets(self) -> List[MarketInfo]:
        """Fetch all spot markets with volume data"""
        try:
            markets_response = await self.client.fetch_spot_markets()
            
            if hasattr(markets_response, 'markets'):
                markets = markets_response.markets
            elif isinstance(markets_response, dict) and 'markets' in markets_response:
                markets = markets_response['markets']
            elif isinstance(markets_response, list):
                markets = markets_response
            else:
                logger.error(f"Unknown markets response format: {type(markets_response)}")
                return []
                
            market_infos = []
            
            for market in markets:
                try:
                    # Handle different market object types
                    if hasattr(market, 'ticker'):
                        ticker = market.ticker
                        market_id = market.market_id
                        base_symbol = market.base_token.symbol if hasattr(market, 'base_token') else 'UNKNOWN'
                        quote_symbol = market.quote_token.symbol if hasattr(market, 'quote_token') else 'UNKNOWN'
                        status = market.market_status if hasattr(market, 'market_status') else 'active'
                    elif isinstance(market, dict):
                        ticker = market.get('ticker', 'UNKNOWN')
                        market_id = market.get('market_id', '')
                        base_symbol = market.get('base_denom', 'UNKNOWN')
                        quote_symbol = market.get('quote_denom', 'UNKNOWN')
                        status = market.get('market_status', 'active')
                    else:
                        logger.warning(f"Unknown market object type: {type(market)}")
                        continue
                    
                    # Only include USD pairs for our trading focus
                    if not ticker.endswith('/USD') and 'USD' not in quote_symbol:
                        continue
                        
                    # Get market summary for volume data
                    summary = await self._get_market_summary(market_id)
                    
                    market_info = MarketInfo(
                        market_id=market_id,
                        ticker=ticker,
                        base_token=base_symbol,
                        quote_token=quote_symbol,
                        volume_24h=Decimal(str(summary.get('volume', '0'))),
                        volume_7d=Decimal(str(summary.get('volume_7d', '0'))),
                        price_change_24h=Decimal(str(summary.get('change_24h', '0'))),
                        market_status=status,
                        is_active=status == 'active'
                    )
                    
                    market_infos.append(market_info)
                    
                except Exception as e:
                    logger.warning(f"Error processing market {market.ticker}: {e}")
                    continue
                    
            return market_infos
            
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    async def _get_market_summary(self, market_id: str) -> Dict[str, Any]:
        """Get market summary including volume data"""
        try:
            # Try to get market summary
            summary_response = await self.client.fetch_spot_market_summary(market_id=market_id)
            
            if hasattr(summary_response, 'market_summary'):
                summary = summary_response.market_summary
                return {
                    'volume': summary.volume if hasattr(summary, 'volume') else '0',
                    'volume_7d': getattr(summary, 'volume_7d', '0'),
                    'change_24h': getattr(summary, 'change_24h', '0')
                }
            elif isinstance(summary_response, dict):
                return summary_response
            else:
                return {'volume': '0', 'volume_7d': '0', 'change_24h': '0'}
                
        except Exception as e:
            logger.debug(f"Could not get summary for {market_id}: {e}")
            return {'volume': '0', 'volume_7d': '0', 'change_24h': '0'}
    
    def get_top_volume_markets(self, markets: List[MarketInfo], count: int = 20) -> List[MarketInfo]:
        """Get top markets by 24h volume"""
        # Filter only active markets
        active_markets = [m for m in markets if m.is_active]
        
        # Sort by 24h volume (descending)
        sorted_markets = sorted(active_markets, key=lambda x: x.volume_24h, reverse=True)
        
        return sorted_markets[:count]
    
    def get_most_volatile_markets(self, markets: List[MarketInfo], count: int = 10) -> List[MarketInfo]:
        """Get most volatile markets by price change"""
        active_markets = [m for m in markets if m.is_active]
        
        # Sort by absolute price change (most volatile)
        sorted_markets = sorted(active_markets, key=lambda x: abs(x.price_change_24h), reverse=True)
        
        return sorted_markets[:count]
    
    async def analyze_market_activity(self, market_id: str, duration: int = 30) -> Dict[str, Any]:
        """Analyze real-time activity for a specific market"""
        logger.info(f"Analyzing activity for {market_id} for {duration} seconds...")
        
        message_count = 0
        orderbook_updates = 0
        trade_updates = 0
        
        def activity_callback(data):
            nonlocal message_count, orderbook_updates, trade_updates
            message_count += 1
            
            # Determine message type based on content
            if 'orderbook' in str(data).lower():
                orderbook_updates += 1
            elif 'trade' in str(data).lower():
                trade_updates += 1
        
        try:
            # Start monitoring
            task = asyncio.create_task(
                self.client.listen_spot_orderbook_updates(
                    market_ids=[market_id],
                    callback=activity_callback
                )
            )
            
            # Wait for data collection
            await asyncio.sleep(duration)
            
            # Stop monitoring
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            return {
                'total_messages': message_count,
                'orderbook_updates': orderbook_updates,
                'trade_updates': trade_updates,
                'messages_per_second': message_count / duration,
                'activity_score': message_count / duration * 10  # Normalized score
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market activity: {e}")
            return {
                'total_messages': 0,
                'orderbook_updates': 0,
                'trade_updates': 0,
                'messages_per_second': 0,
                'activity_score': 0
            }

async def main():
    """Main analysis function"""
    analyzer = MarketVolumeAnalyzer()
    
    logger.info("🔍 Fetching all Injective spot markets...")
    all_markets = await analyzer.fetch_all_spot_markets()
    
    logger.info(f"📊 Found {len(all_markets)} USD markets")
    
    # Get top volume markets
    top_volume = analyzer.get_top_volume_markets(all_markets, 20)
    
    logger.info("\n🏆 TOP 20 MARKETS BY 24H VOLUME:")
    logger.info("=" * 80)
    logger.info(f"{'Rank':<4} {'Ticker':<20} {'Market ID':<16} {'Volume 24h':<15} {'Change 24h':<10}")
    logger.info("-" * 80)
    
    for i, market in enumerate(top_volume, 1):
        logger.info(f"{i:<4} {market.ticker:<20} {market.market_id[:16]:<16} ${market.volume_24h:<14} {market.price_change_24h:>8.2f}%")
    
    # Get most volatile markets
    most_volatile = analyzer.get_most_volatile_markets(all_markets, 10)
    
    logger.info("\n🎢 TOP 10 MOST VOLATILE MARKETS:")
    logger.info("=" * 80)
    logger.info(f"{'Rank':<4} {'Ticker':<20} {'Market ID':<16} {'Change 24h':<10}")
    logger.info("-" * 80)
    
    for i, market in enumerate(most_volatile, 1):
        logger.info(f"{i:<4} {market.ticker:<20} {market.market_id[:16]:<16} {market.price_change_24h:>8.2f}%")
    
    # Analyze activity for top 5 markets
    logger.info("\n📈 ANALYZING REAL-TIME ACTIVITY FOR TOP 5 MARKETS:")
    logger.info("=" * 80)
    
    for i, market in enumerate(top_volume[:5], 1):
        activity = await analyzer.analyze_market_activity(market.market_id, 15)  # 15 seconds each
        
        logger.info(f"{i}. {market.ticker}")
        logger.info(f"   Messages/sec: {activity['messages_per_second']:.2f}")
        logger.info(f"   Activity Score: {activity['activity_score']:.1f}")
        logger.info(f"   Total Messages: {activity['total_messages']}")
        logger.info("")
    
    # Return top markets for use in performance tests
    return [market.market_id for market in top_volume[:20]]

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nTop 20 market IDs for performance testing:")
    for i, market_id in enumerate(result, 1):
        print(f"{i:2d}. {market_id}")
