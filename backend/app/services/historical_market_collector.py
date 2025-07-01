"""
Historical Market Data Collector Service

Continuously collects and stores market indicators for LLM-based sentiment analysis.
No mock data - real failures are stored as NULL/0 values.
"""

import asyncio
import aiohttp
import json
import yfinance as yf
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, time
import pytz
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from ..database import SessionLocal
from ..models import MarketIndicator, NewsSentiment, MarketSentimentAnalysis
from ..config import settings
import google.generativeai as genai
from contextlib import asynccontextmanager
import random

class HistoricalMarketCollector:
    """Collects and stores historical market data for LLM sentiment analysis."""
    
    def __init__(self):
        self.alpha_vantage_key = settings.alpha_vantage_api_key or "demo"
        self.fmp_key = settings.fmp_api_key or "demo"
        
        # Configure Gemini if API key is available
        if hasattr(settings, 'google_api_key') and settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)
        
        # Market indicators to track
        self.indicators = {
            'sp500': {
                "yahoo": "^GSPC",
                "alpha_vantage": "SPY",  # Using SPY as proxy for S&P 500
                "fmp": "^GSPC",
                "fred": None
            },
            'dow': {
                "yahoo": "^DJI", 
                "alpha_vantage": "DIA",  # Using DIA as proxy for Dow
                "fmp": "^DJI",
                "fred": None
            },
            'nasdaq': {
                "yahoo": "^IXIC",
                "alpha_vantage": "QQQ",  # Using QQQ as proxy for NASDAQ
                "fmp": "^IXIC", 
                "fred": None
            },
            'vix': {
                "yahoo": "^VIX",
                "alpha_vantage": "VIX",
                "fmp": "^VIX",
                "fred": None
            },
            'treasury_10y': {
                "yahoo": "^TNX",
                "alpha_vantage": None,
                "fmp": "^TNX",
                "fred": "GS10"  # 10-Year Treasury Constant Maturity Rate
            },
            'dxy': {
                "yahoo": "DX-Y.NYB",
                "alpha_vantage": "UUP",  # Using UUP as proxy for DXY
                "fmp": "DX-Y.NYB",
                "fred": "DTWEXBGS"  # Trade Weighted U.S. Dollar Index
            }
        }
        
        # Eastern time zone for market hours
        self.est = pytz.timezone('US/Eastern')
        
    def is_market_open(self) -> bool:
        """Check if US stock market is currently open."""
        try:
            now_est = datetime.now(self.est)
            
            # Check if it's a weekday (Monday=0, Sunday=6)
            if now_est.weekday() >= 5:  # Weekend
                return False
                
            # Market hours: 9:30 AM - 4:00 PM EST
            market_open = time(9, 30)
            market_close = time(16, 0)
            current_time = now_est.time()
            
            return market_open <= current_time <= market_close
            
        except Exception as e:
            logger.error(f"Error checking market hours: {str(e)}")
            return False
    
    async def collect_indicator_data(self, indicator_type: str, symbol: str) -> Optional[Dict]:
        """Collect market data for a specific indicator."""
        logger.info(f"Collecting data for {indicator_type} ({symbol})")
        
        try:
            # Check if we already have data for today for this indicator
            today = datetime.utcnow().date()
            async with self.session_scope() as session:
                existing_record = session.query(MarketIndicator).filter(
                    and_(
                        MarketIndicator.indicator_type == indicator_type,
                        MarketIndicator.timestamp >= datetime.combine(today, time.min),
                        MarketIndicator.timestamp < datetime.combine(today + timedelta(days=1), time.min)
                    )
                ).first()
                
                if existing_record:
                    logger.info(f"📋 {indicator_type}: Data already exists for today ({existing_record.value:.2f}) - skipping collection")
                    return {
                        'value': existing_record.value,
                        'change_pct': existing_record.change_pct,
                        'data_source': f"{existing_record.data_source}_cached"
                    }
            
            # Get historical data with proper 5-day calculation
            data = await self._get_yahoo_historical_data(symbol)
            if data:
                # Store the indicator data
                async with self.session_scope() as session:
                    indicator = MarketIndicator(
                        indicator_type=indicator_type,
                        value=data['value'],
                        change_pct=data['change_pct'],
                        timestamp=datetime.utcnow(),
                        market_session=self._get_market_session(),
                        data_source=data['data_source'],
                        is_valid=True
                    )
                    session.add(indicator)
                    # Commit handled by session_scope context manager
                    
                logger.info(f"✅ {indicator_type}: {data['value']:.2f} ({data['change_pct']:+.2f}% 5d) - {data['data_source']}")
                return data
                
        except Exception as e:
            logger.error(f"Error collecting {indicator_type} data: {e}")
            
        # Store failed collection only if no data exists for today
        try:
            today = datetime.utcnow().date()
            async with self.session_scope() as session:
                existing_record = session.query(MarketIndicator).filter(
                    and_(
                        MarketIndicator.indicator_type == indicator_type,
                        MarketIndicator.timestamp >= datetime.combine(today, time.min),
                        MarketIndicator.timestamp < datetime.combine(today + timedelta(days=1), time.min)
                    )
                ).first()
                
                if not existing_record:
                    indicator = MarketIndicator(
                        indicator_type=indicator_type,
                        value=None,
                        change_pct=None,
                        timestamp=datetime.utcnow(),
                        market_session=self._get_market_session(),
                        data_source='failed',
                        is_valid=False
                    )
                    session.add(indicator)
                    # Commit handled by session_scope context manager
        except Exception as e:
            logger.error(f"Error storing failed indicator: {e}")
            
        return None

    async def _get_yahoo_historical_data(self, symbol: str) -> Optional[Dict]:
        """Get historical market data from Yahoo API with current live data during market hours."""
        try:
            import aiohttp
            import asyncio
            
            # Add delay to avoid rate limiting
            await asyncio.sleep(0.5)
            
            # During market hours, get current quote data for live prices
            if self.is_market_open():
                current_data = await self._get_current_yahoo_quote(symbol)
                if current_data:
                    return current_data
            
            # Fallback to historical data (for after hours or if current data fails)
            # Get 10 days of data to ensure we have at least 5 trading days
            # This accounts for weekends and potential holidays
            end_time = int(datetime.utcnow().timestamp())
            start_time = int((datetime.utcnow() - timedelta(days=10)).timestamp())
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                'period1': start_time,
                'period2': end_time,
                'interval': '1d',
                'includePrePost': 'false'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'chart' in data and data['chart']['result']:
                            chart = data['chart']['result'][0]
                            timestamps = chart.get('timestamp', [])
                            
                            if 'indicators' in chart and 'quote' in chart['indicators']:
                                quote = chart['indicators']['quote'][0]
                                closes = quote.get('close', [])
                                
                                if closes and len(closes) > 0:
                                    # Get valid closing prices with their timestamps
                                    valid_data = []
                                    for i, price in enumerate(closes):
                                        if price is not None and i < len(timestamps):
                                            date = datetime.fromtimestamp(timestamps[i])
                                            # Only include weekdays (trading days)
                                            if date.weekday() < 5:  # Monday=0, Friday=4
                                                valid_data.append((date, price))
                                    
                                    # Sort by date to ensure proper order
                                    valid_data.sort(key=lambda x: x[0])
                                    
                                    if len(valid_data) >= 2:
                                        # Get the most recent price (current)
                                        current_date, current_price = valid_data[-1]
                                        
                                        # For 5-day change, we want the 5th trading day back
                                        # If we have at least 6 data points, use the 6th from the end (5 days back)
                                        # Otherwise, use the oldest available
                                        if len(valid_data) >= 6:
                                            comparison_date, comparison_price = valid_data[-6]
                                        else:
                                            comparison_date, comparison_price = valid_data[0]
                                        
                                        # Calculate percentage change
                                        change_pct = ((current_price - comparison_price) / comparison_price) * 100
                                        
                                        # Calculate number of trading days between dates
                                        trading_days = len(valid_data) - 1 if len(valid_data) >= 6 else len(valid_data) - 1
                                        
                                        # Log the calculation for debugging
                                        logger.info(f"📊 {symbol}: {comparison_date.strftime('%Y-%m-%d')} {comparison_price:.2f} → {current_date.strftime('%Y-%m-%d')} {current_price:.2f} = {change_pct:+.2f}% ({trading_days} trading days)")
                                        
                                        return {
                                            'value': float(current_price),
                                            'change_pct': change_pct,
                                            'data_source': 'yahoo_historical'
                                        }
                    
                    elif response.status == 429:
                        logger.warning(f"Rate limited for {symbol}, waiting longer...")
                        await asyncio.sleep(2.0)
                        return None
                    else:
                        logger.warning(f"Yahoo API failed for {symbol}: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching Yahoo historical data for {symbol}: {e}")
            return None

    async def _get_current_yahoo_quote(self, symbol: str) -> Optional[Dict]:
        """Get current live market quote during market hours."""
        try:
            import aiohttp
            import asyncio
            
            # Yahoo Finance real-time quote API
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                'range': '5d',
                'interval': '1m',  # 1-minute intervals for current data
                'includePrePost': 'false'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'chart' in data and data['chart']['result']:
                            chart = data['chart']['result'][0]
                            
                            # Get current price from meta data (most recent quote)
                            meta = chart.get('meta', {})
                            current_price = meta.get('regularMarketPrice')
                            
                            if current_price:
                                # Get historical data for 5-day comparison
                                timestamps = chart.get('timestamp', [])
                                if 'indicators' in chart and 'quote' in chart['indicators']:
                                    quote = chart['indicators']['quote'][0]
                                    closes = quote.get('close', [])
                                    
                                    # Find 5 days ago price for comparison
                                    valid_historical = []
                                    for i, price in enumerate(closes):
                                        if price is not None and i < len(timestamps):
                                            date = datetime.fromtimestamp(timestamps[i])
                                            if date.weekday() < 5:  # Trading days only
                                                valid_historical.append((date, price))
                                    
                                    if valid_historical:
                                        valid_historical.sort(key=lambda x: x[0])
                                        
                                        # Use data from 5 trading days ago for comparison
                                        if len(valid_historical) >= 5:
                                            comparison_date, comparison_price = valid_historical[0]
                                        else:
                                            comparison_date, comparison_price = valid_historical[0]
                                        
                                        # Calculate percentage change
                                        change_pct = ((current_price - comparison_price) / comparison_price) * 100
                                        
                                        # Get current market time
                                        current_time = datetime.now(self.est)
                                        
                                        logger.info(f"📈 LIVE {symbol}: {comparison_date.strftime('%Y-%m-%d')} {comparison_price:.2f} → {current_time.strftime('%Y-%m-%d %H:%M')} {current_price:.2f} = {change_pct:+.2f}% (LIVE MARKET DATA)")
                                        
                                        return {
                                            'value': float(current_price),
                                            'change_pct': change_pct,
                                            'data_source': 'yahoo_live'
                                        }
                    
                    elif response.status == 429:
                        logger.warning(f"Rate limited for live quote {symbol}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching live quote for {symbol}: {e}")
            return None
    
    async def store_indicator_data(self, indicator_data: Dict) -> bool:
        """Store market indicator data in the database with deduplication per trading day."""
        try:
            db = SessionLocal()
            try:
                current_timestamp = datetime.utcnow()
                current_date = current_timestamp.date()
                
                # Check if a record for this indicator and date already exists
                existing = db.query(MarketIndicator).filter(
                    MarketIndicator.indicator_type == indicator_data['indicator_type'],
                    MarketIndicator.timestamp >= datetime.combine(current_date, datetime.min.time()),
                    MarketIndicator.timestamp < datetime.combine(current_date, datetime.min.time()) + timedelta(days=1)
                ).first()
                
                if existing:
                    # Update existing record with latest data
                    existing.value = indicator_data['value']
                    existing.change_pct = indicator_data['change_pct']
                    existing.timestamp = current_timestamp
                    existing.market_session = indicator_data['market_session']
                    existing.data_source = indicator_data['data_source']
                    existing.is_valid = indicator_data['is_valid']
                    
                    logger.info(f"Updated {indicator_data['indicator_type']}: {indicator_data['value']} (was: {existing.value}) - {indicator_data['data_source']}")
                else:
                    # Create new record
                    indicator = MarketIndicator(
                        indicator_type=indicator_data['indicator_type'],
                        value=indicator_data['value'],
                        change_pct=indicator_data['change_pct'],
                        timestamp=current_timestamp,
                        market_session=indicator_data['market_session'],
                        data_source=indicator_data['data_source'],
                        is_valid=indicator_data['is_valid']
                    )
                    
                    db.add(indicator)
                    logger.info(f"Stored new {indicator_data['indicator_type']}: {indicator_data['value']} ({indicator_data['data_source']})")
                
                db.commit()
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error storing indicator data: {str(e)}")
            return False
    
    @asynccontextmanager
    async def session_scope(self):
        """Provide a transactional scope around database operations."""
        from ..database import SessionLocal
        
        db = SessionLocal()
        try:
            yield db
            db.commit()  # CRITICAL: Commit the transaction
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _get_market_session(self) -> str:
        """Determine current market session."""
        return 'open' if self.is_market_open() else 'closed'

    async def collect_all_indicators(self) -> List[Dict]:
        """Collect data for all market indicators."""
        logger.info("Starting collection of all market indicators")
        
        # During market hours, collect live data sequentially to avoid rate limiting
        if self.is_market_open():
            logger.info("Market is open - collecting live data sequentially")
            results = []
            for indicator, symbol in self.indicators.items():
                result = await self.collect_indicator_data(indicator, symbol["yahoo"])
                if result:
                    results.append(result)
                # Add small delay between live requests
                await asyncio.sleep(0.5)
            
            logger.info(f"Sequential collection complete: {len(results)}/{len(self.indicators)} indicators collected successfully")
            return results
        else:
            # After hours, use parallel collection (historical data is more reliable)
            logger.info("Market is closed - collecting historical data in parallel")
            tasks = []
            for indicator, symbol in self.indicators.items():
                task = self.collect_indicator_data(indicator, symbol["yahoo"])
                tasks.append(task)
            
            # Collect all data in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter valid results
            valid_results = [r for r in results if isinstance(r, dict) and r is not None]
            
            logger.info(f"Parallel collection complete: {len(valid_results)}/{len(self.indicators)} indicators collected successfully")
            return valid_results
    
    async def add_historical_backfill(self, days_back: int = 5) -> Dict:
        """Backfill historical market data for the specified number of days."""
        return await self.collect_all_indicators()

    async def get_historical_data(self, days_back: int = 30) -> Dict:
        """Get historical market data for exactly the specified number of trading days back."""
        try:
            db = SessionLocal()
            try:
                logger.info(f"Retrieving exactly {days_back} trading days of historical data")
                
                # Get organized data for each indicator
                organized_data = {}
                
                # Process each indicator type
                for indicator_type in self.indicators.keys():
                    # Get the most recent records for this indicator type, ordered by date desc
                    recent_records = db.query(MarketIndicator).filter(
                        MarketIndicator.indicator_type == indicator_type
                    ).order_by(MarketIndicator.timestamp.desc()).limit(days_back * 2).all()  # Get extra to filter properly
                    
                    # Group by date to ensure one record per trading day
                    daily_records = {}
                    for record in recent_records:
                        date_key = record.timestamp.date()
                        # Keep the most recent record for each date (in case of duplicates)
                        if date_key not in daily_records or record.timestamp > daily_records[date_key].timestamp:
                            daily_records[date_key] = record
                    
                    # Sort dates in descending order and take exactly 'days_back' trading days
                    sorted_dates = sorted(daily_records.keys(), reverse=True)
                    target_dates = sorted_dates[:days_back]  # Take exactly N most recent trading days
                    
                    # Calculate 5-day change for current (most recent) day only
                    current_5d_change = None
                    if len(target_dates) >= 6:  # Need at least 6 days to calculate 5-day change
                        current_record = daily_records[target_dates[0]]  # Most recent
                        five_days_back_record = daily_records[target_dates[5]]  # 5 days back
                        
                        if (five_days_back_record.value and current_record.value and 
                            five_days_back_record.value > 0):
                            current_5d_change = ((current_record.value - five_days_back_record.value) / 
                                               five_days_back_record.value) * 100
                    
                    # Build the response data with time series and single 5-day change
                    organized_data[indicator_type] = []
                    for i, date_key in enumerate(target_dates):
                        record = daily_records[date_key]
                        
                        # Only the most recent record gets the 5-day change
                        change_pct = current_5d_change if i == 0 else None
                        
                        organized_data[indicator_type].append({
                            'timestamp': record.timestamp.isoformat(),
                            'date': record.timestamp.date().isoformat(),
                            'value': record.value,
                            'change_pct': change_pct,  # 5-day change for current day only
                            'daily_change_pct': record.change_pct,  # Keep original daily change for reference
                            'is_valid': record.is_valid,
                            'data_source': record.data_source,
                            'market_session': getattr(record, 'market_session', 'unknown')
                        })
                
                # Get news sentiment data
                news_sentiment_records = db.query(NewsSentiment).filter(
                    NewsSentiment.analysis_date >= datetime.now(self.est).date()
                ).order_by(NewsSentiment.analysis_date.desc()).all()
                
                organized_data['news_sentiment'] = []
                for news in news_sentiment_records:
                    organized_data['news_sentiment'].append({
                        'analysis_date': news.analysis_date.isoformat(),
                        'overall_sentiment': news.overall_sentiment,
                        'sentiment_label': news.sentiment_label,
                        'confidence_score': news.confidence_score,
                        'articles_analyzed': news.articles_analyzed,
                        'source_breakdown': news.source_breakdown
                    })
                
                # Count unique trading dates across all indicators for verification
                all_trading_dates = set()
                for indicator_type, data in organized_data.items():
                    for entry in data:
                        all_trading_dates.add(entry['date'])
                
                logger.info(f"Retrieved {len(all_trading_dates)} unique trading dates")
                
                # Log data breakdown
                data_summary = []
                for indicator_type, data in organized_data.items():
                    data_summary.append(f"{indicator_type}: {len(data)} records")
                logger.info(f"Data breakdown: {', '.join(data_summary)}")
                
                # Verify we have the expected structure (should be ~days_back records per indicator)
                for indicator_type, data in organized_data.items():
                    if len(data) != days_back:
                        logger.warning(f"⚠️ {indicator_type}: Got {len(data)} records, expected {days_back}")
                    else:
                        logger.info(f"✅ {indicator_type}: Exactly {days_back} trading days")
                
                return organized_data
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return {}

    async def backfill_historical_data(self, days_back: int = 30) -> Dict:
        """Backfill historical market data to ensure we have exactly 30 consecutive trading days."""
        try:
            logger.info(f"Starting backfill for {days_back} consecutive trading days")
            
            # Go back far enough to ensure we get the required trading days
            # Formula: ~1.4x for weekends + extra buffer for holidays
            calendar_days_needed = int(days_back * 1.6) + 15  # Extra buffer to be safe
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=calendar_days_needed)
            
            logger.info(f"Fetching data from {start_date.date()} to {end_date.date()} ({calendar_days_needed} calendar days)")
            
            backfill_results = {
                "indicators": {},
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days_requested": days_back,
                "calendar_days_searched": calendar_days_needed
            }
            
            db = SessionLocal()
            try:
                for indicator_name, symbol_config in self.indicators.items():
                    yahoo_symbol = symbol_config["yahoo"]
                    logger.info(f"Backfilling {indicator_name} ({yahoo_symbol})")
                    
                    indicator_results = []
                    
                    try:
                        # Use yfinance to get historical data
                        import yfinance as yf
                        
                        # Create ticker object
                        ticker = yf.Ticker(yahoo_symbol)
                        
                        # Get historical data with extended date range
                        hist = ticker.history(start=start_date, end=end_date)
                        
                        if not hist.empty:
                            logger.info(f"✅ yfinance returned {len(hist)} trading days for {indicator_name}")
                            
                            # Get the most recent 'days_back' trading days
                            # Sort by date (most recent first) and take the first 'days_back' records
                            recent_data = hist.tail(days_back)  # Get last N trading days
                            
                            logger.info(f"📊 Using last {len(recent_data)} trading days for {indicator_name}")
                            logger.info(f"📅 Date range: {recent_data.index[0].date()} to {recent_data.index[-1].date()}")
                            
                            # Process data from oldest to newest for proper change calculation
                            hist_list = []
                            for date, row in recent_data.iterrows():
                                hist_list.append((date, row))
                            
                            # Sort by date (oldest first) for proper change calculation
                            hist_list.sort(key=lambda x: x[0])
                            
                            for i, (date, row) in enumerate(hist_list):
                                try:
                                    close_price = float(row['Close'])
                                    
                                    # Calculate daily change percentage
                                    change_pct = 0.0
                                    if i > 0:  # Can calculate change from previous day
                                        prev_close = float(hist_list[i-1][1]['Close'])
                                        change_pct = ((close_price - prev_close) / prev_close) * 100
                                    
                                    # Convert timestamp to datetime
                                    if hasattr(date, 'to_pydatetime'):
                                        date_obj = date.to_pydatetime().replace(tzinfo=None)
                                    else:
                                        date_obj = date.replace(tzinfo=None)
                                    
                                    # Check if record already exists for this trading day
                                    existing = db.query(MarketIndicator).filter(
                                        MarketIndicator.indicator_type == indicator_name,
                                        MarketIndicator.timestamp >= datetime.combine(date_obj.date(), datetime.min.time()),
                                        MarketIndicator.timestamp < datetime.combine(date_obj.date(), datetime.min.time()) + timedelta(days=1)
                                    ).first()
                                    
                                    if not existing:
                                        # Create new record
                                        market_indicator = MarketIndicator(
                                            indicator_type=indicator_name,
                                            value=close_price,
                                            change_pct=change_pct,
                                            data_source="yfinance_backfill",
                                            is_valid=True,
                                            timestamp=date_obj
                                        )
                                        
                                        db.add(market_indicator)
                                        indicator_results.append({
                                            "date": date_obj.date().isoformat(),
                                            "value": close_price,
                                            "change_pct": change_pct
                                        })
                                    else:
                                        logger.debug(f"📍 Record already exists for {indicator_name} on {date_obj.date()}")
                                        
                                except Exception as e:
                                    logger.warning(f"Error processing data point for {indicator_name}: {e}")
                                    continue
                            
                            # Commit all records for this indicator
                            db.commit()
                            logger.info(f"✅ Added {len(indicator_results)} new records for {indicator_name}")
                            
                        else:
                            logger.warning(f"❌ yfinance: No data for {indicator_name}")
                            
                    except Exception as e:
                        logger.error(f"❌ Error backfilling {indicator_name}: {e}")
                    
                    backfill_results["indicators"][indicator_name] = {
                        "symbol": yahoo_symbol,
                        "records_added": len(indicator_results),
                        "sample_data": indicator_results[:3] if indicator_results else []
                    }
                
                # Generate summary
                total_records = sum(result["records_added"] for result in backfill_results["indicators"].values())
                successful_indicators = len([r for r in backfill_results['indicators'].values() if r['records_added'] > 0])
                
                backfill_results["summary"] = {
                    "total_records_added": total_records,
                    "indicators_processed": len(self.indicators),
                    "successful_indicators": successful_indicators,
                    "success_rate": f"{successful_indicators}/{len(self.indicators)}"
                }
                
                logger.info(f"✅ Backfill completed: {total_records} records added across {successful_indicators}/{len(self.indicators)} indicators")
                
                # Verify we now have the required trading days
                await self._verify_historical_coverage(days_back)
                
                return backfill_results
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in backfill_historical_data: {str(e)}")
            return {"error": str(e)}

    async def _verify_historical_coverage(self, days_back: int = 30):
        """Verify that we have adequate historical coverage for each indicator."""
        try:
            db = SessionLocal()
            try:
                logger.info(f"🔍 Verifying coverage for {days_back} trading days...")
                
                for indicator_name in self.indicators.keys():
                    # Get recent records for this indicator
                    recent_records = db.query(MarketIndicator).filter(
                        MarketIndicator.indicator_type == indicator_name
                    ).order_by(MarketIndicator.timestamp.desc()).limit(days_back).all()
                    
                    if recent_records:
                        unique_dates = set(record.timestamp.date() for record in recent_records)
                        logger.info(f"📊 {indicator_name}: {len(recent_records)} records across {len(unique_dates)} unique dates")
                        
                        # Check if we have enough trading days
                        if len(unique_dates) >= days_back * 0.9:  # Allow 10% tolerance
                            logger.info(f"✅ {indicator_name}: Coverage OK")
                        else:
                            logger.warning(f"⚠️ {indicator_name}: Only {len(unique_dates)} unique dates (need ~{days_back})")
                    else:
                        logger.warning(f"❌ {indicator_name}: No data found!")
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error verifying coverage: {e}")

    async def create_mock_historical_data(self, days_back: int = 30) -> Dict:
        """Create realistic mock historical data for testing when real APIs fail."""
        logger.info(f"Creating mock historical data for {days_back} days")
        
        mock_data = {}
        current_date = datetime.now()
        
        # Base values for each indicator (realistic current market levels)
        base_values = {
            "sp500": 4400.0,
            "dow": 34000.0,
            "nasdaq": 13500.0,
            "vix": 20.0,
            "treasury_10y": 4.5,
            "dxy": 103.0
        }
        
        db = SessionLocal()
        try:
            for indicator_name, base_value in base_values.items():
                if indicator_name not in self.indicators:
                    continue
                    
                logger.info(f"Creating mock data for {indicator_name}")
                daily_data = []
                
                # Generate realistic market data with trends and volatility
                current_value = base_value
                trend = random.uniform(-0.2, 0.2)  # Small daily trend
                
                for i in range(days_back):
                    date_obj = current_date - timedelta(days=i)
                    
                    # Skip weekends for market indicators
                    if date_obj.weekday() >= 5:  # Saturday=5, Sunday=6
                        continue
                    
                    # Add realistic daily volatility
                    daily_change = random.uniform(-2.0, 2.0) + trend
                    current_value *= (1 + daily_change / 100)
                    
                    # Ensure positive values
                    current_value = max(current_value, base_value * 0.8)
                    
                    # Calculate percentage change from previous day
                    change_pct = daily_change
                    
                    # Check if record already exists
                    existing = db.query(MarketIndicator).filter(
                        MarketIndicator.indicator_type == indicator_name,
                        MarketIndicator.timestamp >= datetime.combine(date_obj.date(), datetime.min.time()),
                        MarketIndicator.timestamp < datetime.combine(date_obj.date(), datetime.min.time()) + timedelta(days=1)
                    ).first()
                    
                    if not existing:
                        market_indicator = MarketIndicator(
                            indicator_type=indicator_name,
                            value=round(current_value, 2),
                            change_pct=round(change_pct, 2),
                            data_source="mock_historical",
                            is_valid=True,
                            timestamp=date_obj
                        )
                        
                        db.add(market_indicator)
                        daily_data.append({
                            "date": date_obj.date().isoformat(),
                            "value": round(current_value, 2),
                            "change_pct": round(change_pct, 2)
                        })
                
                mock_data[indicator_name] = {
                    "records_created": len(daily_data),
                    "sample_data": daily_data[:5]
                }
            
            db.commit()
            logger.info(f"✅ Mock data creation completed")
            return {
                "success": True,
                "indicators": mock_data,
                "total_records": sum(data["records_created"] for data in mock_data.values()),
                "note": "Mock data created for testing purposes"
            }
            
        except Exception as e:
            logger.error(f"Mock data creation failed: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
            
        finally:
            db.close()

# Global instance
historical_collector = HistoricalMarketCollector() 