from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .database import get_db, engine, SessionLocal
from .models import Base, MarketArticle
from .config import settings
from .services.stock_screener import StockScreener
from .services.market_news_processor import MarketNewsProcessor
from .services.market_sentiment_collector import market_sentiment_collector

from .services.historical_market_collector import historical_collector
from .services.llm_sentiment_analyzer import llm_sentiment_analyzer
import asyncio
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta, date
from sqlalchemy import desc
from loguru import logger
from contextlib import asynccontextmanager

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
market_news_processor = MarketNewsProcessor()

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
async def get_market_news():
    """Get processed market news with AI summaries."""
    try:
        articles = await market_news_processor.get_processed_articles()
        return {"articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/market-news/refresh")
async def refresh_market_news(background_tasks: BackgroundTasks):
    """Refresh market news in the background."""
    try:
        background_tasks.add_task(market_news_processor.collect_and_process_news)
        return {"message": "Market news refresh started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 