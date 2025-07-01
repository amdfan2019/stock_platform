"""
LLM-Based Market Sentiment Analyzer

Uses Gemini LLM to analyze historical market data and generate sentiment analysis.
"""

import json
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import google.generativeai as genai
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import MarketSentimentAnalysis
from ..config import settings
from .historical_market_collector import historical_collector

class LLMSentimentAnalyzer:
    """Uses LLM to analyze market sentiment from historical data."""
    
    def __init__(self):
        # Configure Gemini
        if hasattr(settings, 'google_api_key') and settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)
            self.model = genai.GenerativeModel(settings.llm_model)
        else:
            logger.warning("No Google API key found - LLM sentiment analysis disabled")
            self.model = None
    
    async def generate_sentiment_analysis(self, days_back: int = 30) -> Optional[Dict]:
        """Generate comprehensive sentiment analysis using Gemini."""
        
        if not self.model:
            logger.error("LLM model not configured - cannot generate sentiment analysis")
            return None
        
        try:
            # Get historical market data for time series analysis
            logger.info(f"Retrieving {days_back} days of historical market data for LLM analysis")
            historical_data = await historical_collector.get_historical_data(days_back)
            
            # ALSO get fresh current market indicators (for accurate current values)
            logger.info("Collecting FRESH current market indicators for LLM analysis")
            fresh_current_data = {}
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
                    fresh_indicator = await historical_collector.collect_indicator_data(indicator_type, symbol)
                    if fresh_indicator:
                        fresh_current_data[indicator_type] = {
                            'current_value': fresh_indicator['value'],
                            'current_change_pct': fresh_indicator['change_pct'],
                            'data_source': fresh_indicator['data_source']
                        }
                        logger.info(f"LLM Fresh {indicator_type}: {fresh_indicator['value']:.2f} ({fresh_indicator['change_pct']:+.2f}%)")
                except Exception as e:
                    logger.error(f"Error collecting fresh {indicator_type} for LLM: {e}")
            
            if not historical_data:
                logger.error("No historical data available for sentiment analysis")
                return None
            
            # Collect enhanced sentiment data (Fear & Greed Index)
            logger.info("Collecting enhanced sentiment data (Fear & Greed Index)")
            try:
                from .market_sentiment_collector import market_sentiment_collector
                enhanced_sentiment = await market_sentiment_collector.collect_all_sentiment_data()
                logger.info(f"Enhanced sentiment sources: {list(enhanced_sentiment.keys()) if enhanced_sentiment else 'None'}")
            except Exception as e:
                logger.warning(f"Could not collect enhanced sentiment data: {e}")
                enhanced_sentiment = None
            
            # Prepare data summary for LLM (combining historical + fresh current data)
            data_summary = self._prepare_data_summary(historical_data, fresh_current_data)
            
            # Add enhanced sentiment data to summary
            if enhanced_sentiment:
                data_summary['enhanced_sentiment'] = enhanced_sentiment
                logger.info(f"Added enhanced sentiment data to LLM analysis")
            
            # Generate LLM analysis
            analysis = await self._analyze_with_gemini(data_summary, days_back)
            
            if analysis:
                # Add metadata about data sources
                analysis['data_sources'] = {
                    'historical_indicators': list(historical_data.keys()),
                    'fresh_current_indicators': list(fresh_current_data.keys()),
                    'enhanced_sentiment': list(enhanced_sentiment.keys()) if enhanced_sentiment else [],
                    'total_days_analyzed': days_back
                }
                
                # Store analysis in database
                await self._store_analysis(analysis, historical_data)
                return analysis
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating sentiment analysis: {str(e)}")
            return None
    
    def _prepare_data_summary(self, historical_data: Dict, fresh_current_data: Dict) -> Dict:
        """Prepare a summary of historical data for LLM analysis."""
        try:
            summary = {
                'data_period': {
                    'start_date': None,
                    'end_date': datetime.now().isoformat(),
                    'total_days': 0
                },
                'market_indicators': {},
                'data_completeness': {},
                'full_time_series': {}  # Add full historical data for LLM analysis
            }
            
            # Process market indicators
            for indicator_type, data_points in historical_data.items():
                if not data_points:
                    continue
                    
                # Sort by timestamp (most recent first)
                valid_points = [p for p in data_points if p.get('is_valid', False) and p.get('value') is not None]
                valid_points.sort(key=lambda x: x['timestamp'], reverse=True)
                
                if valid_points:
                    # Get latest and oldest for trend calculation
                    latest = valid_points[0]  # Most recent from historical data
                    oldest = valid_points[-1] if len(valid_points) > 1 else latest
                    
                    # Calculate overall period trend
                    if len(valid_points) >= 2 and oldest['value'] and latest['value']:
                        period_trend_pct = ((latest['value'] - oldest['value']) / oldest['value']) * 100
                    else:
                        period_trend_pct = latest.get('change_pct', 0.0)
                    
                    # Use FRESH current data if available, otherwise fall back to historical latest
                    if indicator_type in fresh_current_data:
                        fresh_data = fresh_current_data[indicator_type]
                        current_value = fresh_data['current_value']
                        recent_change_pct = fresh_data['current_change_pct']  # FRESH 5-day change
                        logger.info(f"LLM using FRESH data for {indicator_type}: {current_value:.2f} ({recent_change_pct:+.2f}%)")
                    else:
                        current_value = latest['value']
                        recent_change_pct = latest.get('change_pct', 0.0)  # Stale historical change
                        logger.warning(f"LLM using stale data for {indicator_type}: {current_value:.2f} ({recent_change_pct:+.2f}%)")
                    
                    # Summary statistics (for overview) - NOW USES FRESH DATA
                    summary['market_indicators'][indicator_type] = {
                        'current_value': current_value,
                        'recent_change_pct': recent_change_pct,  # FRESH 5-day change
                        'period_trend_pct': period_trend_pct,
                        'data_points_count': len(valid_points),
                        'latest_timestamp': latest['timestamp'],
                        'data_freshness': 'fresh' if indicator_type in fresh_current_data else 'historical'
                    }
                    
                    # Full time series data (for detailed LLM analysis)
                    summary['full_time_series'][indicator_type] = []
                    for point in valid_points[:30]:  # Last 30 data points for analysis
                        summary['full_time_series'][indicator_type].append({
                            'date': point['timestamp'].split('T')[0],  # Extract date
                            'value': point['value'],
                            'change_pct': point.get('change_pct', 0.0),
                            'data_source': point.get('data_source', 'unknown')
                        })
                    
                    # Track data completeness
                    total_points = len(data_points)
                    valid_points_count = len(valid_points)
                    summary['data_completeness'][indicator_type] = (valid_points_count / total_points * 100) if total_points > 0 else 0
            
            # Set data period
            all_timestamps = []
            for indicator_data in historical_data.values():
                if isinstance(indicator_data, list):
                    for point in indicator_data:
                        if 'timestamp' in point:
                            all_timestamps.append(point['timestamp'])
                        elif 'survey_date' in point:
                            all_timestamps.append(point['survey_date'])
            
            if all_timestamps:
                all_timestamps.sort()
                summary['data_period']['start_date'] = all_timestamps[-1]  # Oldest
                summary['data_period']['end_date'] = all_timestamps[0]     # Most recent
                summary['data_period']['total_days'] = len(set([ts.split('T')[0] for ts in all_timestamps if 'T' in ts]))
            
            # Add fresh data summary
            fresh_indicators_count = len(fresh_current_data)
            logger.info(f"Prepared data summary for {len(summary['market_indicators'])} indicators with {summary['data_period']['total_days']} days of data. Fresh current data: {fresh_indicators_count} indicators.")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error preparing data summary: {str(e)}")
            return {}
    
    async def _analyze_with_gemini(self, data_summary: Dict, days_back: int) -> Optional[Dict]:
        """Use Gemini to analyze market sentiment."""
        try:
            prompt = f"""
You are a professional financial analyst providing market sentiment analysis to investors. Analyze the following comprehensive market data from the past {days_back} days and provide a clear, client-focused sentiment assessment.

IMPORTANT: Use the 'full_time_series' data below for your analysis. This contains daily values for each indicator over the full {days_back}-day period.

MARKET DATA SUMMARY:
{json.dumps(data_summary, indent=2)}

ANALYSIS INSTRUCTIONS:
1. **Client-Focused Language**: Write for investors, avoid technical jargon like "dataset", "database", or "data points"
2. **Don't Repeat Visible Data**: Users can already see current 5-day changes, focus on trends and context instead
3. **Recent Market Context**: ALWAYS mention recent developments within the last month that could impact sentiment
4. **Earnings Season Awareness**: Consider quarterly earnings cycles (earnings season occurs after each quarter ends: Jan, Apr, Jul, Oct)
5. **Focus on Insights**: Provide interpretation and context, not just data repetition
6. **Integrated Analysis**: Combine current trends with historical context in a natural, flowing narrative

Please provide a detailed analysis in the following JSON format:

{{
    "sentiment_score": <float between 1.0 and 10.0>,
    "sentiment_label": "<one of: Extremely Bearish, Very Bearish, Bearish, Slightly Bearish, Neutral, Slightly Bullish, Bullish, Very Bullish, Extremely Bullish>",
    "confidence_level": <float between 0.0 and 1.0>,
    "trend_analysis": "<comprehensive analysis that naturally weaves together current market dynamics, historical context, and what's driving sentiment. Include recent market developments from the last month, consider earnings season timing, and draw relevant historical comparisons. Make connections between past patterns and current trends. Avoid repeating specific percentage changes visible in the UI>",
    "market_outlook": "<brief, concise forward-looking perspective - 2-3 sentences maximum, focus on key themes and potential scenarios>"
}}

ANALYSIS GUIDELINES:
1. **Client Communication**: Write clearly for investors, avoid technical database terminology
2. **Pattern Recognition**: Look for meaningful trends, reversals, and momentum shifts
3. **Market Context**: Provide broader market perspective without repeating visible percentage changes
4. **Volatility Assessment**: Use VIX trends to gauge fear/greed cycles and market stress
5. **Cross-Asset Insights**: Consider how equity, bond, and dollar movements interact
6. **Recent Market Context**: Reference recent events, policy changes, economic data, or market developments from the last 30 days
7. **Earnings Seasonality**: Consider current timing relative to quarterly earnings cycles:
   - Q1 earnings: Reports in April (companies report previous quarter ending March 31)
   - Q2 earnings: Reports in July (companies report previous quarter ending June 30)  
   - Q3 earnings: Reports in October (companies report previous quarter ending September 30)
   - Q4 earnings: Reports in January (companies report previous quarter ending December 31)
8. **Forward-Looking**: Provide actionable insights for investment decisions
9. **Historical Integration**: Weave historical context naturally into the trend analysis instead of separating it

SENTIMENT SCALE (1-10):
- 1-2: Extremely/Very Bearish (sustained declines, high volatility, risk-off)
- 3-4: Bearish/Slightly Bearish (downward bias, elevated caution)
- 5-6: Neutral/Slightly Bullish (mixed signals, consolidation phases)
- 7-8: Bullish/Very Bullish (upward momentum, risk-on sentiment)
- 9-10: Extremely Bullish (euphoric conditions, potential overextension)

Focus on providing clear, actionable analysis that helps investors understand current market conditions.
"""

            response = await self.model.generate_content_async(prompt)
            
            if response and response.text:
                # Extract JSON from response
                analysis_json = self._extract_json_from_response(response.text)
                
                if analysis_json:
                    # Validate the analysis
                    validated_analysis = self._validate_analysis(analysis_json)
                    
                    if validated_analysis:
                        logger.info(f"Generated LLM sentiment analysis: {validated_analysis['sentiment_score']}/10 ({validated_analysis['sentiment_label']})")
                        return validated_analysis
            
            logger.error("Failed to generate valid sentiment analysis from LLM")
            return None
            
        except Exception as e:
            logger.error(f"Error in Gemini analysis: {str(e)}")
            return None
    
    def _extract_json_from_response(self, response_text: str) -> Optional[Dict]:
        """Extract and parse JSON from LLM response."""
        try:
            # Look for JSON block
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Look for JSON without markdown
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    logger.error("No JSON found in LLM response")
                    return None
            
            # Parse JSON
            analysis = json.loads(json_str)
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error extracting JSON from response: {str(e)}")
            return None
    
    def _validate_analysis(self, analysis: Dict) -> Optional[Dict]:
        """Validate and clean the LLM analysis response."""
        try:
            required_fields = ['sentiment_score', 'sentiment_label', 'confidence_level', 'trend_analysis', 'market_outlook']
            
            # Check required fields
            for field in required_fields:
                if field not in analysis:
                    logger.error(f"Missing required field: {field}")
                    return None
            
            # Validate sentiment score
            score = float(analysis['sentiment_score'])
            if not (1.0 <= score <= 10.0):
                logger.error(f"Invalid sentiment score: {score}")
                return None
            
            # Validate confidence level
            confidence = float(analysis['confidence_level'])
            if not (0.0 <= confidence <= 1.0):
                logger.error(f"Invalid confidence level: {confidence}")
                return None
            
            # Clean up text fields
            text_fields = ['sentiment_label', 'trend_analysis', 'market_outlook']
            for field in text_fields:
                if field in analysis and analysis[field]:
                    analysis[field] = str(analysis[field]).strip()
            
            return analysis
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error validating analysis: {str(e)}")
            return None
    
    async def _store_analysis(self, analysis: Dict, historical_data: Dict) -> bool:
        """Store the sentiment analysis in the database."""
        try:
            db = SessionLocal()
            try:
                # Get data period
                data_period_start = None
                data_period_end = datetime.utcnow()
                
                # Find oldest data point
                all_timestamps = []
                for indicator_data in historical_data.values():
                    if isinstance(indicator_data, list):
                        for point in indicator_data:
                            if 'timestamp' in point:
                                try:
                                    ts = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00'))
                                    all_timestamps.append(ts)
                                except:
                                    pass
                
                if all_timestamps:
                    data_period_start = min(all_timestamps)
                
                # Create analysis record
                sentiment_analysis = MarketSentimentAnalysis(
                    analysis_date=datetime.utcnow(),
                    sentiment_score=analysis['sentiment_score'],
                    sentiment_label=analysis['sentiment_label'],
                    confidence_level=analysis['confidence_level'],
                    key_factors=[],  # Removed from LLM response
                    trend_analysis=analysis.get('trend_analysis', ''),
                    historical_context=analysis.get('historical_context', ''),
                    market_outlook=analysis.get('market_outlook', ''),
                    data_period_start=data_period_start,
                    data_period_end=data_period_end,
                    indicators_analyzed=list(historical_data.keys())
                )
                
                db.add(sentiment_analysis)
                db.commit()
                
                logger.info(f"Stored sentiment analysis: {analysis['sentiment_score']}/10 ({analysis['sentiment_label']})")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error storing sentiment analysis: {str(e)}")
            return False
    
    async def get_latest_analysis(self) -> Optional[Dict]:
        """Get the most recent sentiment analysis."""
        try:
            db = SessionLocal()
            try:
                latest = db.query(MarketSentimentAnalysis).order_by(
                    MarketSentimentAnalysis.analysis_date.desc()
                ).first()
                
                if latest:
                    return {
                        'analysis_date': latest.analysis_date.isoformat(),
                        'sentiment_score': latest.sentiment_score,
                        'sentiment_label': latest.sentiment_label,
                        'confidence_level': latest.confidence_level,
                        'key_factors': latest.key_factors,
                        'trend_analysis': latest.trend_analysis,
                        'historical_context': latest.historical_context,
                        'market_outlook': latest.market_outlook,
                        'data_period_start': latest.data_period_start.isoformat() if latest.data_period_start else None,
                        'data_period_end': latest.data_period_end.isoformat() if latest.data_period_end else None,
                        'indicators_analyzed': latest.indicators_analyzed
                    }
                
                return None
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting latest analysis: {str(e)}")
            return None

# Global instance
llm_sentiment_analyzer = LLMSentimentAnalyzer() 