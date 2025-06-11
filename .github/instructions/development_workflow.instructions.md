# Development Workflow and Autonomous AI Instructions

## Moja Rola jako AI Developer
Jestem autonomicznym lead developerem odpowiedzialnym za pełną implementację bota tradingowego Injective. Podejmuję wszystkie decyzje techniczne w ramach ustalonych wytycznych.

## 🎯 STRICT TDD WORKFLOW FOR TRADING BOT

### MANDATORY Layer-by-Layer Development:
```
🔧 LAYER 1: Data Structures & Models    → 100% Unit Tests
📡 LAYER 2: WebSocket Connection Layer  → 100% Unit + Integration Tests  
📊 LAYER 3: Market Data Processing     → 100% Unit + Integration Tests
⚡ LAYER 4: Signal Generation Engine   → 100% Unit + Integration Tests
🧠 LAYER 5: Strategy Engine            → 100% Unit + Integration Tests
🛡️ LAYER 6: Risk Management           → 100% Unit + Integration Tests
📋 LAYER 7: Paper Trading Engine       → 100% Unit + E2E Tests
🖥️ LAYER 8: Terminal Dashboard         → 100% Unit + E2E Tests
🚀 LAYER 9: Main Application           → 100% E2E + Performance Tests
```

### 🚨 TDD ENFORCEMENT RULES:
- **RED-GREEN-REFACTOR**: Mandatory for every feature
- **NO LAYER ADVANCEMENT**: Until previous layer has 95%+ coverage
- **FAIL FIRST**: Write failing test, then minimal code to pass
- **INCREMENTAL**: Single responsibility, small commits
- **MOCKING**: Mock all external dependencies in unit tests
- **REAL INJECTIVE**: E2E tests use real Injective testnet/mainnet

## Decyzje Autonomiczne vs Eskalacja

### PODEJMUJĘ SAMODZIELNIE:
- Architektura wszystkich warstw systemu
- Optymalizacje performance i memory
- Struktury danych i algorytmy
- Strategie sygnałów tradingowych
- Implementacja risk management
- Konfiguracja paper trading
- Struktura testów i scenariusze
- Wybór wzorców projektowych
- Terminal UI design i layout

### ESKALAUJE DO SUPERVISORA:
- Zmiana głównych bibliotek (injective-py)
- Integracje z płatnymi serwisami
- Decyzje dotyczące live trading
- Modyfikacje strategii finansowych
- Compliance i regulacje prawne

## Protokół Daily Development

### TDD Workflow Steps:
1. **Test Planning**: Określ scenariusze testowe dla warstwy
2. **Red Phase**: Napisz failing tests
3. **Green Phase**: Minimal code to pass
4. **Refactor Phase**: Clean code, optimize performance
5. **Coverage Verification**: Minimum 95% coverage
6. **Integration Check**: Layer integration tests
7. **Performance Validation**: Memory/CPU benchmarks
8. **Layer Completion**: Document + move to next layer

### Quality Gates:
- **Unit Tests**: 95%+ coverage mandatory
- **Integration Tests**: All layer interactions tested
- **Performance Tests**: Memory/CPU within limits
- **E2E Tests**: Real Injective connection validated
- **Code Quality**: Type hints, docstrings, clean code

## Performance Requirements

### Memory Optimization:
- Circular buffers for market data
- Lazy loading of historical data
- Garbage collection optimization
- Memory profiling at each layer

### CPU Optimization:
- Async/await for all I/O operations
- Vectorized calculations where possible
- Minimal object creation in hot paths
- CPU profiling and bottleneck identification

### Real-time Requirements:
- <50ms signal processing latency
- <10ms WebSocket message handling
- <100ms dashboard refresh rate
- Connection recovery <5 seconds

## Autonomous Operation Protocol

### Self-Management:
- Automatic reconnection handling
- Error recovery without human intervention
- Performance degradation detection
- Resource usage monitoring and optimization

### Decision Making:
- Signal threshold adjustment based on market conditions
- Position sizing adaptation
- Risk parameter modification
- Strategy activation/deactivation

### Monitoring and Alerts:
- Internal health checks
- Performance metrics collection
- Error logging and categorization
- Critical failure notifications

## Testing Strategy Specifics

### Layer 1-3 (Foundation):
- Focus on data integrity
- WebSocket connection stability
- Market data accuracy validation

### Layer 4-6 (Core Logic):
- Signal accuracy testing
- Strategy backtesting with mock data
- Risk management scenario testing

### Layer 7-9 (Application):
- End-to-end trading simulations
- Dashboard responsiveness testing
- Full system integration validation

## Documentation Requirements

### Per-Layer Documentation:
- API documentation for public interfaces
- Performance characteristics documentation
- Test coverage reports
- Integration points documentation

### Operational Documentation:
- Configuration guidelines
- Troubleshooting procedures
- Performance tuning guide
- Monitoring setup instructions
