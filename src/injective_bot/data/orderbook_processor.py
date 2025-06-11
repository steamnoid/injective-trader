"""
Orderbook Processor - Layer 3 Market Data Processing

Real-time orderbook analysis including depth calculation, spread analysis,
and liquidity metrics for trading signal generation.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass

from injective_bot.models import OrderbookSnapshot, PriceLevel


@dataclass
class MarketDepthAnalysis:
    """Market depth analysis results"""
    market_id: str
    timestamp: datetime
    total_bid_volume: Decimal
    total_ask_volume: Decimal
    bid_ask_ratio: Decimal  # bid_volume / ask_volume
    volume_imbalance: Decimal  # (bid_volume - ask_volume) / (bid_volume + ask_volume)
    depth_levels: int
    liquidity_5_percent: Decimal  # Liquidity within 5% of mid price
    liquidity_10_percent: Decimal  # Liquidity within 10% of mid price


@dataclass  
class SpreadAnalysis:
    """Bid-ask spread analysis results"""
    market_id: str
    timestamp: datetime
    bid_price: Decimal
    ask_price: Decimal
    absolute_spread: Decimal
    percentage_spread: Decimal
    mid_price: Decimal
    weighted_mid_price: Decimal  # Volume-weighted mid price


class OrderbookProcessor:
    """
    Real-time orderbook processor for market analysis.
    
    Features:
    - Orderbook depth analysis
    - Bid-ask spread calculations  
    - Volume-weighted average price (VWAP) calculations
    - Market liquidity metrics
    - Imbalance detection
    - High-performance processing (<50ms per snapshot)
    """
    
    def __init__(self, depth_levels: int = 10, spread_threshold: Decimal = Decimal("0.01")):
        """
        Initialize orderbook processor.
        
        Args:
            depth_levels: Number of price levels to analyze for depth
            spread_threshold: Threshold for spread classification
        """
        self.depth_levels = depth_levels
        self.spread_threshold = spread_threshold
        self._processed_count = 0
        self._last_update = None
        
    def calculate_spread(self, orderbook: OrderbookSnapshot) -> SpreadAnalysis:
        """
        Calculate bid-ask spread analysis.
        
        Args:
            orderbook: Orderbook snapshot to analyze
            
        Returns:
            SpreadAnalysis with spread metrics
        """
        if not orderbook.bids and not orderbook.asks:
            return SpreadAnalysis(
                market_id=orderbook.market_id,
                timestamp=orderbook.timestamp,
                bid_price=Decimal("0"),
                ask_price=Decimal("0"),
                absolute_spread=Decimal("0"),
                percentage_spread=Decimal("0"),
                mid_price=Decimal("0"),
                weighted_mid_price=Decimal("0")
            )
            
        if not orderbook.bids or not orderbook.asks:
            # Handle one-sided orderbook
            best_bid = orderbook.bids[0].price if orderbook.bids else Decimal("0")
            best_ask = orderbook.asks[0].price if orderbook.asks else Decimal("0")
            return SpreadAnalysis(
                market_id=orderbook.market_id,
                timestamp=orderbook.timestamp,
                bid_price=best_bid,
                ask_price=best_ask,
                absolute_spread=Decimal("0"),
                percentage_spread=Decimal("0"),
                mid_price=Decimal("0"),
                weighted_mid_price=Decimal("0")
            )
            
        best_bid = orderbook.bids[0].price
        best_ask = orderbook.asks[0].price
        
        absolute_spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        percentage_spread = (absolute_spread / mid_price) * 100 if mid_price > 0 else Decimal("0")
        
        # Calculate volume-weighted mid price
        weighted_mid_price = self._calculate_weighted_mid_price(orderbook)
        
        return SpreadAnalysis(
            market_id=orderbook.market_id,
            timestamp=orderbook.timestamp,
            bid_price=best_bid,
            ask_price=best_ask,
            absolute_spread=absolute_spread,
            percentage_spread=percentage_spread,
            mid_price=mid_price,
            weighted_mid_price=weighted_mid_price
        )
        
    def analyze_market_depth(self, orderbook: OrderbookSnapshot) -> MarketDepthAnalysis:
        """
        Analyze orderbook depth and liquidity.
        
        Args:
            orderbook: Orderbook snapshot to analyze
            
        Returns:
            MarketDepthAnalysis with depth metrics
        """
        total_bid_volume = sum(level.quantity for level in orderbook.bids)
        total_ask_volume = sum(level.quantity for level in orderbook.asks)
        
        # Calculate bid/ask ratio
        if total_ask_volume > 0:
            bid_ask_ratio = total_bid_volume / total_ask_volume
        elif total_bid_volume > 0:
            bid_ask_ratio = Decimal("inf")
        else:
            bid_ask_ratio = Decimal("0")
        
        # Calculate volume imbalance
        total_volume = total_bid_volume + total_ask_volume
        if total_volume > 0:
            volume_imbalance = (total_bid_volume - total_ask_volume) / total_volume
        else:
            volume_imbalance = Decimal("0")
            
        # Calculate liquidity within price ranges
        mid_price = self._calculate_mid_price(orderbook)
        liquidity_5_percent = Decimal("0")
        liquidity_10_percent = Decimal("0")
        
        if mid_price:
            price_5_percent = mid_price * Decimal("0.05")
            price_10_percent = mid_price * Decimal("0.10")
            
            # Bid side liquidity
            for level in orderbook.bids:
                if mid_price - level.price <= price_10_percent:
                    liquidity_10_percent += level.quantity
                    if mid_price - level.price <= price_5_percent:
                        liquidity_5_percent += level.quantity
                        
            # Ask side liquidity  
            for level in orderbook.asks:
                if level.price - mid_price <= price_10_percent:
                    liquidity_10_percent += level.quantity
                    if level.price - mid_price <= price_5_percent:
                        liquidity_5_percent += level.quantity
        
        return MarketDepthAnalysis(
            market_id=orderbook.market_id,
            timestamp=orderbook.timestamp,
            total_bid_volume=total_bid_volume,
            total_ask_volume=total_ask_volume,
            bid_ask_ratio=bid_ask_ratio,
            volume_imbalance=volume_imbalance,
            depth_levels=len(orderbook.bids) + len(orderbook.asks),
            liquidity_5_percent=liquidity_5_percent,
            liquidity_10_percent=liquidity_10_percent
        )
        
    def calculate_vwap(self, price_levels: List[PriceLevel], depth: int = 5) -> Decimal:
        """
        Calculate Volume-Weighted Average Price for given price levels.
        
        Args:
            price_levels: List of price levels
            depth: Number of price levels to include
            
        Returns:
            VWAP as Decimal
        """
        if not price_levels:
            return Decimal("0")
            
        levels = price_levels[:depth]
        total_value = sum(level.price * level.quantity for level in levels)
        total_volume = sum(level.quantity for level in levels)
        
        if total_volume > 0:
            return total_value / total_volume
        else:
            return Decimal("0")
            
    def aggregate_price_levels(self, price_levels: List[PriceLevel], tick_size: Decimal) -> List[PriceLevel]:
        """
        Aggregate price levels within tick size ranges.
        
        Args:
            price_levels: List of price levels to aggregate
            tick_size: Minimum price increment for aggregation
            
        Returns:
            List of aggregated price levels
        """
        if not price_levels:
            return []
            
        aggregated = {}
        
        for level in price_levels:
            # Round price to tick size
            tick_price = (level.price // tick_size) * tick_size
            
            if tick_price in aggregated:
                aggregated[tick_price] += level.quantity
            else:
                aggregated[tick_price] = level.quantity
                
        # Convert back to PriceLevel objects
        result = [PriceLevel(price=price, quantity=quantity) 
                 for price, quantity in aggregated.items()]
        
        # Sort by price (maintain original order direction)
        if price_levels and len(price_levels) > 1:
            if price_levels[0].price > price_levels[1].price:
                # Descending (bids)
                result.sort(key=lambda x: x.price, reverse=True)
            else:
                # Ascending (asks)  
                result.sort(key=lambda x: x.price)
                
        return result
        
    def calculate_imbalance(self, orderbook: OrderbookSnapshot) -> Decimal:
        """
        Calculate orderbook volume imbalance.
        
        Args:
            orderbook: Orderbook snapshot
            
        Returns:
            Imbalance ratio between -1 and 1
        """
        total_bid_volume = sum(level.quantity for level in orderbook.bids)
        total_ask_volume = sum(level.quantity for level in orderbook.asks)
        
        total_volume = total_bid_volume + total_ask_volume
        if total_volume > 0:
            return (total_bid_volume - total_ask_volume) / total_volume
        else:
            return Decimal("0")
            
    def calculate_depth_percentages(self, orderbook: OrderbookSnapshot) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate liquidity depth at various percentage levels.
        
        Args:
            orderbook: Orderbook snapshot
            
        Returns:
            Dictionary with depth percentages and liquidity data
        """
        mid_price = self._calculate_mid_price(orderbook)
        if not mid_price:
            return {
                "1%": {"price_range": Decimal("0"), "volume": Decimal("0")},
                "5%": {"price_range": Decimal("0"), "volume": Decimal("0")},
                "10%": {"price_range": Decimal("0"), "volume": Decimal("0")}
            }
            
        percentages = [1, 5, 10]
        result = {}
        
        for pct in percentages:
            price_range = mid_price * Decimal(str(pct / 100))
            volume = Decimal("0")
            
            # Bid side liquidity
            for level in orderbook.bids:
                if mid_price - level.price <= price_range:
                    volume += level.quantity
                    
            # Ask side liquidity
            for level in orderbook.asks:
                if level.price - mid_price <= price_range:
                    volume += level.quantity
                    
            result[f"{pct}%"] = {
                "price_range": price_range,
                "volume": volume
            }
            
        return result
        
    def classify_spread(self, spread_analysis: SpreadAnalysis) -> str:
        """
        Classify spread as tight, normal, or wide.
        
        Args:
            spread_analysis: Spread analysis results
            
        Returns:
            Classification string: "tight", "normal", or "wide"
        """
        if spread_analysis.percentage_spread <= self.spread_threshold * 50:  # 0.5% for 1% threshold
            return "tight"
        elif spread_analysis.percentage_spread <= self.spread_threshold * 100:  # 1% for 1% threshold
            return "normal"
        else:
            return "wide"
        
    def _calculate_mid_price(self, orderbook: OrderbookSnapshot) -> Optional[Decimal]:
        """Calculate mid price from best bid/ask"""
        if orderbook.bids and orderbook.asks:
            return (orderbook.bids[0].price + orderbook.asks[0].price) / 2
        return None
        
    def _calculate_weighted_mid_price(self, orderbook: OrderbookSnapshot) -> Decimal:
        """Calculate volume-weighted mid price"""
        if not orderbook.bids or not orderbook.asks:
            return Decimal("0")
            
        # Use top 3 levels for VWAP calculation
        bid_levels = orderbook.bids[:3]
        ask_levels = orderbook.asks[:3]
        
        total_bid_value = sum(level.price * level.quantity for level in bid_levels)
        total_bid_volume = sum(level.quantity for level in bid_levels)
        
        total_ask_value = sum(level.price * level.quantity for level in ask_levels)
        total_ask_volume = sum(level.quantity for level in ask_levels)
        
        total_value = total_bid_value + total_ask_value
        total_volume = total_bid_volume + total_ask_volume
        
        if total_volume > 0:
            return total_value / total_volume
        else:
            return (orderbook.bids[0].price + orderbook.asks[0].price) / 2
            
    def get_processing_stats(self) -> Dict:
        """Get processor statistics"""
        return {
            "processed_count": self._processed_count,
            "last_update": self._last_update
        }
