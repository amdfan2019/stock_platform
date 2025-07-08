import json
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import google.generativeai as genai
from ..config import settings
from .stock_screener import StockScreener
from .news_collector import NewsCollector
from loguru import logger
from ..models import GeminiApiCallLog


class LLMInference:
    """
    LLM-powered inference engine that combines valuation, technical, and sentiment signals
    to generate intelligent buy/sell recommendations with reasoning.
    """
    
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=settings.google_api_key)
        self.llm_model = genai.GenerativeModel(settings.llm_model)
        
        # Initialize other services
        self.stock_screener = StockScreener()
        self.news_collector = NewsCollector()
    
    async def generate_recommendation(self, ticker: str) -> Dict:
        """
        Generate comprehensive buy/sell recommendation for a stock.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary containing recommendation with reasoning and confidence
        """
        try:
            logger.info(f"Generating recommendation for {ticker}")
            
            # Gather all data sources in parallel
            tasks = [
                self._get_stock_analysis(ticker),
                self._get_news_sentiment(ticker),
                self._get_market_context()
            ]
            
            stock_analysis, news_sentiment, market_context = await asyncio.gather(*tasks)
            
            # Calculate individual signals
            valuation_signal = await self._calculate_valuation_signal(stock_analysis)
            technical_signal = await self._calculate_technical_signal(stock_analysis)
            news_signal = news_sentiment.get("overall_sentiment", 0.0)
            
            # Generate LLM-powered recommendation
            recommendation = await self._generate_llm_recommendation(
                ticker, stock_analysis, news_sentiment, market_context,
                valuation_signal, technical_signal, news_signal
            )
            
            # Calculate price ranges
            price_ranges = await self._calculate_price_ranges(stock_analysis, recommendation)
            
            # Combine everything into final recommendation
            final_recommendation = {
                "ticker": ticker,
                "action": recommendation["action"],
                "confidence_score": recommendation["confidence"],
                "reasoning": recommendation["reasoning"],
                "key_factors": recommendation["key_factors"],
                
                # Individual signals
                "valuation_signal": valuation_signal,
                "technical_signal": technical_signal,
                "news_sentiment_signal": news_signal,
                
                # Price ranges
                **price_ranges,
                
                # Risk assessment
                "risk_level": recommendation["risk_level"],
                "volatility_score": await self._calculate_volatility_score(stock_analysis),
                
                # Metadata
                "recommendation_type": "daily",
                "expires_at": datetime.now() + timedelta(days=1),
                "created_at": datetime.now(),
                "is_active": True
            }
            
            logger.info(f"Generated {recommendation['action']} recommendation for {ticker} with {recommendation['confidence']:.2f} confidence")
            return final_recommendation
            
        except Exception as e:
            logger.error(f"Error generating recommendation for {ticker}: {str(e)}")
            raise
    
    async def _get_stock_analysis(self, ticker: str) -> Dict:
        """Get comprehensive stock analysis from screener."""
        try:
            analysis = await self.stock_screener.analyze_stock(ticker)
            
            # Calculate intrinsic value
            intrinsic_value, margin_of_safety = await self.stock_screener.calculate_intrinsic_value(analysis)
            analysis["intrinsic_value_estimate"] = intrinsic_value
            analysis["margin_of_safety"] = margin_of_safety
            
            return analysis
            
        except Exception as e:
            logger.warning(f"Error getting stock analysis: {str(e)}")
            return {}
    
    async def _get_news_sentiment(self, ticker: str) -> Dict:
        """Get news sentiment analysis."""
        try:
            # Collect recent news (last 24 hours)
            articles = await self.news_collector.collect_stock_news(ticker, hours_lookback=24)
            
            # Calculate sentiment signal
            sentiment_signal = await self.news_collector.calculate_news_sentiment_signal(articles)
            
            return {
                **sentiment_signal,
                "articles": articles
            }
            
        except Exception as e:
            logger.warning(f"Error getting news sentiment: {str(e)}")
            return {"overall_sentiment": 0.0, "confidence": 0.0, "articles": []}
    
    async def _get_market_context(self) -> Dict:
        """Get overall market context and conditions."""
        try:
            # For now, return basic market context
            # In practice, this would analyze broader market indicators
            return {
                "market_trend": "neutral",
                "vix_level": "normal",
                "sector_performance": "mixed"
            }
            
        except Exception as e:
            logger.warning(f"Error getting market context: {str(e)}")
            return {"market_trend": "neutral"}
    
    async def _calculate_valuation_signal(self, analysis: Dict) -> float:
        """Calculate valuation signal (-1 to 1) based on fundamental metrics."""
        try:
            signal = 0.0
            factors = []
            
            # P/E Ratio Analysis
            pe_ratio = analysis.get("pe_ratio")
            if pe_ratio:
                if pe_ratio < 15:
                    signal += 0.3
                    factors.append("Low P/E ratio")
                elif pe_ratio > 30:
                    signal -= 0.3
                    factors.append("High P/E ratio")
            
            # PEG Ratio Analysis
            peg_ratio = analysis.get("peg_ratio")
            if peg_ratio:
                if peg_ratio < 1.0:
                    signal += 0.2
                    factors.append("Attractive PEG ratio")
                elif peg_ratio > 2.0:
                    signal -= 0.2
                    factors.append("High PEG ratio")
            
            # Price to Book Analysis
            price_to_book = analysis.get("price_to_book")
            if price_to_book:
                if price_to_book < 1.5:
                    signal += 0.1
                elif price_to_book > 5.0:
                    signal -= 0.1
            
            # Margin of Safety
            margin_of_safety = analysis.get("margin_of_safety")
            if margin_of_safety:
                if margin_of_safety > 20:
                    signal += 0.3
                    factors.append("High margin of safety")
                elif margin_of_safety < -20:
                    signal -= 0.3
                    factors.append("Trading above intrinsic value")
            
            # Quality Score
            quality_score = analysis.get("quality_score", 50)
            if quality_score > 75:
                signal += 0.1
                factors.append("High quality company")
            elif quality_score < 30:
                signal -= 0.1
                factors.append("Quality concerns")
            
            # Ensure signal is within bounds
            signal = max(-1.0, min(1.0, signal))
            
            return signal
            
        except Exception as e:
            logger.warning(f"Error calculating valuation signal: {str(e)}")
            return 0.0
    
    async def _calculate_technical_signal(self, analysis: Dict) -> float:
        """Calculate technical signal (-1 to 1) based on technical indicators."""
        try:
            signal = 0.0
            
            # Moving Average Analysis
            sma_50 = analysis.get("sma_50")
            sma_200 = analysis.get("sma_200")
            current_price = analysis.get("current_price")
            
            if all([sma_50, sma_200, current_price]):
                # Golden Cross / Death Cross
                if sma_50 > sma_200:
                    signal += 0.2
                else:
                    signal -= 0.2
                
                # Price vs Moving Averages
                if current_price > sma_50:
                    signal += 0.1
                else:
                    signal -= 0.1
            
            # RSI Analysis
            rsi = analysis.get("rsi_14")
            if rsi:
                if rsi < 30:
                    signal += 0.3  # Oversold
                elif rsi > 70:
                    signal -= 0.3  # Overbought
            
            # MACD Analysis
            macd_signal = analysis.get("macd_signal")
            if macd_signal == "bullish":
                signal += 0.2
            elif macd_signal == "bearish":
                signal -= 0.2
            
            # Bollinger Bands Position
            bollinger_position = analysis.get("bollinger_position")
            if bollinger_position is not None:
                if bollinger_position < -0.3:
                    signal += 0.1  # Near lower band (potential support)
                elif bollinger_position > 0.3:
                    signal -= 0.1  # Near upper band (potential resistance)
            
            # Volume Analysis
            volume_ratio = analysis.get("volume_ratio", 1.0)
            if volume_ratio > 1.5:
                signal += 0.1  # High volume confirms moves
            
            # Momentum Score
            momentum_score = analysis.get("momentum_score", 0)
            if momentum_score > 20:
                signal += 0.1
            elif momentum_score < -20:
                signal -= 0.1
            
            # Ensure signal is within bounds
            signal = max(-1.0, min(1.0, signal))
            
            return signal
            
        except Exception as e:
            logger.warning(f"Error calculating technical signal: {str(e)}")
            return 0.0
    
    async def _generate_llm_recommendation(
        self, ticker: str, stock_analysis: Dict, news_sentiment: Dict, 
        market_context: Dict, valuation_signal: float, technical_signal: float, 
        news_signal: float
    ) -> Dict:
        """Use LLM to generate final recommendation with reasoning."""
        try:
            # Prepare data summary for LLM
            data_summary = {
                "ticker": ticker,
                "current_price": stock_analysis.get("current_price"),
                "market_cap": stock_analysis.get("market_cap"),
                "pe_ratio": stock_analysis.get("pe_ratio"),
                "quality_score": stock_analysis.get("quality_score"),
                "margin_of_safety": stock_analysis.get("margin_of_safety"),
                "valuation_signal": valuation_signal,
                "technical_signal": technical_signal,
                "news_signal": news_signal,
                "news_article_count": news_sentiment.get("article_count", 0),
                "high_impact_news": news_sentiment.get("high_impact_count", 0)
            }
            
            prompt = f"""
            As an expert financial analyst, analyze the following stock data and provide a comprehensive investment recommendation.
            
            Stock: {ticker}
            Data: {json.dumps(data_summary, indent=2)}
            
            Consider:
            1. Valuation signal: {valuation_signal:.2f} (-1=overvalued, +1=undervalued)
            2. Technical signal: {technical_signal:.2f} (-1=bearish, +1=bullish)  
            3. News sentiment: {news_signal:.2f} (-1=negative, +1=positive)
            4. Recent news articles: {news_sentiment.get('article_count', 0)}
            
            Provide your analysis as valid JSON with:
            {{
                "action": "BUY|HOLD|SELL",
                "confidence": float (0-1),
                "reasoning": "1-2 sentence explanation",
                "key_factors": ["factor1", "factor2", "factor3"],
                "risk_level": "low|medium|high",
                "time_horizon": "short|medium|long"
            }}
            
            Guidelines:
            - BUY: Strong positive signals, good value, low risk
            - HOLD: Mixed signals, fair value, moderate risk  
            - SELL: Negative signals, overvalued, high risk
            - Confidence should reflect signal strength and consistency
            - Keep reasoning concise but insightful
            """
            
            response = await self.llm_model.generate_content_async(prompt)
            
            # Log Gemini API call
            try:
                db_log = SessionLocal()
                log_entry = GeminiApiCallLog(
                    timestamp=datetime.utcnow(),
                    purpose='llm_inference',
                    prompt=prompt
                )
                db_log.add(log_entry)
                db_log.commit()
                db_log.close()
            except Exception as e:
                logger.warning(f"Failed to log Gemini API call: {e}")
            
            # Parse LLM response
            try:
                recommendation = json.loads(response.text)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    recommendation = json.loads(json_match.group())
                else:
                    # Fallback recommendation
                    recommendation = {
                        "action": "HOLD",
                        "confidence": 0.5,
                        "reasoning": "Unable to parse LLM recommendation",
                        "key_factors": ["Analysis error"],
                        "risk_level": "medium",
                        "time_horizon": "medium"
                    }
            
            # Validate and sanitize recommendation
            recommendation["action"] = recommendation.get("action", "HOLD").upper()
            if recommendation["action"] not in ["BUY", "HOLD", "SELL"]:
                recommendation["action"] = "HOLD"
            
            recommendation["confidence"] = max(0.0, min(1.0, recommendation.get("confidence", 0.5)))
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error generating LLM recommendation: {str(e)}")
            return {
                "action": "HOLD",
                "confidence": 0.5,
                "reasoning": f"Error in analysis: {str(e)}",
                "key_factors": ["Analysis error"],
                "risk_level": "medium",
                "time_horizon": "medium"
            }
    
    async def _calculate_price_ranges(self, analysis: Dict, recommendation: Dict) -> Dict:
        """Calculate buy and sell price ranges based on analysis."""
        try:
            current_price = analysis.get("current_price")
            if not current_price:
                return {}
            
            action = recommendation.get("action", "HOLD")
            confidence = recommendation.get("confidence", 0.5)
            
            # Base ranges on volatility and confidence
            volatility_multiplier = 1.0 + (1.0 - confidence) * 0.2  # Higher uncertainty = wider ranges
            
            if action == "BUY":
                # Buy range: current price to 5-15% below (depending on confidence)
                buy_range_high = current_price * 1.02  # Slight premium allowed
                buy_range_low = current_price * (1.0 - 0.05 - (1.0 - confidence) * 0.10)
                
                # Sell range: 15-25% above current price
                sell_range_low = current_price * 1.15
                sell_range_high = current_price * (1.25 + confidence * 0.10)
                
            elif action == "SELL":
                # Sell range: current price to 5% above
                sell_range_low = current_price * 0.98
                sell_range_high = current_price * 1.05
                
                # Buy range: 15-30% below current price
                buy_range_high = current_price * 0.85
                buy_range_low = current_price * (0.70 - (1.0 - confidence) * 0.10)
                
            else:  # HOLD
                # Narrow ranges around current price
                buy_range_high = current_price * 0.95
                buy_range_low = current_price * 0.85
                sell_range_low = current_price * 1.05
                sell_range_high = current_price * 1.15
            
            return {
                "buy_range_low": round(buy_range_low, 2),
                "buy_range_high": round(buy_range_high, 2),
                "sell_range_low": round(sell_range_low, 2),
                "sell_range_high": round(sell_range_high, 2)
            }
            
        except Exception as e:
            logger.warning(f"Error calculating price ranges: {str(e)}")
            return {}
    
    async def _calculate_volatility_score(self, analysis: Dict) -> float:
        """Calculate volatility score based on technical indicators."""
        try:
            score = 0.5  # Base volatility
            
            # RSI-based volatility
            rsi = analysis.get("rsi_14")
            if rsi:
                if rsi > 70 or rsi < 30:
                    score += 0.2  # High RSI indicates more volatility
            
            # Bollinger Band position
            bollinger_position = analysis.get("bollinger_position")
            if bollinger_position is not None:
                score += abs(bollinger_position) * 0.3
            
            # Volume ratio
            volume_ratio = analysis.get("volume_ratio", 1.0)
            if volume_ratio > 2.0:
                score += 0.2  # High volume indicates volatility
            
            # Momentum score
            momentum_score = analysis.get("momentum_score", 0)
            score += abs(momentum_score) / 100 * 0.2
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.warning(f"Error calculating volatility score: {str(e)}")
            return 0.5 