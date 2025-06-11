# Data Sources Integration Instructions

## Źródła Danych Injective Protocol

### Jedyne Źródło Danych: Injective Protocol DEX
**Philosophy**: Zero external dependencies - all data from Injective ecosystem

### Główne Strumienie Danych

#### 1. **Market Data Streams (Priorytet #1)**
- **Endpoint**: Injective Chain WebSocket
- **Data**: Real-time OHLCV dla wszystkich par *-USD
- **Format**: Protobuf messages via injective-py
- **Frequency**: Real-time tick data
- **Critical dla**: Signal generation, strategy decisions

#### 2. **Orderbook Streams (Priorytet #1)**
- **Endpoint**: Injective Chain WebSocket  
- **Data**: Real-time order book depth, spreads
- **Format**: Protobuf orderbook snapshots
- **Frequency**: Real-time updates
- **Critical dla**: Liquidity analysis, entry/exit timing

#### 3. **Trade Streams (Priorytet #2)**
- **Endpoint**: Injective Chain WebSocket
- **Data**: Executed trades, volume, price impact
- **Format**: Trade execution messages
- **Frequency**: Real-time trade notifications
- **Critical dla**: Market momentum, volume analysis

#### 4. **Account Streams (Paper Trading)**
- **Endpoint**: Injective Chain Account Stream
- **Data**: Positions, balances, orders (simulated)
- **Format**: Account state messages
- **Frequency**: Real-time account updates
- **Critical dla**: Paper trading simulation, P&L tracking

#### 5. **Derivative Markets Data**
- **Endpoint**: Injective Derivative Markets API
- **Data**: Leverage information, funding rates
- **Format**: Market metadata messages
- **Frequency**: Periodic updates
- **Critical dla**: Leverage strategies, cost analysis

#### 6. **Market Metadata**
- **Endpoint**: Injective Chain Market Stream
- **Data**: Tick sizes, lot sizes, trading fees
- **Format**: Market configuration messages
- **Frequency**: On market changes
- **Critical dla**: Order sizing, cost calculations

## Implementacja Connectorów

### Wzorzec Unified Injective Connector
**Philosophy**: Single, robust connector to Injective Protocol z multiple data stream management

### Wymagania Implementacyjne

#### WebSocket Management:
- **Connection Pooling**: Efficient multi-stream connections
- **Automatic Reconnection**: Exponential backoff retry logic
- **Message Routing**: Stream-specific message handling
- **Rate Limiting**: Respect Injective API limits
- **Error Recovery**: Graceful handling of connection failures

#### Data Processing:
- **Real-time Processing**: <50ms message processing
- **Data Validation**: Comprehensive data quality checks
- **Memory Management**: Circular buffers dla historical data
- **Stream Synchronization**: Coordinate multiple data streams
- **Deduplication**: Handle duplicate messages

#### Performance Optimization:
- **Memory Efficiency**: Minimal object creation
- **CPU Optimization**: Vectorized calculations
- **Latency Minimization**: Direct protobuf processing
- **Resource Management**: Controlled memory footprint
- **Garbage Collection**: Optimized GC behavior

## Walidacja Danych (KRYTYCZNA)

### Market Data Validation:
- **Price Range Validation**: Reasonable price movements
- **Volume Validation**: Realistic volume patterns
- **Timestamp Validation**: Chronological data order
- **Completeness Check**: No missing critical data
- **Consistency Check**: Cross-stream data correlation

### Orderbook Validation:
- **Spread Validation**: Reasonable bid-ask spreads
- **Depth Validation**: Sufficient liquidity depth
- **Price Level Validation**: Proper price level ordering
- **Update Validation**: Consistent orderbook updates
- **Arbitrage Detection**: Cross-market opportunities

### Trade Data Validation:
- **Execution Validation**: Valid trade executions
- **Price Validation**: Within orderbook bounds
- **Volume Validation**: Realistic trade sizes
- **Frequency Validation**: Normal trading patterns
- **Market Impact Validation**: Expected price impact

## Cache Strategy (Memory-Only)

### Multi-Level Caching:
- **L1 Cache**: Current market state (immediate access)
- **L2 Cache**: Recent historical data (circular buffers)
- **L3 Cache**: Aggregated signals (computed metrics)

### Cache TTL Strategy:
- **Market Data**: Real-time (no TTL)
- **Orderbook**: Real-time snapshots
- **Signals**: 1-second computed cache
- **Metadata**: 1-hour cache dla stable data

### Memory Management:
- **Fixed Size Buffers**: Prevent memory growth
- **Ring Buffers**: Efficient historical data storage
- **Object Pooling**: Reuse objects dla high-frequency data
- **Weak References**: Prevent memory leaks
- **Periodic Cleanup**: Automated memory management

## Error Handling & Resilience

### Connection Resilience:
- **Circuit Breaker Pattern**: Prevent cascade failures
- **Exponential Backoff**: Intelligent retry logic
- **Health Monitoring**: Connection quality assessment
- **Fallback Mechanisms**: Graceful degradation
- **Emergency Shutdown**: Critical failure protection

### Data Quality Assurance:
- **Real-time Validation**: Immediate data quality checks
- **Anomaly Detection**: Unusual data pattern identification
- **Data Recovery**: Gap filling mechanisms
- **Quality Metrics**: Continuous data quality monitoring
- **Alert System**: Critical data quality notifications

## Performance Targets

### Latency Requirements:
- **Market Data Processing**: <10ms per message
- **Signal Generation**: <50ms end-to-end
- **Order Decision**: <100ms from signal to decision
- **Dashboard Update**: <100ms refresh rate

### Throughput Requirements:
- **Message Processing**: 10,000+ messages/second
- **Concurrent Streams**: 50+ simultaneous market streams
- **Memory Usage**: <512MB total footprint
- **CPU Usage**: <25% single core utilization

### Reliability Requirements:
- **Connection Uptime**: >99.9%
- **Data Accuracy**: >99.99%
- **Recovery Time**: <5 seconds
- **Error Rate**: <0.1%

## Monitoring & Observability

### Real-time Metrics:
- **Connection Health**: WebSocket connection status
- **Data Flow Rate**: Messages per second per stream
- **Processing Latency**: End-to-end processing time
- **Memory Usage**: Real-time memory consumption
- **Error Rates**: Connection and processing errors

### Data Quality Metrics:
- **Message Completeness**: Missing data detection
- **Data Freshness**: Age of latest data
- **Validation Failures**: Data quality issues
- **Stream Synchronization**: Cross-stream timing
- **Recovery Success**: Error recovery effectiveness
