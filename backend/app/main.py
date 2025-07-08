from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .database import get_db, engine, SessionLocal
from .models import Base, MarketArticle, MarketNewsSummary, EconomicIndicator, EconomicEvent, FundamentalsAnalysis
from .config import settings
from .services.stock_screener import StockScreener
from .services.market_sentiment_collector import market_sentiment_collector
from .services.historical_market_collector import historical_collector
from .services.llm_sentiment_analyzer import llm_sentiment_analyzer
from .services.simple_market_news import SimpleMarketNews
from .services.economic_fundamentals_collector import economic_fundamentals_collector
import asyncio
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import desc, and_
from loguru import logger
from contextlib import asynccontextmanager
from collections import defaultdict
from . import api
from .api import router as debug_router

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Stock Platform API starting up...")
    yield
    # Shutdown
    print("📉 Stock Platform API shutting down...")

# Initialize FastAPI app
app = FastAPI(
    title="Stock Platform API",
    description="Advanced stock analysis and market intelligence platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
stock_screener = StockScreener()
market_news_service = SimpleMarketNews()

# Pydantic models for API requests/responses
class StockSearchRequest(BaseModel):
    ticker: str

class RecommendationResponse(BaseModel):
    ticker: str
    action: str
    confidence_score: float
    reasoning: str
    key_factors: List[str]
    valuation_signal: float
    technical_signal: float
    news_sentiment_signal: float
    buy_range_low: Optional[float] = None
    buy_range_high: Optional[float] = None
    sell_range_low: Optional[float] = None
    sell_range_high: Optional[float] = None
    risk_level: str
    volatility_score: float
    created_at: datetime

class NewsArticleResponse(BaseModel):
    title: str
    summary: Optional[str]
    source: str
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]
    impact_level: Optional[str]
    published_at: Optional[datetime]

class StockAnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    current_price: Optional[float]
    market_cap: Optional[float]
    pe_ratio: Optional[float]
    quality_score: Optional[float]
    margin_of_safety: Optional[float]
    recommendation: Optional[RecommendationResponse]
    recent_news: List[NewsArticleResponse]

class NewsSentimentRequest(BaseModel):
    force_refresh: Optional[bool] = False
    sources: Optional[List[str]] = None  # ['alphavantage_news', 'general_news']

# API Routes

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Stock Platform API v2.0",
        "description": "Advanced market intelligence with LLM-powered sentiment analysis",
        "features": [
            "Historical market data collection",
            "LLM-based sentiment analysis", 
            "News sentiment analysis from multiple sources",
            "Real-time market indicators",
            "AI-enhanced market news"
        ],
        "endpoints": {
            "market_sentiment": "/api/market-sentiment",
            "sentiment_analysis": "/api/sentiment-analysis/latest",
            "market_data": "/api/market-data/historical",
            "market_data_collect": "/api/market-data/collect",
            "historical_backfill": "/api/market-data/backfill",
            "market_news": "/api/market-news",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "connected",
            "market_data_collector": "active",
            "llm_analyzer": "configured" if llm_sentiment_analyzer.model else "not_configured"
        }
    }

