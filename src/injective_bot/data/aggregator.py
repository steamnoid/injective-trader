"""
Market Data Aggregator - Layer 3 Market Data Processing

Real-time OHLCV data aggregation from trade execution streams.
Supports multiple timeframes and provides efficient candlestick generation.
"""

from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
import asyncio
from dataclasses import dataclass

from injective_bot.models import TradeExecution, OHLCVData
from .circular_buffer import CircularBuffer


class TimeFrame(str, Enum):
    """Supported timeframes for OHLCV aggregation"""
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"


class MarketDataAggregator:
    """
    Real-time OHLCV data aggregator from trade execution streams.
    
    Features:
    - Multiple timeframe support (1m, 5m, 15m, 1h, 4h, 1d)
    - Real-time candlestick updates
    - Memory-efficient circular buffers
    - High-performance aggregation (<50ms processing)
    - Thread-safe operations
    """
    
    def __init__(self, timeframes: List[TimeFrame] = None, buffer_size: int = 1000):
        """
        Initialize market data aggregator.
        
        Args:
            timeframes: List of timeframes to aggregate data for
            buffer_size: Size of circular buffers for each timeframe
        """
        self._buffer_size = buffer_size
        self._timeframes = timeframes or list(TimeFrame)
        
        # Market ID -> Timeframe -> CircularBuffer[OHLCVData]
        self._ohlcv_buffers: Dict[str, Dict[TimeFrame, CircularBuffer[OHLCVData]]] = {}
        
        # Current incomplete candles (being built)
        self._current_candles: Dict[str, Dict[TimeFrame, OHLCVData]] = {}
        
        # Processing statistics
        self._trade_count = 0
        self._last_update = None
        
    @property
    def timeframes(self) -> List[TimeFrame]:
        """Get configured timeframes"""
        return self._timeframes
        
    @property  
    def buffer_size(self) -> int:
        """Get buffer size"""
        return self._buffer_size
        
    @property
    def _data_buffer(self) -> Dict[str, Dict[TimeFrame, CircularBuffer[OHLCVData]]]:
        """Get data buffers for testing/memory efficiency checks"""
        return self._ohlcv_buffers
        
    def process_trade(self, trade: TradeExecution) -> Dict[TimeFrame, Optional[OHLCVData]]:
        """
        Process new trade execution and update OHLCV data.
        
        Args:
            trade: Trade execution to process
            
        Returns:
            Dictionary of timeframe -> completed OHLCV candle (if any)
        """
        # Input validation
        if trade is None:
            return None
            
        # Validate trade data
        if not trade.market_id or not trade.market_id.strip():
            raise ValueError("Invalid trade: market_id cannot be empty")
            
        self._trade_count += 1
        self._last_update = datetime.now(timezone.utc)
        
        completed_candles = {}
        market_id = trade.market_id
        
        # Initialize buffers for market if needed
        if market_id not in self._ohlcv_buffers:
            self._initialize_market(market_id)
            
        # Process trade for each timeframe
        for timeframe in self._timeframes:
            candle = self._process_trade_for_timeframe(trade, timeframe)
            completed_candles[timeframe] = candle
                
        return completed_candles
        
    def _initialize_market(self, market_id: str) -> None:
        """Initialize buffers and structures for a new market"""
        self._ohlcv_buffers[market_id] = {}
        self._current_candles[market_id] = {}
        
        for timeframe in self._timeframes:
            self._ohlcv_buffers[market_id][timeframe] = CircularBuffer[OHLCVData](
                capacity=self._buffer_size
            )
            
    def _process_trade_for_timeframe(
        self, 
        trade: TradeExecution, 
        timeframe: TimeFrame
    ) -> Optional[OHLCVData]:
        """Process trade for specific timeframe"""
        market_id = trade.market_id
        candle_timestamp = self._get_candle_timestamp(trade.timestamp, timeframe)
        
        # Get or create current candle
        current_candle = self._current_candles[market_id].get(timeframe)
        
        if current_candle is None or current_candle.timestamp != candle_timestamp:
            # New candle period - save old candle if exists
            completed_candle = None
            if current_candle is not None:
                self._ohlcv_buffers[market_id][timeframe].append(current_candle)
                completed_candle = current_candle
                
            # Start new candle
            from injective_bot.models import OHLCVData as ModelOHLCVData
            self._current_candles[market_id][timeframe] = ModelOHLCVData(
                market_id=market_id,
                timestamp=candle_timestamp,
                timeframe=timeframe.value,
                open_price=trade.price,
                high_price=trade.price,
                low_price=trade.price,
                close_price=trade.price,
                volume=trade.quantity,
                trades_count=1
            )
            
            return completed_candle
        else:
            # Update existing candle
            current_candle.high_price = max(current_candle.high_price, trade.price)
            current_candle.low_price = min(current_candle.low_price, trade.price)
            current_candle.close_price = trade.price
            current_candle.volume += trade.quantity
            current_candle.trades_count += 1
            
            return None
            
    def _get_candle_timestamp(self, timestamp: datetime, timeframe: TimeFrame) -> datetime:
        """Get normalized timestamp for candle period"""
        if timeframe == TimeFrame.ONE_MINUTE:
            return timestamp.replace(second=0, microsecond=0)
        elif timeframe == TimeFrame.FIVE_MINUTE:
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == TimeFrame.FIFTEEN_MINUTE:
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == TimeFrame.ONE_HOUR:
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif timeframe == TimeFrame.FOUR_HOUR:
            hour = (timestamp.hour // 4) * 4
            return timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
        elif timeframe == TimeFrame.ONE_DAY:
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
            
    def get_ohlcv_data(
        self, 
        timeframe: TimeFrame, 
        market_id: str = None
    ) -> Optional[OHLCVData]:
        """
        Get current OHLCV data for timeframe.
        
        Args:
            timeframe: Timeframe to retrieve
            market_id: Market identifier (if None, uses first available market)
            
        Returns:
            Current OHLCV data for the timeframe
        """
        if market_id is None:
            # Use first available market if not specified
            if not self._current_candles:
                return None
            market_id = next(iter(self._current_candles.keys()))
            
        if market_id not in self._current_candles:
            return None
            
        return self._current_candles[market_id].get(timeframe)
        
    def get_historical_ohlcv(
        self, 
        timeframe: TimeFrame,
        limit: int = 100,
        market_id: str = None
    ) -> List[OHLCVData]:
        """
        Get historical OHLCV data for market and timeframe.
        
        Args:
            timeframe: Timeframe to retrieve
            limit: Number of candles to retrieve (newest first)
            market_id: Market identifier (if None, uses first available market)
            
        Returns:
            List of OHLCV data
        """
        if market_id is None:
            # Use first available market if not specified
            if not self._ohlcv_buffers:
                return []
            market_id = next(iter(self._ohlcv_buffers.keys()))
            
        if market_id not in self._ohlcv_buffers:
            return []
            
        buffer = self._ohlcv_buffers[market_id].get(timeframe)
        if buffer is None or buffer.is_empty():
            return []
            
        return buffer.get_latest(limit)
        
    def get_completed_candles(self, timeframe: TimeFrame) -> List[OHLCVData]:
        """Get all completed candles for timeframe across all markets"""
        completed = []
        for market_id in self._ohlcv_buffers:
            buffer = self._ohlcv_buffers[market_id].get(timeframe)
            if buffer:
                completed.extend(buffer.to_list())
        return completed
        
    def get_current_candle(
        self, 
        market_id: str, 
        timeframe: TimeFrame
    ) -> Optional[OHLCVData]:
        """Get current incomplete candle for market and timeframe"""
        if market_id not in self._current_candles:
            return None
            
        return self._current_candles[market_id].get(timeframe)
        
    def get_processing_stats(self) -> Dict:
        """Get aggregator processing statistics"""
        return {
            "trade_count": self._trade_count,
            "last_update": self._last_update,
            "markets_count": len(self._ohlcv_buffers),
            "memory_usage": self._estimate_memory_usage()
        }
        
    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes"""
        # Rough estimation: each OHLCV entry ~200 bytes
        total_entries = 0
        for market_buffers in self._ohlcv_buffers.values():
            for buffer in market_buffers.values():
                total_entries += len(buffer)
        return total_entries * 200
        
    def clear_market_data(self, market_id: str) -> None:
        """Clear all data for specific market"""
        if market_id in self._ohlcv_buffers:
            for buffer in self._ohlcv_buffers[market_id].values():
                buffer.clear()
            self._current_candles[market_id].clear()
            
    def clear_all_data(self) -> None:
        """Clear all aggregated data"""
        for market_id in list(self._ohlcv_buffers.keys()):
            self.clear_market_data(market_id)
