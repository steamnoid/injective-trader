# Injective Sniper Bot - Project Overview

## Mission Statement
Stworzenie w pełni autonomicznego bota tradingowego wykorzystującego Injective Protocol DEX do sniper trading na wszystkich parach *-USD z wykorzystaniem zaawansowanych sygnałów i metryk do identyfikacji pozycji o największym potencjale.

## Cele Biznesowe
- **Główny**: Autonomiczny sniper trading na Injective DEX
- **Cel**: Maksymalizacja zysków poprzez wczesne wykrywanie możliwości tradingowych
- **Wynik**: Działający bot tradingowy z paper trading i live trading capabilities

## Kluczowe Komponenty Systemu
1. **WebSocket Manager** - połączenie z Injective Protocol
2. **Market Scanner** - monitorowanie wszystkich par *-USD
3. **Signal Engine** - analiza OHLCV, orderbook i innych metryk
4. **Strategy Engine** - wybór optymalnych pozycji
5. **Risk Manager** - zarządzanie ryzykiem i pozycjami
6. **Paper Trading** - symulacja na danych mainnet
7. **Terminal Dashboard** - interfejs użytkownika (rich library)

## Wymagania Techniczne
- **Język**: Python 3.11+
- **Główna biblioteka**: injective-py
- **WebSocket**: natywne wsparcie w injective-py
- **Dashboard**: rich library (terminal UI)
- **Brak bazy danych**: wszystkie dane z Injective API
- **Optymalizacja**: RAM i CPU optimized
- **Deployment**: Standalone Python application

## Kluczowe Źródła Danych (Injective Protocol)
1. **Market Data Streams** - OHLCV real-time
2. **Orderbook Streams** - depth, spreads, liquidity
3. **Trade Streams** - wykonane transakcje
4. **Account Streams** - pozycje, balanse (paper trading)
5. **Derivative Markets** - leverage data
6. **Market Metadata** - tick size, lot size, fees

## Ograniczenia i Wymagania
- Brak dostępu do danych historycznych orderbook
- Paper trading na danych mainnet (nie testnet)
- Pełna autonomia - zero manual intervention
- Real-time performance requirements
- Memory efficient data structures
- CPU optimized algorithms

## Success Metrics
- **Performance**: <50ms signal processing latency
- **Memory**: <512MB RAM usage sustained
- **CPU**: <25% single core utilization
- **Uptime**: >99.9% connection stability
- **Testing**: >95% unit test coverage
- **Paper Trading**: Profitable simulation results

## Development Strategy
- **Bottom-up TDD**: Start from lowest layer
- **Layer-by-layer**: Complete testing before next layer
- **No API Discovery**: Use official injective-py documentation
- **Real-time Focus**: Optimize for low-latency performance
- **Autonomous Design**: Self-contained, self-managing system

## Risk Management Framework
- Position sizing based on account balance
- Stop-loss mechanisms
- Maximum drawdown limits
- Correlation analysis between positions
- Leverage control and monitoring
- Emergency shutdown procedures

## Monitoring and Observability
- Real-time P&L tracking
- Performance metrics collection
- Error rate monitoring
- Connection health status
- Signal generation statistics
- Trade execution analytics
