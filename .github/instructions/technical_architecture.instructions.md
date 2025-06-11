# Technical Architecture Instructions

## Stack Technologiczny (OBOWIĄZKOWY)
- **Język**: Python 3.11+
- **Główna biblioteka**: injective-py (oficjalna biblioteka Injective Protocol)
- **Async Framework**: asyncio (native Python)
- **Terminal UI**: rich library
- **Testing**: pytest + pytest-asyncio + pytest-mock
- **Type Checking**: mypy z strict mode
- **Code Quality**: black, isort, flake8, pre-commit hooks
- **Profiling**: memory_profiler, cProfile dla optymalizacji

## Wzorce Architektoniczne (WYMAGANE)
- **Layered Architecture**: 9-layer stack z clear separation
- **Observer Pattern**: Market data notifications
- **Strategy Pattern**: Pluggable trading strategies  
- **State Machine**: Connection and trading state management
- **Circuit Breaker**: Resilience dla WebSocket connections
- **Producer-Consumer**: Async data processing pipelines
- **Singleton Pattern**: Application configuration and state

## Struktura Projektu
```
injective-sniper-bot/
├── .github/
│   └── injective_instructions/    # Instrukcje projektu
├── docs/                          # Dokumentacja
├── src/
│   └── injective_bot/
│       ├── __init__.py
│       ├── main.py               # Entry point
│       ├── config/               # Konfiguracja
│       ├── models/               # Layer 1: Data models
│       ├── connection/           # Layer 2: WebSocket management
│       ├── data/                 # Layer 3: Market data processing
│       ├── signals/              # Layer 4: Signal generation
│       ├── strategies/           # Layer 5: Trading strategies
│       ├── risk/                 # Layer 6: Risk management
│       ├── trading/              # Layer 7: Paper trading engine
│       ├── dashboard/            # Layer 8: Terminal UI
│       └── utils/                # Utilities i helpers
├── tests/                        # Comprehensive test suite
│   ├── unit/                    # Unit tests per layer
│   ├── integration/             # Cross-layer integration tests
│   ├── e2e/                     # End-to-end real trading tests
│   └── performance/             # Performance benchmarks
├── benchmarks/                   # Performance testing
├── requirements/                 # Dependencies
└── README.md
```

## Memory Architecture (KRYTYCZNE)
- **Circular Buffers**: OHLCV data z fixed size
- **Ring Buffers**: Orderbook snapshots
- **Memory Pools**: Object reuse dla high-frequency data
- **Lazy Loading**: On-demand data retrieval
- **Weak References**: Avoid memory leaks
- **Garbage Collection Tuning**: Optimized GC settings

## Performance Architecture
- **Async/Await**: All I/O operations non-blocking
- **Vectorized Operations**: NumPy dla calculations
- **Compiled Extensions**: Numba dla critical paths
- **Connection Pooling**: Efficient WebSocket management
- **Batch Processing**: Grouped operations where possible
- **Zero-Copy Operations**: Minimize data copying

## Data Flow Architecture
```
Injective WebSocket → Connection Manager → Data Processor → Signal Engine → Strategy Engine → Risk Manager → Paper Trading → Dashboard
```

## Configuration Management
- **Environment Variables**: Sensitive configuration
- **YAML Files**: Strategy parameters i settings
- **Runtime Configuration**: Dynamic parameter adjustment
- **Validation**: Pydantic models dla all config
- **Hot Reload**: Configuration updates without restart

## Error Handling Architecture
- **Graceful Degradation**: Partial functionality w przypadku błędów
- **Automatic Recovery**: Self-healing mechanisms
- **Circuit Breakers**: Prevent cascade failures
- **Retry Logic**: Exponential backoff dla reconnections
- **Error Classification**: Different handling dla different error types

## State Management
- **Application State**: Global state management
- **Connection State**: WebSocket connection status
- **Trading State**: Current positions i orders
- **Market State**: Current market conditions
- **Risk State**: Portfolio risk metrics

## Monitoring Architecture
- **Health Checks**: Component health monitoring
- **Metrics Collection**: Performance metrics gathering
- **Alerting**: Critical condition notifications
- **Logging**: Structured logging z context
- **Profiling**: Real-time performance monitoring

## Security Architecture
- **API Key Management**: Secure credential handling
- **Connection Security**: Encrypted WebSocket connections
- **Input Validation**: All input data validated
- **Error Masking**: Sensitive information protection
- **Audit Logging**: Security event logging

## Scalability Architecture
- **Horizontal Scaling**: Multiple bot instances support
- **Load Balancing**: Market monitoring distribution
- **Resource Isolation**: Component resource limits
- **Adaptive Algorithms**: Self-tuning parameters
- **Performance Monitoring**: Resource usage tracking

## Testing Architecture
- **Test Doubles**: Sophisticated mocking dla external dependencies
- **Test Data Management**: Realistic market data fixtures
- **Test Environment**: Isolated testing environment
- **Performance Testing**: Load i stress testing
- **Integration Testing**: Real Injective testnet integration