@app.get("/api/stocks/trending")
async def get_trending_stocks():
    """Get trending stocks based on market activity."""
    try:
        trending_stocks = await stock_screener.get_trending_stocks()
        return {"stocks": trending_stocks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stocks/search")
async def search_stocks(query: str):
    """Search for stocks by symbol or company name."""
    try:
        results = await stock_screener.search_stocks(query)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market-news")
async def get_market_news(background_tasks: BackgroundTasks):
    """Get processed market news with AI summaries. Serve cached top-10 immediately, trigger update in background."""
    try:
        # 1. Query and return the current top-10 from the DB immediately
        db = SessionLocal()
        try:
            all_recent = db.query(MarketArticle).filter(
                MarketArticle.published_at >= datetime.now(timezone.utc) - timedelta(hours=24)
            ).order_by(desc(MarketArticle.published_at)).all()
            formatted = market_news_service._format_articles_for_frontend(all_recent)
            for a in formatted:
                a['relevance_score'] = market_news_service._relevance_score(a)
            def utc_ts(dt):
                if dt is None:
                    return 0
                if isinstance(dt, str):
                    try:
                        dt = datetime.fromisoformat(dt)
                    except Exception:
                        return 0
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            top = sorted(formatted, key=lambda x: (-x['relevance_score'], -utc_ts(x.get('published_at'))))[:10]
            top = sorted(top, key=lambda x: -utc_ts(x.get('published_at')))
        finally:
            db.close()
        # 2. Trigger the update/fetch pipeline in the background
        background_tasks.add_task(market_news_service.get_market_news)
        # Fetch the most recent summary
        db = SessionLocal()
        try:
            latest_summary = db.query(MarketNewsSummary).order_by(MarketNewsSummary.created_at.desc()).first()
            news_summary = latest_summary.summary if latest_summary else None
        finally:
            db.close()
        return {
            "articles": top,
            "total_articles": len(top),
            "hours_lookback": 24,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources_covered": [s["name"] for s in market_news_service.news_sources],
            "cache_status": "fresh",
            "news_summary": news_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/market-news/refresh")
async def refresh_market_news(background_tasks: BackgroundTasks):
    """Refresh market news in the background (no-op for simple version)."""
    return {"message": "Market news refresh is handled automatically in the new system."}

@app.post("/api/market-data/collect")
async def collect_market_data():
    """Collect current market indicator data including Fear & Greed Index."""
    try:
        # Collect traditional market indicators
        results = await historical_collector.collect_all_indicators()
        
        # Also collect Fear & Greed Index only (removing news sentiment)
        logger.info("Collecting Fear & Greed Index")
        fear_greed_data = await market_sentiment_collector.collect_fear_greed_index()
        
        # Count successful collections by checking if data has valid values
        successful = len([r for r in results if r and r.get('value') is not None])
        
        # Add Fear & Greed data to results if available
        if fear_greed_data:
            results.append({
                'indicator_type': 'fear_greed_index',
                'value': fear_greed_data['value'],
                'label': fear_greed_data['label'],
                'source': fear_greed_data['source'],
                'timestamp': fear_greed_data['timestamp']
            })
            successful += 1
        
        return {
            "message": "Market data and Fear & Greed Index collection completed",
            "indicators_collected": len(results),
            "successful_collections": successful,
            "fear_greed_index": fear_greed_data,
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market-data/historical")
async def get_historical_data(days_back: int = 30):
    """Get historical market data for analysis."""
    try:
        if days_back < 1 or days_back > 90:
            raise HTTPException(status_code=400, detail="days_back must be between 1 and 90")
            
        data = await historical_collector.get_historical_data(days_back)
        
        return {
            "days_back": days_back,
            "indicators": list(data.keys()),
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/market-data/backfill")
async def backfill_historical_data(days_back: int = 30, background_tasks: BackgroundTasks = None):
    """Backfill historical market data for the past N days."""
    try:
        if days_back < 1 or days_back > 90:
            raise HTTPException(status_code=400, detail="days_back must be between 1 and 90")
        
        if background_tasks:
            # Run backfill in background for large requests
            background_tasks.add_task(historical_collector.backfill_historical_data, days_back)
            return {
                "message": f"Historical backfill started for {days_back} days",
                "status": "background_task_started"
            }
        else:
            # Run synchronously for smaller requests
            result = await historical_collector.backfill_historical_data(days_back)
            return result
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/market-data/create-mock-data")
async def create_mock_historical_data(days_back: int = 30):
    """Create mock historical data for testing purposes."""
    try:
        if days_back < 1 or days_back > 90:
            raise HTTPException(status_code=400, detail="days_back must be between 1 and 90")
            
        mock_data = await historical_collector.create_mock_data(days_back)
        
        return {
            "message": f"Mock historical data created for {days_back} days",
            "mock_data": mock_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sentiment-analysis/generate")
async def generate_sentiment_analysis(days_back: int = 30):
    """Generate new LLM-based sentiment analysis."""
    try:
        if days_back < 1 or days_back > 90:
            raise HTTPException(status_code=400, detail="days_back must be between 1 and 90")
            
        analysis = await llm_sentiment_analyzer.generate_sentiment_analysis(days_back)
        
        if analysis:
            return {
                "message": "Sentiment analysis generated successfully",
                "analysis": analysis
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate sentiment analysis")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sentiment-analysis/latest")
async def get_latest_sentiment_analysis():
    """Get the most recent sentiment analysis."""
    try:
        analysis = await llm_sentiment_analyzer.get_latest_analysis()
        
        if analysis:
            return {"analysis": analysis}
        else:
            return {"analysis": None, "message": "No sentiment analysis available"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market-sentiment")
async def get_market_sentiment():
    """Get current market sentiment (combines latest data + LLM analysis) - NO NEWS SENTIMENT."""
    try:
        # Get latest sentiment analysis
        analysis = await llm_sentiment_analyzer.get_latest_analysis()
        
        # Get FRESH current market indicators (not historical time series)
        logger.info("Collecting fresh current market indicators for market sentiment endpoint")
        current_indicators = {}
        
        # Collect fresh data for each indicator (same as market-data/collect does)
        indicators_config = {
            'sp500': '^GSPC',
            'dow': '^DJI', 
            'nasdaq': '^IXIC',
            'vix': '^VIX',
            'treasury_10y': '^TNX',
            'dxy': 'DX-Y.NYB'
        }
        
        for indicator_type, symbol in indicators_config.items():
            try:
                indicator_data = await historical_collector.collect_indicator_data(indicator_type, symbol)
                if indicator_data:
                    current_indicators[indicator_type] = {
                        'value': indicator_data['value'],
                        'change_pct': indicator_data['change_pct'],
                        'data_source': indicator_data['data_source']
                    }
                    logger.info(f"Fresh {indicator_type}: {indicator_data['value']:.2f} ({indicator_data['change_pct']:+.2f}%)")
                else:
                    logger.warning(f"Failed to get fresh data for {indicator_type}")
            except Exception as e:
                logger.error(f"Error collecting fresh {indicator_type} data: {e}")
        
        # Get current Fear & Greed Index ONLY (no news sentiment)
        fear_greed_data = await market_sentiment_collector.collect_fear_greed_index()
        if fear_greed_data:
            current_indicators['fear_greed_index'] = fear_greed_data
        
        # Combine analysis with current data
        response = {
            "sentiment_analysis": analysis,
            "current_indicators": current_indicators,
            "data_timestamp": datetime.utcnow().isoformat(),
            "market_session": "regular" if historical_collector.is_market_open() else "closed"
        }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fear-greed-index")
async def get_fear_greed_index():
    """Get current Fear & Greed Index."""
    try:
        fear_greed_data = await market_sentiment_collector.collect_fear_greed_index()
        
        if fear_greed_data:
            return {
                "fear_greed_index": fear_greed_data,
                "interpretation": {
                    "0-25": "Extreme Fear",
                    "25-45": "Fear", 
                    "45-55": "Neutral",
                    "55-75": "Greed",
                    "75-100": "Extreme Greed"
                }
            }
        else:
            return {
                "fear_greed_index": None,
                "message": "Fear & Greed Index not available"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Economic Fundamentals endpoints
@app.get("/api/fundamentals")
async def get_fundamentals_data():
    """Get current economic fundamentals data with LLM analysis."""
    try:
        db = SessionLocal()
        try:
            # Get latest indicators by category
            categories = ['inflation', 'employment', 'interest_rates', 'gdp', 'consumer', 'manufacturing', 'home_prices']
            fundamentals_data = {}
            
            for category in categories:
                # Get the most recent indicators for each indicator_name in this category
                indicators = db.query(EconomicIndicator).filter(
                    EconomicIndicator.category == category
                ).order_by(
                    EconomicIndicator.indicator_name,
                    EconomicIndicator.reference_date.desc()
                ).all()
                # Group by indicator_name, take up to 5 most recent for each
                grouped = defaultdict(list)
                for ind in indicators:
                    grouped[ind.indicator_name].append(ind)
                recent_indicators = []
                for inds in grouped.values():
                    recent_indicators.extend(inds[:5])
                # Sort by reference_date descending
                recent_indicators = sorted(recent_indicators, key=lambda x: x.reference_date, reverse=True)
                fundamentals_data[category] = [
                    {
                        'indicator_name': ind.indicator_name,
                        'value': ind.value,
                        'unit': ind.unit,
                        'reference_date': ind.reference_date.isoformat(),
                        'previous_value': ind.previous_value,
                        'period_type': ind.period_type,
                        'source': ind.source
                    }
                    for ind in recent_indicators
                ]
            
            # Get latest fundamentals analysis
            latest_analysis = db.query(FundamentalsAnalysis).order_by(
                FundamentalsAnalysis.analysis_date.desc()
            ).first()
            
            analysis_data = None
            if latest_analysis:
                analysis_data = {
                    'overall_assessment': latest_analysis.overall_assessment,
                    'economic_cycle_stage': latest_analysis.economic_cycle_stage,
                    'inflation_outlook': latest_analysis.inflation_outlook,
                    'employment_outlook': latest_analysis.employment_outlook,
                    'monetary_policy_stance': latest_analysis.monetary_policy_stance,
                    'key_insights': latest_analysis.key_insights,
                    'market_implications': latest_analysis.market_implications,
                    'sector_impacts': latest_analysis.sector_impacts,
                    'risk_factors': latest_analysis.risk_factors,
                    'confidence_level': latest_analysis.confidence_level,
                    'analysis_date': latest_analysis.analysis_date.isoformat(),
                    'explanation': latest_analysis.explanation
                }
            
            return {
                'fundamentals_data': fundamentals_data,
                'analysis': analysis_data,
                'data_timestamp': datetime.utcnow().isoformat(),
                'categories': categories
            }
            
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fundamentals/collect")
async def collect_fundamentals_data(background_tasks: BackgroundTasks):
    """Collect fresh economic fundamentals data (incremental - only new dates)."""
    try:
        # Start incremental collection in background
        background_tasks.add_task(economic_fundamentals_collector.collect_latest_data)
        
        return {
            "message": "Incremental economic fundamentals data collection started",
            "description": "Only new data points will be added, existing dates will be skipped",
            "status": "background_task_started",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fundamentals/backfill")
async def backfill_fundamentals_data(days_back: int = 730, background_tasks: BackgroundTasks = None):
    """Backfill historical economic fundamentals data."""
    try:
        if days_back < 30 or days_back > 3650:
            raise HTTPException(status_code=400, detail="days_back must be between 30 and 3650 (10 years)")
        
        if background_tasks:
            # Run backfill in background for large requests
            background_tasks.add_task(economic_fundamentals_collector.backfill_historical_data, days_back)
            return {
                "message": f"Historical economic data backfill started for {days_back} days",
                "description": "This will collect full time series data from FRED API",
                "status": "background_task_started",
                "days_back": days_back,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Run synchronously for smaller requests
            result = await economic_fundamentals_collector.backfill_historical_data(days_back)
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fundamentals/analyze")
async def generate_fundamentals_analysis():
    """Generate new LLM analysis of economic fundamentals."""
    try:
        analysis = await economic_fundamentals_collector.generate_fundamentals_analysis()
        
        if analysis:
            # Store the analysis
            stored = await economic_fundamentals_collector._store_analysis(analysis)
            return {
                "message": "Fundamentals analysis generated successfully",
                "analysis": analysis,
                "stored": stored
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate fundamentals analysis")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fundamentals/events")
async def get_upcoming_economic_events():
    """Get upcoming economic events and data releases."""
    try:
        db = SessionLocal()
        try:
            # Get upcoming events in the next 30 days
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=30)
            
            upcoming_events = db.query(EconomicEvent).filter(
                and_(
                    EconomicEvent.scheduled_date >= start_date,
                    EconomicEvent.scheduled_date <= end_date
                )
            ).order_by(EconomicEvent.scheduled_date).all()
            
            events_data = [
                {
                    'event_name': event.event_name,
                    'category': event.category,
                    'scheduled_date': event.scheduled_date.isoformat(),
                    'importance': event.importance,
                    'previous_value': event.previous_value,
                    'forecast_value': event.forecast_value,
                    'actual_value': event.actual_value,
                    'impact_description': event.impact_description,
                    'is_released': event.is_released
                }
                for event in upcoming_events
            ]
            
            return {
                'upcoming_events': events_data,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'total_events': len(events_data)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fundamentals/stats")
async def get_fundamentals_database_stats():
    """Get statistics about the fundamentals data in the database."""
    try:
        db = SessionLocal()
        try:
            # Get data coverage statistics
            stats = {}
            
            # Overall statistics
            total_indicators = db.query(EconomicIndicator).count()
            
            # Date range coverage
            oldest_date = db.query(EconomicIndicator.reference_date).order_by(EconomicIndicator.reference_date).first()
            newest_date = db.query(EconomicIndicator.reference_date).order_by(EconomicIndicator.reference_date.desc()).first()
            
            # Count by category
            categories = ['inflation', 'employment', 'interest_rates', 'gdp', 'consumer', 'manufacturing', 'home_prices']
            category_counts = {}
            category_date_ranges = {}
            
            for category in categories:
                count = db.query(EconomicIndicator).filter(EconomicIndicator.category == category).count()
                category_counts[category] = count
                
                # Get date range for this category
                oldest_cat = db.query(EconomicIndicator.reference_date).filter(
                    EconomicIndicator.category == category
                ).order_by(EconomicIndicator.reference_date).first()
                newest_cat = db.query(EconomicIndicator.reference_date).filter(
                    EconomicIndicator.category == category
                ).order_by(EconomicIndicator.reference_date.desc()).first()
                
                category_date_ranges[category] = {
                    'oldest': oldest_cat[0].isoformat() if oldest_cat else None,
                    'newest': newest_cat[0].isoformat() if newest_cat else None
                }
            
            # Count by indicator
            indicator_counts = {}
            for indicator_name in ['cpi_all_items', 'unemployment_rate', 'fed_funds_rate', 'gdp_real']:
                count = db.query(EconomicIndicator).filter(
                    EconomicIndicator.indicator_name == indicator_name
                ).count()
                if count > 0:
                    indicator_counts[indicator_name] = count
            
            return {
                'total_data_points': total_indicators,
                'date_range': {
                    'oldest': oldest_date[0].isoformat() if oldest_date else None,
                    'newest': newest_date[0].isoformat() if newest_date else None
                },
                'category_counts': category_counts,
                'category_date_ranges': category_date_ranges,
                'sample_indicator_counts': indicator_counts,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"message": "Endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": f"Unexpected error: {str(exc)}"}
    )

app.include_router(debug_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 