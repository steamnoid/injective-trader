#!/usr/bin/env python3
"""
Fetch Most Volumed Perpetual USDT Markets from Injective Protocol
This script will discover and analyze active perpetual markets to identify
the highest volume USDT pairs for testing our multiple market subscription fix.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network
import json
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PerpetualMarketAnalyzer:
    """Analyze and fetch perpetual markets data from Injective Protocol"""
    
    def __init__(self, network: str = "mainnet"):
        self.network = Network.mainnet() if network == "mainnet" else Network.testnet()
        self.client = None
        
    async def initialize(self) -> bool:
        """Initialize the Injective client"""
        try:
            self.client = AsyncClient(self.network)
            logger.info("✅ Injective client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize client: {e}")
            return False
            
    async def fetch_derivative_markets(self) -> List[Dict[str, Any]]:
        """Fetch all derivative markets from Injective"""
        try:
            logger.info("📊 Fetching derivative markets...")
            markets_response = await self.client.fetch_derivative_markets()
            
            if hasattr(markets_response, 'markets'):
                markets = markets_response.markets
                logger.info(f"Found {len(markets)} derivative markets")
                return markets
            else:
                logger.warning("No markets found in response")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching derivative markets: {e}")
            return []
    
    async def fetch_market_summary(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Fetch market summary for volume analysis"""
        try:
            summary_response = await self.client.fetch_derivative_market_summary(market_id=market_id)
            return summary_response
        except Exception as e:
            logger.debug(f"Could not fetch summary for market {market_id}: {e}")
            return None
    
    async def analyze_perpetual_markets(self) -> List[Dict[str, Any]]:
        """Analyze perpetual markets and return sorted by volume"""
        markets = await self.fetch_derivative_markets()
        if not markets:
            return []
        
        perpetual_usdt_markets = []
        
        logger.info("🔍 Analyzing markets for USDT perpetuals...")
        
        for market in markets:
            try:
                # Extract market information
                market_info = {
                    'market_id': market.market_id,
                    'ticker': market.ticker,
                    'base_token': getattr(market, 'base_token', {}).get('symbol', 'Unknown'),
                    'quote_token': getattr(market, 'quote_token', {}).get('symbol', 'Unknown'),
                    'market_status': market.market_status,
                    'perpetual_market_info': getattr(market, 'perpetual_market_info', None),
                    'volume_24h': 0,  # Will be filled from market summary
                    'price': 0,       # Will be filled from market summary
                }
                
                # Filter for USDT perpetuals
                if (market_info['quote_token'] == 'USDT' and 
                    market_info['perpetual_market_info'] is not None and
                    market_info['market_status'] == 'active'):
                    
                    # Fetch market summary for volume data
                    summary = await self.fetch_market_summary(market.market_id)
                    if summary:
                        market_info['volume_24h'] = float(getattr(summary, 'volume', 0))
                        market_info['price'] = float(getattr(summary, 'price', 0))
                    
                    perpetual_usdt_markets.append(market_info)
                    logger.info(f"✅ Found perpetual: {market_info['ticker']} (Volume: ${market_info['volume_24h']:,.2f})")
                    
            except Exception as e:
                logger.debug(f"Error processing market {getattr(market, 'market_id', 'unknown')}: {e}")
                continue
        
        # Sort by 24h volume (descending)
        perpetual_usdt_markets.sort(key=lambda x: x['volume_24h'], reverse=True)
        
        return perpetual_usdt_markets
    
    async def get_top_perpetual_markets(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top perpetual USDT markets by volume"""
        markets = await self.analyze_perpetual_markets()
        return markets[:limit]
    
    def format_market_report(self, markets: List[Dict[str, Any]]) -> str:
        """Format markets data into a readable report"""
        if not markets:
            return "❌ No perpetual USDT markets found"
        
        report = "\n" + "="*80 + "\n"
        report += "📊 TOP PERPETUAL USDT MARKETS BY 24H VOLUME\n"
        report += "="*80 + "\n"
        
        for i, market in enumerate(markets, 1):
            report += f"\n{i:2d}. {market['ticker']:20s}\n"
            report += f"    Market ID: {market['market_id']}\n"
            report += f"    Base/Quote: {market['base_token']}/{market['quote_token']}\n"
            report += f"    24h Volume: ${market['volume_24h']:>15,.2f}\n"
            report += f"    Price: ${market['price']:>20,.6f}\n"
            report += f"    Status: {market['market_status']}\n"
            report += "    " + "-"*50 + "\n"
        
        return report
    
    async def export_market_ids_for_testing(self, markets: List[Dict[str, Any]], filename: str = "top_perpetual_market_ids.json"):
        """Export market IDs in format suitable for testing"""
        market_data = {
            'timestamp': datetime.now().isoformat(),
            'top_perpetual_usdt_markets': [
                {
                    'market_id': market['market_id'],
                    'ticker': market['ticker'],
                    'volume_24h': market['volume_24h'],
                    'rank': i + 1
                }
                for i, market in enumerate(markets)
            ],
            'testing_recommendations': {
                'highest_volume_pair': markets[0]['market_id'] if markets else None,
                'top_3_for_testing': [m['market_id'] for m in markets[:3]],
                'btc_usdt_perp': next((m['market_id'] for m in markets if 'BTC' in m['ticker']), None),
                'eth_usdt_perp': next((m['market_id'] for m in markets if 'ETH' in m['ticker']), None),
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(market_data, f, indent=2)
        
        logger.info(f"💾 Market data exported to {filename}")
        return market_data

async def main():
    """Main execution function"""
    logger.info("🚀 Starting Perpetual USDT Markets Analysis...")
    
    analyzer = PerpetualMarketAnalyzer(network="mainnet")
    
    # Initialize client
    if not await analyzer.initialize():
        logger.error("❌ Failed to initialize analyzer")
        return
    
    # Fetch and analyze markets
    logger.info("📈 Fetching top perpetual USDT markets...")
    top_markets = await analyzer.get_top_perpetual_markets(limit=15)
    
    if not top_markets:
        logger.error("❌ No perpetual markets found")
        return
    
    # Display results
    report = analyzer.format_market_report(top_markets)
    print(report)
    
    # Export for testing
    exported_data = await analyzer.export_market_ids_for_testing(top_markets)
    
    # Print testing recommendations
    print("\n" + "="*80)
    print("🎯 TESTING RECOMMENDATIONS")
    print("="*80)
    
    testing = exported_data['testing_recommendations']
    if testing['btc_usdt_perp']:
        print(f"BTC/USDT PERP Market ID: {testing['btc_usdt_perp']}")
    if testing['eth_usdt_perp']:
        print(f"ETH/USDT PERP Market ID: {testing['eth_usdt_perp']}")
    
    print(f"\nTop 3 Markets for Multi-Market Testing:")
    for i, market_id in enumerate(testing['top_3_for_testing'], 1):
        market = next(m for m in top_markets if m['market_id'] == market_id)
        print(f"{i}. {market['ticker']:15s} - {market_id}")
    
    print(f"\n✅ Analysis complete! Found {len(top_markets)} active perpetual USDT markets")

if __name__ == "__main__":
    asyncio.run(main())
