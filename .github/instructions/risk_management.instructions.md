# Risk Management Framework Instructions

## 🛡️ COMPREHENSIVE RISK MANAGEMENT STRATEGY

### Philosophy: Capital Preservation First
**Priority**: Ochrona kapitału ma absolutny priorytet nad zyskami. Lepiej stracić potencjalny zysk niż rzeczywisty kapitał.

## Multi-Layer Risk Architecture

### Layer 1: Position-Level Risk
- **Position Sizing**: Kelly criterion z conservative multiplier
- **Stop-Loss Management**: Dynamic stop-loss adjustment
- **Take-Profit Logic**: Scaled profit taking
- **Time-Based Exits**: Maximum position holding time
- **Correlation Limits**: Position correlation restrictions

### Layer 2: Portfolio-Level Risk
- **Maximum Exposure**: Total portfolio exposure limits
- **Sector Diversification**: Avoid concentration w similar assets
- **Currency Exposure**: USD pair concentration management
- **Leverage Limits**: Portfolio-wide leverage restrictions
- **Drawdown Protection**: Maximum portfolio drawdown limits

### Layer 3: System-Level Risk
- **Operational Risk**: System failure protection
- **Connectivity Risk**: WebSocket disconnection handling
- **Market Risk**: Extreme market condition protection
- **Liquidity Risk**: Market liquidity assessment
- **Counterparty Risk**: Injective Protocol risk assessment

## Position Risk Management

### Position Sizing Framework:
- **Base Position Size**: 1-2% of portfolio per position
- **Signal Confidence Scaling**: Higher confidence = larger size
- **Volatility Adjustment**: Lower size w high volatility
- **Correlation Adjustment**: Reduced size dla correlated positions
- **Maximum Single Position**: Never exceed 5% of portfolio

### Dynamic Stop-Loss System:
- **Initial Stop-Loss**: 2-3% below entry price
- **Trailing Stop-Loss**: Dynamic adjustment with profit
- **Volatility-Based Stops**: ATR-based stop placement
- **Time-Based Stops**: Maximum holding period limits
- **Technical Stop-Loss**: Support/resistance level stops

### Leverage Risk Control:
- **Maximum Leverage**: 5:1 leverage limit
- **Confidence-Based Leverage**: Higher confidence = higher leverage allowed
- **Volatility-Adjusted Leverage**: Reduced leverage w high volatility
- **Portfolio Leverage**: Total portfolio leverage monitoring
- **Margin Safety**: Maintain 50%+ margin buffer

## Portfolio Risk Management

### Diversification Requirements:
- **Maximum Correlation**: No more than 70% correlation between positions
- **Asset Class Limits**: Maximum exposure per asset category
- **Time Diversification**: Spread entries across time
- **Strategy Diversification**: Multiple strategy deployment
- **Market Condition Diversification**: Strategies dla different regimes

### Risk Limits and Controls:
- **Daily Loss Limit**: Maximum 5% portfolio loss per day
- **Weekly Loss Limit**: Maximum 10% portfolio loss per week
- **Monthly Loss Limit**: Maximum 15% portfolio loss per month
- **Maximum Drawdown**: Stop trading at 20% portfolio drawdown
- **Consecutive Loss Limit**: Stop after 5 consecutive losing trades

### Position Correlation Management:
- **Real-time Correlation Monitoring**: Continuous correlation calculation
- **Correlation Limits**: Maximum correlation between positions
- **Diversification Scoring**: Portfolio diversification measurement
- **Risk Concentration**: Avoid risk concentration w single factors
- **Dynamic Rebalancing**: Automatic position adjustment dla correlation

## Emergency Risk Procedures

### Emergency Shutdown Triggers:
- **Extreme Market Volatility**: VIX-equivalent > threshold
- **System Performance Degradation**: Latency > critical threshold
- **Connection Instability**: WebSocket disconnections > limit
- **Unusual P&L Patterns**: Unexpected loss patterns
- **External Market Events**: Major market disruptions

### Emergency Response Procedures:
- **Immediate Position Closure**: Close all positions within 60 seconds
- **Risk Assessment**: Evaluate portfolio risk exposure
- **System Diagnostics**: Check all system components
- **Market Analysis**: Assess market conditions
- **Recovery Planning**: Plan for safe system restart

### Risk Override Mechanisms:
- **Manual Override**: Human intervention capability
- **Risk Parameter Adjustment**: Real-time risk parameter changes
- **Strategy Suspension**: Individual strategy shutdown
- **Market Suspension**: Specific market pair suspension
- **System Maintenance Mode**: Safe shutdown dla maintenance

## Real-time Risk Monitoring

### Continuous Risk Metrics:
- **Portfolio Beta**: Market correlation measurement
- **Value at Risk (VaR)**: Daily VaR calculation
- **Expected Shortfall**: Tail risk measurement
- **Sharpe Ratio**: Risk-adjusted performance
- **Maximum Drawdown**: Current vs historical drawdown

### Risk Alerting System:
- **Warning Levels**: Multiple risk warning thresholds
- **Critical Alerts**: Immediate attention required
- **Trend Alerts**: Risk trend deterioration
- **Correlation Alerts**: High correlation warnings
- **Performance Alerts**: Unusual performance patterns

### Risk Dashboard Integration:
- **Real-time Risk Display**: Current risk metrics
- **Risk Trend Visualization**: Risk evolution over time
- **Alert Status**: Current alert levels
- **Position Risk Breakdown**: Individual position risk
- **Portfolio Risk Summary**: Overall portfolio risk

## Adaptive Risk Management

### Dynamic Risk Adjustment:
- **Market Volatility Adjustment**: Risk parameters adjust to volatility
- **Performance-Based Adjustment**: Risk based on recent performance
- **Correlation-Based Adjustment**: Risk based on portfolio correlation
- **Liquidity-Based Adjustment**: Risk based on market liquidity
- **Time-Based Adjustment**: Risk based on market hours/conditions

### Machine Learning Risk Enhancement:
- **Risk Pattern Recognition**: Historical risk pattern analysis
- **Predictive Risk Modeling**: Forward-looking risk assessment
- **Anomaly Detection**: Unusual risk pattern identification
- **Risk Optimization**: ML-based risk parameter optimization
- **Stress Testing**: Scenario-based risk testing

## Performance vs Risk Optimization

### Risk-Adjusted Performance Targets:
- **Target Sharpe Ratio**: >1.5 minimum acceptable
- **Target Maximum Drawdown**: <15% acceptable
- **Target Win Rate**: >55% dla profitable operation
- **Target Risk-Reward**: Minimum 1:2 risk-reward ratio
- **Target Volatility**: Portfolio volatility management

### Risk Budget Allocation:
- **Strategy Risk Budgets**: Risk allocation per strategy
- **Asset Risk Budgets**: Risk allocation per asset class
- **Time Risk Budgets**: Risk allocation across time
- **Factor Risk Budgets**: Risk allocation per risk factor
- **Total Risk Budget**: Overall portfolio risk budget

## Compliance and Governance

### Risk Policy Enforcement:
- **Automated Compliance**: Automatic rule enforcement
- **Exception Handling**: Rare exception management
- **Audit Trail**: Complete risk decision logging
- **Performance Review**: Regular risk performance assessment
- **Policy Updates**: Risk policy evolution and improvement

### Regulatory Considerations:
- **Position Limits**: Regulatory position size limits
- **Leverage Restrictions**: Regulatory leverage compliance
- **Reporting Requirements**: Risk reporting obligations
- **Risk Disclosure**: Risk methodology transparency
- **Best Practices**: Industry standard risk practices
