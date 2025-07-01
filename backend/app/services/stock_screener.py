import pandas as pd
import numpy as np
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.timeseries import TimeSeries
import ta
import asyncio
import aiohttp
import time
import requests
import os
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from ..config import settings
from loguru import logger


class StockScreener:
    """
    Core engine for analyzing stocks using fundamental and technical analysis.
    Uses direct API calls to avoid rate limiting issues with yfinance.
    """
    
    def __init__(self):
        # Alpha Vantage setup - use environment variable directly if settings key is empty
        api_key = settings.alpha_vantage_api_key or os.getenv('ALPHAVANTAGE_API_KEY')
        if not api_key:
            logger.warning("No Alpha Vantage API key found - some features may be limited")
            self.av_fundamental = None
            self.av_timeseries = None
        else:
            self.av_fundamental = FundamentalData(key=api_key)
            self.av_timeseries = TimeSeries(key=api_key)
        self.last_request_time = {}
        self.cache = {}  # Simple in-memory cache
        
        # Headers for Yahoo Finance direct API
        self.yahoo_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    
    async def analyze_stock(self, ticker: str) -> Dict:
        """
        Comprehensive stock analysis using working API endpoints.
        """
        try:
            logger.info(f"Starting analysis for {ticker}")
            
            # Check cache first
            cache_key = f"stock_data_{ticker}"
            if cache_key in self.cache:
                cache_time = self.cache[cache_key].get('timestamp', datetime.min)
                if datetime.now() - cache_time < timedelta(minutes=15):  # 15-minute cache
                    logger.info(f"Using cached data for {ticker}")
                    return self.cache[cache_key]['data']
            
            # Get data from multiple sources concurrently
            tasks = [
                self._get_alpha_vantage_quote(ticker),
                self._get_alpha_vantage_fundamentals(ticker),
                self._get_yahoo_current_data(ticker),
                self._get_yahoo_historical_data(ticker)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            av_quote, av_fundamentals, yahoo_current, yahoo_historical = results
            
            # Combine all successful data
            result = await self._combine_data_sources(ticker, av_quote, av_fundamentals, yahoo_current, yahoo_historical)
            
            # Cache successful result
            if result.get('current_price'):
                self.cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.now()
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {str(e)}")
            return await self._create_minimal_response(ticker)
    
    async def _get_alpha_vantage_quote(self, ticker: str) -> Dict:
        """Get current quote from Alpha Vantage (free tier)."""
        try:
            if not self.av_timeseries:
                return {}
                
            # Rate limiting
            await self._rate_limit("alpha_vantage", 12)  # 5 requests per minute
            
            data, _ = self.av_timeseries.get_quote_endpoint(ticker)
            if data:
                logger.info(f"Alpha Vantage quote success for {ticker}")
                return {
                    'source': 'alpha_vantage_quote',
                    'current_price': float(data.get('05. price', 0)),
                    'volume': int(data.get('06. volume', 0)),
                    'previous_close': float(data.get('08. previous close', 0)),
                    'change_percent': data.get('10. change percent', '0%').replace('%', ''),
                }
            return {}
        except Exception as e:
            logger.warning(f"Alpha Vantage quote failed for {ticker}: {str(e)}")
            return {}
    
    async def _get_alpha_vantage_fundamentals(self, ticker: str) -> Dict:
        """Get fundamental data from Alpha Vantage (working endpoint)."""
        try:
            if not self.av_fundamental:
                return {}
                
            # Rate limiting
            await self._rate_limit("alpha_vantage_fund", 12)
            
            data, _ = self.av_fundamental.get_company_overview(ticker)
            if data:
                logger.info(f"Alpha Vantage fundamentals success for {ticker}")
                return {
                    'source': 'alpha_vantage_fundamentals',
                    'company_name': data.get('Name', ticker),
                    'sector': data.get('Sector'),
                    'industry': data.get('Industry'),
                    'market_cap': self._safe_float(data.get('MarketCapitalization')),
                    'pe_ratio': self._safe_float(data.get('PERatio')),
                    'forward_pe': self._safe_float(data.get('ForwardPE')),
                    'price_to_book': self._safe_float(data.get('PriceToBookRatio')),
                    'debt_to_equity': self._safe_float(data.get('DebtToEquityRatio')),
                    'return_on_equity': self._safe_float(data.get('ReturnOnEquityTTM')),
                    'dividend_yield': self._safe_float(data.get('DividendYield')),
                    'profit_margin': self._safe_float(data.get('ProfitMargin')),
                    'book_value': self._safe_float(data.get('BookValue')),
                    'earnings_per_share': self._safe_float(data.get('EPS')),
                }
            return {}
        except Exception as e:
            logger.warning(f"Alpha Vantage fundamentals failed for {ticker}: {str(e)}")
            return {}
    
    async def _get_yahoo_current_data(self, ticker: str) -> Dict:
        """Get current data from Yahoo Finance direct API."""
        try:
            # Rate limiting
            await self._rate_limit("yahoo_current", 1)
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.yahoo_headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "chart" in data and data["chart"]["result"]:
                            result = data["chart"]["result"][0]
                            meta = result["meta"]
                            
                            logger.info(f"Yahoo current data success for {ticker}")
                            return {
                                'source': 'yahoo_current',
                                'current_price': meta.get('regularMarketPrice'),
                                'company_name': meta.get('longName', ticker),
                                'currency': meta.get('currency'),
                                'exchange': meta.get('exchangeName'),
                                'market_state': meta.get('marketState'),
                                'previous_close': meta.get('previousClose'),
                                'day_high': meta.get('regularMarketDayHigh'),
                                'day_low': meta.get('regularMarketDayLow'),
                            }
            return {}
        except Exception as e:
            logger.warning(f"Yahoo current data failed for {ticker}: {str(e)}")
            return {}
    
    async def _get_yahoo_historical_data(self, ticker: str) -> Dict:
        """Get historical data from Yahoo Finance for technical analysis."""
        try:
            # Rate limiting
            await self._rate_limit("yahoo_historical", 1)
            
            # Get 3 months of daily data
            period1 = int((datetime.now() - timedelta(days=90)).timestamp())
            period2 = int(datetime.now().timestamp())
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={period1}&period2={period2}&interval=1d"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.yahoo_headers, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "chart" in data and data["chart"]["result"]:
                            result = data["chart"]["result"][0]
                            
                            timestamps = result["timestamp"]
                            ohlcv = result["indicators"]["quote"][0]
                            
                            # Create DataFrame
                            df = pd.DataFrame({
                                'Open': ohlcv['open'],
                                'High': ohlcv['high'],
                                'Low': ohlcv['low'],
                                'Close': ohlcv['close'],
                                'Volume': ohlcv['volume']
                            }, index=pd.to_datetime(timestamps, unit='s'))
                            
                            # Remove NaN rows
                            df = df.dropna()
                            
                            if len(df) > 50:  # Need enough data for technical analysis
                                technical_indicators = await self._calculate_technical_indicators(df)
                                
                                logger.info(f"Yahoo historical data success for {ticker} ({len(df)} days)")
                                return {
                                    'source': 'yahoo_historical',
                                    'data_points': len(df),
                                    'latest_close': df['Close'].iloc[-1],
                                    **technical_indicators
                                }
            return {}
        except Exception as e:
            logger.warning(f"Yahoo historical data failed for {ticker}: {str(e)}")
            return {}
    
    async def _combine_data_sources(self, ticker: str, av_quote: Dict, av_fundamentals: Dict, 
                                  yahoo_current: Dict, yahoo_historical: Dict) -> Dict:
        """Combine data from all successful sources."""
        
        # Start with base structure
        result = {
            "ticker": ticker,
            "timestamp": datetime.now(),
            "data_sources": []
        }
        
        # Determine best current price
        current_price = None
        if av_quote and av_quote.get('current_price'):
            current_price = av_quote['current_price']
            result["data_sources"].append("alpha_vantage_quote")
        elif yahoo_current and yahoo_current.get('current_price'):
            current_price = yahoo_current['current_price']
            result["data_sources"].append("yahoo_current")
        elif yahoo_historical and yahoo_historical.get('latest_close'):
            current_price = yahoo_historical['latest_close']
            result["data_sources"].append("yahoo_historical")
        
        result["current_price"] = current_price
        
        # Company info (prefer Alpha Vantage, fallback to Yahoo)
        if av_fundamentals:
            result.update({
                "company_name": av_fundamentals.get('company_name', ticker),
                "sector": av_fundamentals.get('sector'),
                "industry": av_fundamentals.get('industry'),
                "market_cap": av_fundamentals.get('market_cap'),
                "pe_ratio": av_fundamentals.get('pe_ratio'),
                "forward_pe": av_fundamentals.get('forward_pe'),
                "price_to_book": av_fundamentals.get('price_to_book'),
                "debt_to_equity": av_fundamentals.get('debt_to_equity'),
                "return_on_equity": av_fundamentals.get('return_on_equity'),
                "dividend_yield": av_fundamentals.get('dividend_yield'),
                "profit_margin": av_fundamentals.get('profit_margin'),
                "earnings_per_share": av_fundamentals.get('earnings_per_share'),
            })
            result["data_sources"].append("alpha_vantage_fundamentals")
        elif yahoo_current:
            result.update({
                "company_name": yahoo_current.get('company_name', ticker),
                "sector": None,
                "industry": None,
                "market_cap": None,
                "pe_ratio": None,
                "forward_pe": None,
                "price_to_book": None,
                "debt_to_equity": None,
                "return_on_equity": None,
            })
        else:
            result.update({
                "company_name": ticker,
                "sector": None,
                "industry": None,
                "market_cap": None,
                "pe_ratio": None,
                "forward_pe": None,
                "price_to_book": None,
                "debt_to_equity": None,
                "return_on_equity": None,
            })
        
        # Technical indicators from Yahoo historical
        if yahoo_historical:
            for key, value in yahoo_historical.items():
                if key not in ['source', 'data_points', 'latest_close']:
                    result[key] = value
            result["data_sources"].append("yahoo_historical")
        
        # Market data from various sources
        if av_quote:
            result.update({
                "volume": av_quote.get('volume'),
                "previous_close": av_quote.get('previous_close'),
                "change_percent": av_quote.get('change_percent'),
            })
        elif yahoo_current:
            result.update({
                "previous_close": yahoo_current.get('previous_close'),
                "day_high": yahoo_current.get('day_high'),
                "day_low": yahoo_current.get('day_low'),
                "exchange": yahoo_current.get('exchange'),
            })
        
        # Calculate quality score
        result["quality_score"] = await self._calculate_quality_score(result)
        
        logger.info(f"Combined data for {ticker} from sources: {result['data_sources']}")
        return result
    
    async def _calculate_quality_score(self, data: Dict) -> float:
        """Calculate investment quality score based on available data."""
        try:
            score = 50.0  # Base score
            
            # Fundamental scoring
            if data.get("pe_ratio"):
                pe = data["pe_ratio"]
                if 10 < pe < 25:
                    score += 15
                elif 5 < pe <= 10:
                    score += 10
                elif pe > 40:
                    score -= 15
            
            if data.get("return_on_equity"):
                roe = data["return_on_equity"]
                if roe > 0.20:  # 20% ROE excellent
                    score += 15
                elif roe > 0.15:  # 15% ROE good
                    score += 10
                elif roe < 0:  # Negative ROE bad
                    score -= 10
            
            if data.get("debt_to_equity"):
                de = data["debt_to_equity"]
                if de < 0.3:  # Low debt good
                    score += 10
                elif de > 1.0:  # High debt concerning
                    score -= 10
            
            if data.get("profit_margin"):
                margin = data["profit_margin"]
                if margin > 0.20:  # 20% margin excellent
                    score += 10
                elif margin > 0.10:  # 10% margin good
                    score += 5
                elif margin < 0:  # Negative margin bad
                    score -= 15
            
            # Technical scoring
            if data.get("rsi_14"):
                rsi = data["rsi_14"]
                if 40 < rsi < 60:  # Neutral zone good
                    score += 5
                elif rsi < 30:  # Oversold might be opportunity
                    score += 10
                elif rsi > 80:  # Overbought concerning
                    score -= 10
            
            if data.get("sma_50") and data.get("current_price"):
                price = data["current_price"]
                sma50 = data["sma_50"]
                if price > sma50:  # Above 50-day average
                    score += 5
            
            # Momentum scoring
            if data.get("momentum_score"):
                momentum = data["momentum_score"]
                if momentum > 10:
                    score += 10
                elif momentum < -10:
                    score -= 10
            
            return max(0, min(100, score))
            
        except Exception:
            return 50.0
    
    async def _rate_limit(self, source: str, wait_seconds: int):
        """Rate limiting helper."""
        if source in self.last_request_time:
            elapsed = time.time() - self.last_request_time[source]
            if elapsed < wait_seconds:
                await asyncio.sleep(wait_seconds - elapsed)
        self.last_request_time[source] = time.time()
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        try:
            if value in [None, '', 'None', 'N/A']:
                return None
            return float(value)
        except (ValueError, TypeError):
            return None
    
    async def _create_minimal_response(self, ticker: str) -> Dict:
        """Create minimal response when all data sources fail."""
        return {
            "ticker": ticker,
            "company_name": ticker,
            "sector": None,
            "industry": None,
            "market_cap": None,
            "current_price": None,
            "timestamp": datetime.now(),
            "pe_ratio": None,
            "forward_pe": None,
            "price_to_book": None,
            "debt_to_equity": None,
            "return_on_equity": None,
            "quality_score": 50.0,
            "data_sources": [],
            "error": "All data sources failed"
        }
    
    async def _calculate_technical_indicators(self, hist_data: pd.DataFrame) -> Dict:
        """Calculate technical indicators from historical data."""
        try:
            if len(hist_data) < 50:
                logger.warning("Insufficient data for technical analysis")
                return {}
            
            close_prices = hist_data['Close']
            volume = hist_data['Volume']
            
            indicators = {}
            
            # Moving averages
            if len(hist_data) >= 50:
                indicators["sma_50"] = close_prices.rolling(window=50).mean().iloc[-1]
            if len(hist_data) >= 200:
                indicators["sma_200"] = close_prices.rolling(window=200).mean().iloc[-1]
            
            # RSI
            if len(hist_data) >= 14:
                indicators["rsi_14"] = ta.momentum.rsi(close_prices, window=14).iloc[-1]
            
            # MACD
            if len(hist_data) >= 26:
                macd_line = ta.trend.macd(close_prices).iloc[-1]
                macd_signal_line = ta.trend.macd_signal(close_prices).iloc[-1]
                indicators["macd_signal"] = "bullish" if macd_line > macd_signal_line else "bearish"
            
            # Bollinger Bands
            if len(hist_data) >= 20:
                bb_upper = ta.volatility.bollinger_hband(close_prices).iloc[-1]
                bb_lower = ta.volatility.bollinger_lband(close_prices).iloc[-1]
                current_price = close_prices.iloc[-1]
                indicators["bollinger_position"] = (current_price - bb_lower) / (bb_upper - bb_lower) - 0.5
            
            # Volume analysis
            if len(hist_data) >= 50:
                avg_volume_50 = volume.rolling(window=50).mean().iloc[-1]
                current_volume = volume.iloc[-1]
                indicators["avg_volume_50"] = avg_volume_50
                indicators["volume_ratio"] = current_volume / avg_volume_50 if avg_volume_50 > 0 else 1
            
            # Momentum score
            if len(hist_data) >= 50:
                indicators["momentum_score"] = await self._calculate_momentum_score(hist_data)
            
            return indicators
            
        except Exception as e:
            logger.warning(f"Error calculating technical indicators: {str(e)}")
            return {}
    
    async def _calculate_momentum_score(self, hist_data: pd.DataFrame) -> float:
        """Calculate momentum score from price and volume trends."""
        try:
            close_prices = hist_data['Close']
            volume = hist_data['Volume']
            
            # Price momentum (20-day vs 50-day performance)
            if len(hist_data) >= 50:
                price_20d = close_prices.rolling(window=20).mean().iloc[-1]
                price_50d = close_prices.rolling(window=50).mean().iloc[-1]
                price_momentum = (price_20d / price_50d - 1) * 100
            else:
                price_momentum = 0
            
            # Volume momentum
            if len(hist_data) >= 50:
                volume_20d = volume.rolling(window=20).mean().iloc[-1]
                volume_50d = volume.rolling(window=50).mean().iloc[-1]
                volume_momentum = (volume_20d / volume_50d - 1) * 100 if volume_50d > 0 else 0
            else:
                volume_momentum = 0
            
            # Combined momentum score (weighted)
            momentum_score = (price_momentum * 0.7) + (volume_momentum * 0.3)
            
            # Normalize to -100 to 100 scale
            return max(-100, min(100, momentum_score))
            
        except Exception:
            return 0.0

    async def calculate_intrinsic_value(self, analysis: Dict) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate intrinsic value and margin of safety using multiple valuation approaches.
        Returns (intrinsic_value, margin_of_safety) or (None, None) if insufficient data.
        """
        try:
            current_price = analysis.get('current_price')
            if not current_price:
                return None, None
            
            # Collect valuation inputs
            pe_ratio = analysis.get('pe_ratio')
            price_to_book = analysis.get('price_to_book')
            earnings_per_share = analysis.get('earnings_per_share')
            book_value = analysis.get('book_value')
            market_cap = analysis.get('market_cap')
            
            valuations = []
            
            # Method 1: P/E based valuation (if we have EPS)
            if pe_ratio and earnings_per_share and pe_ratio > 0:
                # Use industry average P/E of 18 as fair value benchmark
                fair_pe = 18.0
                pe_based_value = earnings_per_share * fair_pe
                valuations.append(pe_based_value)
                logger.info(f"P/E based valuation: ${pe_based_value:.2f} (EPS: {earnings_per_share}, Fair P/E: {fair_pe})")
            
            # Method 2: Book value based (P/B approach)
            if price_to_book and book_value and price_to_book > 0:
                # Use P/B of 2.0 as reasonable fair value for most companies
                fair_pb = 2.0
                pb_based_value = book_value * fair_pb
                valuations.append(pb_based_value)
                logger.info(f"P/B based valuation: ${pb_based_value:.2f} (Book: {book_value}, Fair P/B: {fair_pb})")
            
            # Method 3: DCF approximation using current metrics
            if earnings_per_share and earnings_per_share > 0:
                # Simple DCF: EPS * growth_multiple * discount_factor
                # Assume 8% growth, 10% discount rate, 10 year horizon
                growth_rate = 0.08
                discount_rate = 0.10
                years = 10
                
                # Future EPS
                future_eps = earnings_per_share * ((1 + growth_rate) ** years)
                # Terminal P/E of 15
                terminal_value = future_eps * 15
                # Present value
                dcf_value = terminal_value / ((1 + discount_rate) ** years)
                valuations.append(dcf_value)
                logger.info(f"DCF approximation: ${dcf_value:.2f}")
            
            # Method 4: Asset-based valuation (conservative)
            if book_value:
                # Conservative asset value (80% of book value)
                asset_value = book_value * 0.8
                valuations.append(asset_value)
                logger.info(f"Asset-based valuation: ${asset_value:.2f}")
            
            if not valuations:
                logger.warning("No valuation methods could be applied - insufficient data")
                return None, None
            
            # Calculate weighted average intrinsic value
            if len(valuations) == 1:
                intrinsic_value = valuations[0]
            else:
                # Weight: P/E (40%), P/B (25%), DCF (25%), Asset (10%)
                weights = [0.4, 0.25, 0.25, 0.1][:len(valuations)]
                # Normalize weights
                weight_sum = sum(weights)
                weights = [w/weight_sum for w in weights]
                
                intrinsic_value = sum(val * weight for val, weight in zip(valuations, weights))
            
            # Calculate margin of safety
            margin_of_safety = ((intrinsic_value - current_price) / intrinsic_value) * 100
            
            logger.info(f"Calculated intrinsic value: ${intrinsic_value:.2f}, Current: ${current_price:.2f}, MoS: {margin_of_safety:.1f}%")
            
            return intrinsic_value, margin_of_safety
            
        except Exception as e:
            logger.error(f"Error calculating intrinsic value: {str(e)}")
            return None, None 