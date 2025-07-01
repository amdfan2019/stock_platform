from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from datetime import datetime


class Stock(Base):
    __tablename__ = "stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, index=True, nullable=False)
    company_name = Column(String(255), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Float)
    current_price = Column(Float)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    metrics = relationship("StockMetrics", back_populates="stock")
    news_articles = relationship("NewsArticle", back_populates="stock")
    recommendations = relationship("Recommendation", back_populates="stock")


class StockMetrics(Base):
    __tablename__ = "stock_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    
    # Valuation Metrics
    pe_ratio = Column(Float)
    forward_pe = Column(Float)
    peg_ratio = Column(Float)
    price_to_book = Column(Float)
    price_to_sales = Column(Float)
    
    # Historical Context
    pe_5_year_median = Column(Float)
    pe_percentile = Column(Float)  # Current PE vs historical range (0-100)
    
    # Financial Health
    debt_to_equity = Column(Float)
    current_ratio = Column(Float)
    quick_ratio = Column(Float)
    return_on_equity = Column(Float)
    return_on_assets = Column(Float)
    
    # Cash Flow
    free_cash_flow_per_share = Column(Float)
    fcf_growth_rate = Column(Float)  # YoY growth rate
    operating_cash_flow = Column(Float)
    
    # Technical Indicators
    sma_50 = Column(Float)
    sma_200 = Column(Float)
    rsi_14 = Column(Float)
    macd_signal = Column(String(10))  # 'bullish', 'bearish', 'neutral'
    bollinger_position = Column(Float)  # -1 to 1, where price sits in bands
    
    # Volume and Momentum
    avg_volume_50 = Column(Float)
    volume_ratio = Column(Float)  # Current volume vs average
    momentum_score = Column(Float)  # Custom momentum calculation
    
    # Calculated Fields
    intrinsic_value_estimate = Column(Float)
    margin_of_safety = Column(Float)  # Percentage below intrinsic value
    quality_score = Column(Float)  # 0-100 composite quality metric
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="metrics")


class NewsArticle(Base):
    __tablename__ = "news_articles"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    
    title = Column(String(500), nullable=False)
    summary = Column(Text)  # AI-generated summary (max 300 chars)
    url = Column(String(1000))
    source = Column(String(100))
    
    # Sentiment Analysis
    sentiment_score = Column(Float)  # -1 to 1 (negative to positive)
    sentiment_label = Column(String(20))  # 'positive', 'negative', 'neutral'
    confidence_score = Column(Float)  # 0 to 1
    
    # Impact Classification
    impact_level = Column(String(20))  # 'high', 'medium', 'low'
    impact_categories = Column(JSON)  # ['earnings', 'management', 'regulation', etc.]
    
    # Keywords and Signals
    extracted_signals = Column(JSON)  # Key actionable signals
    keywords = Column(JSON)  # Important keywords/entities
    
    published_at = Column(DateTime(timezone=True))
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="news_articles")


