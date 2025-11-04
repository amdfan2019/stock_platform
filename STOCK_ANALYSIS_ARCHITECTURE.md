# Stock Analysis Architecture v2.0

## Overview
Redesigned stock analysis system that mirrors the successful global market infrastructure (Momentum, News, Fundamentals) but applied to individual stocks. Each stock maintains historical time series data and receives daily AI-powered analysis.

## Architecture Layers

### 1. Data Collection Layer

#### StockDataCollector Service
- **Purpose**: Collect and store time series data for individual stocks
- **Data Sources**: 
  - yfinance (price, volume, fundamentals)
  - Market news database (filter for stock mentions)
- **Storage**: StockTimeSeries table
- **Schedule**: Daily updates for tracked stocks
- **Data Points**:
  - Price metrics (open, high, low, close, volume)
  - Valuation metrics (P/E, P/B, P/S, market cap)
  - Growth metrics (revenue, earnings, margins)
  - Technical indicators (RSI, MACD, moving averages)

### 2. Storage Layer

#### StockTimeSeries Model
```python
class StockTimeSeries(Base):
    ticker: str
    date: date
    
    # Price Data
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: bigint
    
    # Valuation Metrics
    pe_ratio: float
    pb_ratio: float
    ps_ratio: float
    market_cap: float
    
    # Growth Metrics
    revenue: float
    earnings: float
    profit_margin: float
    
    # Technical Indicators
    rsi: float
    macd: float
    sma_50: float
    sma_200: float
    
    data_source: str
    created_at: timestamp
```

#### StockTechnicalAnalysis Model
```python
class StockTechnicalAnalysis(Base):
    ticker: str
    analysis_date: timestamp
    
    # Trend Analysis
    trend_direction: str (Bullish/Bearish/Sideways)
    trend_strength: float (0-1)
    trend_duration_days: int
    
    # Support/Resistance
    support_level: float
    resistance_level: float
    support_strength: float (0-1)
    resistance_strength: float (0-1)
    
    # Momentum
    momentum_score: float (-1 to 1)
    momentum_trend: str (Accelerating/Stable/Decelerating)
    
    # Volatility
    volatility_level: str (Low/Medium/High)
    volatility_percentile: float (vs 1 year)
    
    # Volume Analysis
    volume_trend: str (Increasing/Stable/Decreasing)
    unusual_volume: bool
    
    # Pattern Recognition
    chart_pattern: str
    pattern_reliability: float (0-1)
    
    # Context
    vs_market_performance: float (% difference from S&P 500)
    relative_strength: float (vs sector)
    
    # Key Insights
    technical_summary: str (LLM generated)
    key_levels: list[dict]
    entry_points: list[dict]
    exit_points: list[dict]
    
    agent_id: str
    confidence_score: float
```

#### StockNewsAnalysis Model
```python
class StockNewsAnalysis(Base):
    ticker: str
    analysis_date: timestamp
    
    # News Impact
    overall_sentiment: float (-1 to 1)
    sentiment_label: str (Very Negative to Very Positive)
    news_volume: int (number of mentions)
    
    # Key Themes (LLM extracted)
    growth_opportunities: list[str]
    competitive_threats: list[str]
    regulatory_concerns: list[str]
    product_developments: list[str]
    management_changes: list[str]
    
    # Earnings Context
    recent_earnings: str (Beat/Miss/In-line)
    guidance_direction: str (Raised/Maintained/Lowered)
    analyst_revisions: str (Upgrades/Downgrades/Mixed)
    
    # Market Context Integration
    vs_sector_news: str (Better/Worse/Neutral)
    market_attention_level: str (High/Medium/Low)
    
    # Recent Events (last 7 days)
    major_news_events: list[dict]
    price_moving_news: list[dict]
    
    # Forward Looking
    upcoming_catalysts: list[str]
    key_dates: list[dict] (earnings dates, product launches, etc)
    
    # LLM Synthesis
    news_summary: str
    key_worries: list[str]
    key_opportunities: list[str]
    
    agent_id: str
    articles_analyzed: int
```

### 3. Analysis Layer

#### StockTechnicalAgent
- **Input**: StockTimeSeries data (90+ days)
- **Context**: Market sentiment, market technical trends
- **Output**: StockTechnicalAnalysis
- **LLM Task**: 
  - Analyze price patterns and trends
  - Identify key support/resistance levels
  - Assess momentum and volatility
  - Compare to market performance
  - Generate actionable technical insights