class Recommendation(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    
    # Recommendation Details
    action = Column(String(10), nullable=False)  # 'BUY', 'HOLD', 'SELL'
    confidence_score = Column(Float, nullable=False)  # 0 to 1
    
    # Price Ranges
    buy_range_low = Column(Float)
    buy_range_high = Column(Float)
    sell_range_low = Column(Float)
    sell_range_high = Column(Float)
    
    # Reasoning
    reasoning = Column(Text)  # LLM-generated explanation
    key_factors = Column(JSON)  # List of key decision factors
    
    # Signal Sources
    valuation_signal = Column(Float)  # -1 to 1
    technical_signal = Column(Float)  # -1 to 1
    news_sentiment_signal = Column(Float)  # -1 to 1
    
    # Risk Assessment
    risk_level = Column(String(20))  # 'low', 'medium', 'high'
    volatility_score = Column(Float)
    
    # Time-based
    recommendation_type = Column(String(20))  # 'daily', 'weekly', 'triggered'
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    stock = relationship("Stock", back_populates="recommendations")


class MarketArticle(Base):
    __tablename__ = "market_articles"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Article Identification (unique together)
    url = Column(String(1000), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    source = Column(String(100), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # AI-Enhanced Content
    implication_title = Column(String(500))  # AI-generated implication title
    ai_summary = Column(Text)  # AI-generated summary
    market_impact = Column(String(20))  # 'High', 'Medium', 'Low'
    sentiment = Column(String(20))  # 'bullish', 'bearish', 'neutral'
    mentioned_tickers = Column(JSON)  # List of mentioned stock symbols
    affected_sectors = Column(JSON)  # List of affected sectors
    
    # Relevance and Processing
    relevance_score = Column(Float)  # Calculated relevance score
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    processing_version = Column(String(10), default="1.0")  # For tracking algorithm changes
    
    # Content Quality
    content_quality_score = Column(Float)  # 0-100 content quality assessment
    freshness_score = Column(Float)  # Time-based freshness score
    
    # Deduplication
    content_hash = Column(String(64), index=True)  # Hash of title + summary for dedup


class MarketIndicator(Base):
    """Historical storage for individual market indicators."""
    __tablename__ = "market_indicators"
    
    id = Column(Integer, primary_key=True, index=True)
    indicator_type = Column(String, index=True)  # 'sp500', 'vix', 'treasury_10y', 'dxy', etc.
    value = Column(Float)  # The actual value
    change_pct = Column(Float, nullable=True)  # Percentage change if applicable
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    market_session = Column(String)  # 'regular', 'pre_market', 'after_hours', 'closed'
    data_source = Column(String)  # 'yfinance', 'alpha_vantage', 'manual', etc.
    is_valid = Column(Boolean, default=True)  # False if data collection failed
    created_at = Column(DateTime, default=datetime.utcnow)


class NewsSentiment(Base):
    """News sentiment analysis results from multiple sources."""
    __tablename__ = "news_sentiment"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_date = Column(Date, index=True)  # Date of the analysis
    overall_sentiment = Column(Float)  # -1 to 1 sentiment score
    sentiment_label = Column(String(20))  # 'Positive', 'Negative', 'Neutral'
    confidence_score = Column(Float)  # 0 to 1 confidence
    articles_analyzed = Column(Integer)  # Number of articles analyzed
    source_breakdown = Column(JSON)  # Details by source (reddit, news, etc.)
    data_source = Column(String, default='multi_source')  # Source combination used
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSentiment(Base):
    """Market sentiment data collection and storage."""
    __tablename__ = "market_sentiment"
    
    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Index Data
    sp500_price = Column(Float, nullable=True)
    sp500_change_pct = Column(Float, nullable=True)
    dow_price = Column(Float, nullable=True)
    dow_change_pct = Column(Float, nullable=True)
    nasdaq_price = Column(Float, nullable=True)
    nasdaq_change_pct = Column(Float, nullable=True)
    
    # Volatility Data
    vix_value = Column(Float, nullable=True)
    vix_change_pct = Column(Float, nullable=True)
    
    # Options Data
    put_call_ratio = Column(Float, nullable=True)
    
    # Treasury Data
    treasury_10y_yield = Column(Float, nullable=True)
    
    # Dollar Data
    dxy_value = Column(Float, nullable=True)
    dxy_change_pct = Column(Float, nullable=True)
    
    # Market Breadth
    new_highs = Column(Integer, nullable=True)
    new_lows = Column(Integer, nullable=True)
    advance_decline_ratio = Column(Float, nullable=True)
    
    # News Sentiment
    news_sentiment_score = Column(Float, nullable=True)  # -1 to 1
    news_sentiment_label = Column(String(20), nullable=True)  # 'Positive', 'Negative', 'Neutral'
    news_confidence = Column(Float, nullable=True)  # 0 to 1
    
    # Calculated Scores
    momentum_score = Column(Float, nullable=True)
    fear_greed_score = Column(Float, nullable=True)
    breadth_score = Column(Float, nullable=True)
    overall_sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(50), nullable=True)
    
    # Analysis Results
    key_drivers = Column(Text, nullable=True)  # JSON string
    trend_analysis = Column(Text, nullable=True)
    data_completeness = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketSentimentAnalysis(Base):
    """LLM-generated market sentiment analysis based on historical data."""
    __tablename__ = "market_sentiment_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_date = Column(DateTime, default=datetime.utcnow, index=True)
    sentiment_score = Column(Float)  # 1-10 scale from LLM
    sentiment_label = Column(String)  # "Extremely Bearish" to "Extremely Bullish"
    confidence_level = Column(Float)  # LLM's confidence in the analysis
    key_factors = Column(JSON)  # List of key factors driving sentiment
    trend_analysis = Column(Text)  # LLM's detailed trend analysis
    historical_context = Column(Text)  # LLM's comparison to historical patterns
    market_outlook = Column(Text)  # LLM's forward-looking analysis
    data_period_start = Column(DateTime)  # Start of data period analyzed
    data_period_end = Column(DateTime)  # End of data period analyzed
    indicators_analyzed = Column(JSON)  # List of indicators included in analysis
    created_at = Column(DateTime, default=datetime.utcnow)


class UserWatchlist(Base):
    __tablename__ = "user_watchlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False)  # For future user management
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    
    # User Preferences
    alert_threshold = Column(Float)  # Custom confidence threshold for alerts
    notification_enabled = Column(Boolean, default=True)
    
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock")


class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    service = Column(String(50), nullable=False)  # 'screener', 'news', 'llm'
    action = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # 'success', 'error', 'warning'
    message = Column(Text)
    log_metadata = Column(JSON)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now()) 