#### StockNewsAgent  
- **Input**: Market news (filtered for stock mentions)
- **Context**: Market news themes, sector trends
- **Output**: StockNewsAnalysis
- **LLM Task**:
  - Filter and categorize stock-specific news
  - Extract key themes, worries, opportunities
  - Assess sentiment and impact
  - Identify catalysts and risks
  - Provide forward-looking insights

#### StockMasterAgent
- **Input**: 
  - StockTechnicalAnalysis (latest)
  - StockNewsAnalysis (latest)
  - Market sentiment context
  - Economic fundamentals context
  - StockTimeSeries (current metrics)
- **Output**: StockAnalysis (comprehensive recommendation)
- **LLM Task**:
  - Synthesize technical + news + market context
  - Generate buy/sell/hold recommendation
  - Set target price with justification
  - Explain current price level
  - Provide future outlook
  - Identify key risks and catalysts

### 4. Orchestration Layer

#### Daily Stock Update Workflow
```
1. StockDataCollector.collect_daily_data(ticker)
   ↓
2. StockTechnicalAgent.run_cycle(ticker)
   ↓
3. StockNewsAgent.run_cycle(ticker)
   ↓
4. StockMasterAgent.run_cycle(ticker)
   ↓
5. Store final StockAnalysis
```

#### Scheduler
- Run daily for all "tracked" stocks
- Stagger updates to avoid API rate limits
- Priority queue for user-requested stocks

### 5. API Layer

#### Endpoints
- `GET /api/stock/{ticker}/analysis` - Latest comprehensive analysis
- `GET /api/stock/{ticker}/technical` - Latest technical analysis
- `GET /api/stock/{ticker}/news` - Latest news analysis
- `GET /api/stock/{ticker}/timeseries?days=90` - Historical data
- `POST /api/stock/{ticker}/analyze` - Trigger immediate analysis
- `POST /api/stock/{ticker}/track` - Add to daily tracking list
- `GET /api/stocks/tracked` - List all tracked stocks

## Data Flow Example

### User searches for AAPL:

1. **Frontend** requests `/api/stock/AAPL/analysis`
2. **Backend** checks if analysis exists and is recent (< 24 hours)
3. If not recent:
   - **StockDataCollector** fetches latest data from yfinance
   - **StockTechnicalAgent** analyzes time series
   - **StockNewsAgent** filters market news for AAPL
   - **StockMasterAgent** synthesizes everything
4. Return comprehensive analysis to frontend

### Daily Background Process:

```
Every day at 6 PM EST (after market close):
  For each tracked_stock in tracked_stocks:
    1. Collect daily data (price, volume, fundamentals)
    2. Run technical analysis
    3. Run news analysis  
    4. Run master synthesis
    5. Log Gemini API calls for debugging
```

## Integration with Existing Infrastructure

### Market Sentiment Agent
- Provides market-wide sentiment score (1-10)
- Used to contextualize individual stock momentum

### Market News Agent  
- Provides overall market themes
- Stock news agent filters these for stock mentions
- Compares stock-specific sentiment to market sentiment

### Economic Fundamentals Agent
- Provides macro context (GDP, inflation, Fed policy)
- Used to assess how stock fits in economic cycle

## Scalability Considerations

### Database Optimization
- Index on (ticker, date) for fast time series queries
- Partition stock_timeseries by date for performance
- Cascade deletes for removed stocks

### API Rate Limits
- yfinance: Implement retry logic and delays
- News sources: Cache and reuse market news
- Gemini LLM: Track usage per stock, prioritize active stocks

### Storage Growth
- ~365 rows per stock per year in stock_timeseries
- For 100 stocks: ~36,500 rows/year
- Implement data retention policy (e.g., keep 2 years)

### Computation
- Technical analysis: Fast (mathematical calculations)
- News analysis: Medium (LLM call, but uses existing market news)
- Master synthesis: Medium (LLM call)
- Total: ~3 LLM calls per stock per day

## Future Enhancements

1. **Real-time Updates**: WebSocket for intraday price updates
2. **Watchlist System**: User-specific tracked stocks
3. **Alerts**: Price target hit, support/resistance breach
4. **Backtesting**: Test historical accuracy of recommendations
5. **Peer Comparison**: Compare multiple stocks side-by-side
6. **Sector Analysis**: Aggregate stocks by sector for sector views
7. **Portfolio Analysis**: Analyze user's portfolio as a whole

