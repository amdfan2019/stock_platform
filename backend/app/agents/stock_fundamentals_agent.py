"""
Stock Fundamentals Agent

Analyzes fundamental metrics for specific stocks, including valuation,
growth, profitability, and competitive position within market context.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from .base_stock_agent import BaseStockAgent
from ..database import SessionLocal
from ..models import StockFundamentalsAnalysis


class StockFundamentalsAgent(BaseStockAgent):
    """Agent specialized in analyzing stock fundamentals"""
    
    def __init__(self, ticker: str, agent_id: str = None):
        if not agent_id:
            agent_id = f"stock_fundamentals_{ticker.lower()}_001"
        
        specialized_prompt = f"""
You are a Long-Term Fundamentals Analyst specializing in {ticker}.

YOUR UNIQUE ROLE - TREND ANALYSIS:
You are NOT analyzing single-quarter snapshots. Your job is to identify LONG-TERM TRENDS:

1. REVENUE & EARNINGS TRENDS (Multi-Quarter/Year):
   - Is growth ACCELERATING, STABLE, or DECELERATING over the past 4-8 quarters?
   - Are margins EXPANDING or COMPRESSING over time?
   - Is the business becoming MORE or LESS profitable?
   - Example: "Revenue growth accelerated from 5% → 12% → 18% over last 3 quarters"

2. COMPETITIVE POSITION TRENDS:
   - Is market share GROWING or SHRINKING?
   - Are competitive advantages STRENGTHENING or WEAKENING?
   - Are new threats emerging or old threats diminishing?

3. VALUATION TRENDS:
   - How does current PE compare to its 1-year, 3-year, 5-year average?
   - Is the company trading at a premium or discount to its historical valuation?
   - Has the valuation multiple expanded or contracted over time?

4. QUALITY TRENDS:
   - Is return on equity improving or deteriorating?
   - Is debt increasing or decreasing relative to equity?
   - Is free cash flow generation improving?

You will receive quarterly historical data. Use it to identify TRENDS, not just current state.

IMPORTANT TEMPORAL CONTEXT:
- Latest reported quarter: Use 'latest_quarter_label' provided
- ONLY refer to quarters that have been reported (past data)
- DO NOT calculate growth rates (already provided) - ANALYZE the trend direction

Output Format (JSON):
{{
    "profit_margins": float (net margin percentage),
    "debt_to_equity": float,
    "return_on_equity": float,
    "free_cash_flow": float,
    "current_pe": float,
    "forward_pe": float,
    "historical_pe_avg": float,
    "pe_vs_industry": float,
    "pe_vs_market": float,
    "revenue_growth_trend": "Accelerating|Stable|Decelerating",
    "earnings_consistency": float (0-1),
    "guidance_outlook": "Positive|Neutral|Negative",
    "market_share_trend": "Gaining|Stable|Losing",
    "competitive_advantages": ["moat1", "moat2"],
    "competitive_threats": ["threat1", "threat2"],
    "interest_rate_sensitivity": "High|Medium|Low",
    "fundamental_strengths": ["strength1", "strength2"],
    "fundamental_concerns": ["concern1", "concern2"],
    "valuation_conclusion": "Undervalued|Fair Value|Overvalued",
    "confidence": float (0-1),
    "finding_type": "stock_fundamentals_analysis"
}}

Be specific about {ticker} and provide actionable fundamental insights.
"""
        
        super().__init__(agent_id, "stock_fundamentals", ticker, specialized_prompt)
        
    async def run_cycle(self):
        """Main cycle for stock fundamentals analysis"""
        try:
            logger.info(f"[{self.agent_id}] Starting fundamentals analysis for {self.ticker}")
            
            # Collect fundamentals data for this stock
            fundamentals_data = await self._collect_stock_fundamentals_data()
            
            if not fundamentals_data:
                logger.warning(f"[{self.agent_id}] Insufficient fundamentals data for {self.ticker}")
                return
            
            # Analyze fundamentals with full context
            fundamentals_analysis = await self.analyze_with_full_context(
                fundamentals_data,
                f"Analyze {self.ticker}'s fundamental metrics and financial health. "
                f"Compare valuation to historical levels, industry peers, and market averages. "
                f"Assess growth prospects and competitive position within current economic context."
            )
            
            # Store fundamentals analysis
            await self._store_fundamentals_analysis(fundamentals_data, fundamentals_analysis)
            
            logger.info(f"[{self.agent_id}] Fundamentals analysis completed for {self.ticker}: {fundamentals_analysis.get('valuation_conclusion', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] Error in fundamentals analysis cycle: {e}")
    
    async def _collect_stock_fundamentals_data(self) -> Dict:
        """Collect fundamentals-related data for this stock INCLUDING quarterly history for trend analysis"""
        try:
            # Get stock fundamentals from yfinance
            fundamentals = await self.get_stock_fundamentals()
            
            # Get quarterly historical data for TREND ANALYSIS
            quarterly_history = await self._get_quarterly_trends()
            
            # Get recent stock-specific memory for context
            stock_memory = await self.memory.get_stock_short_term_memory(30)
            
            # Get market fundamentals context for comparison
            market_fundamentals_context = await self.request_market_context('fundamentals')
            
            # Get recent price data for valuation context
            price_data = await self.memory.get_stock_price_history(90)
            
            # Calculate derived metrics
            current_price = price_data.get('current_price') if price_data else None
            market_cap = fundamentals.get('market_cap')
            
            # Calculate some basic derived metrics
            derived_metrics = {}
            
            if fundamentals.get('pe_ratio') and fundamentals.get('earnings_growth'):
                # PEG ratio calculation
                derived_metrics['calculated_peg'] = fundamentals['pe_ratio'] / max(fundamentals['earnings_growth'] * 100, 1)
            
            # Historical valuation context (simplified)
            pe_current = fundamentals.get('pe_ratio', 20)
            pe_historical_avg = pe_current * 0.9  # Simplified historical average
            
            # Industry comparison (simplified for demonstration)
            sector = fundamentals.get('sector', 'Technology')
            industry_pe_avg = {
                'Technology': 25,
                'Healthcare': 22,
                'Financial Services': 15,
                'Consumer Cyclical': 18,
                'Industrial': 20
            }.get(sector, 20)
            
            fundamentals_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'ticker': self.ticker,
                'sector': sector,
                'industry': fundamentals.get('industry', 'Unknown'),
                
                # Current fundamentals
                'current_fundamentals': fundamentals,
                'derived_metrics': derived_metrics,
                
                # QUARTERLY TRENDS FOR LONG-TERM ANALYSIS
                'quarterly_trends': quarterly_history,
                
                # Valuation context
                'current_price': current_price,
                'pe_current': pe_current,
                'pe_historical_avg': pe_historical_avg,
                'industry_pe_avg': industry_pe_avg,
                'market_pe_avg': 20,  # Simplified market average
                
                # Growth context
                'price_performance_90d': price_data.get('price_change_pct', 0) if price_data else 0,
                'volatility_90d': price_data.get('volatility', 20) if price_data else 20,
                
                # Economic context
                'market_fundamentals_context': market_fundamentals_context,
                'economic_cycle': market_fundamentals_context.get('economic_cycle_stage', 'mid_cycle'),
                'interest_rate_environment': market_fundamentals_context.get('interest_rate_environment', 'neutral'),
                
                # Historical context
                'recent_fundamentals_history': stock_memory.get('recent_analysis', []),
                
                # Meta information
                'data_sources': ['yfinance', 'market_context', 'historical_analysis', 'quarterly_trends'],
                'data_quality': 'high' if fundamentals.get('pe_ratio') else 'medium'
            }
            
            return fundamentals_data
            
        except Exception as e:
            logger.error(f"Error collecting fundamentals data for {self.ticker}: {e}")
            return {}
    
    async def _get_quarterly_trends(self) -> Dict:
        """Get quarterly historical data for trend analysis"""
        try:
            import yfinance as yf
            stock = yf.Ticker(self.ticker)
            
            # Get quarterly income statement (last 8 quarters if available)
            quarterly_income = stock.quarterly_income_stmt
            
            if quarterly_income is None or quarterly_income.empty:
                logger.warning(f"[{self.ticker}] No quarterly income data available")
                return {}
            
            # Get quarterly financials (balance sheet)
            quarterly_balance = stock.quarterly_balance_sheet
            
            # Extract key metrics over time
            quarters = []
            for col in quarterly_income.columns[:8]:  # Last 8 quarters
                quarter_data = {
                    'quarter_end': col.strftime('%Y-%m-%d'),
                    'total_revenue': float(quarterly_income.loc['Total Revenue', col]) if 'Total Revenue' in quarterly_income.index else None,
                    'gross_profit': float(quarterly_income.loc['Gross Profit', col]) if 'Gross Profit' in quarterly_income.index else None,
                    'operating_income': float(quarterly_income.loc['Operating Income', col]) if 'Operating Income' in quarterly_income.index else None,
                    'net_income': float(quarterly_income.loc['Net Income', col]) if 'Net Income' in quarterly_income.index else None,
                }
                
                # Calculate margins if data available
                if quarter_data['total_revenue'] and quarter_data['net_income']:
                    quarter_data['net_margin'] = (quarter_data['net_income'] / quarter_data['total_revenue']) * 100
                if quarter_data['total_revenue'] and quarter_data['gross_profit']:
                    quarter_data['gross_margin'] = (quarter_data['gross_profit'] / quarter_data['total_revenue']) * 100
                
                quarters.append(quarter_data)
            
            # Calculate YoY growth rates
            if len(quarters) >= 5:
                for i in range(len(quarters) - 4):
                    if quarters[i]['total_revenue'] and quarters[i + 4]['total_revenue']:
                        quarters[i]['revenue_yoy_growth'] = ((quarters[i]['total_revenue'] - quarters[i + 4]['total_revenue']) / quarters[i + 4]['total_revenue']) * 100
                    if quarters[i]['net_income'] and quarters[i + 4]['net_income'] and quarters[i + 4]['net_income'] != 0:
                        quarters[i]['earnings_yoy_growth'] = ((quarters[i]['net_income'] - quarters[i + 4]['net_income']) / abs(quarters[i + 4]['net_income'])) * 100
            
            trend_summary = {
                'quarters': quarters,
                'num_quarters': len(quarters),
                'data_source': 'yfinance_quarterly_income_stmt'
            }
            
            logger.info(f"[{self.ticker}] Retrieved {len(quarters)} quarters of historical data for trend analysis")
            return trend_summary
            
        except Exception as e:
            logger.error(f"[{self.ticker}] Error getting quarterly trends: {e}")
            return {}
    
    async def _store_fundamentals_analysis(self, fundamentals_data: Dict, analysis: Dict):
        """Store fundamentals analysis in database"""
        try:
            db = SessionLocal()
            
            fundamentals = fundamentals_data.get('current_fundamentals', {})
            
            # DEBUG: Log what values we're actually storing
            logger.info(f"[{self.ticker}] STORING: revenue_growth={fundamentals.get('revenue_growth')}, earnings_growth={fundamentals.get('earnings_growth')}")
            logger.info(f"[{self.ticker}] LLM returned: revenue_growth={analysis.get('revenue_growth')}, earnings_growth={analysis.get('earnings_growth')}")
            
            fundamentals_analysis = StockFundamentalsAnalysis(
                ticker=self.ticker,
                analysis_date=datetime.utcnow(),
                
                # Financial Health
                revenue_growth=fundamentals.get('revenue_growth'),  # ALWAYS use our calculation, not LLM's
                earnings_growth=fundamentals.get('earnings_growth'),  # ALWAYS use our calculation, not LLM's (handles loss-to-profit correctly)
                profit_margins=analysis.get('profit_margins', fundamentals.get('profit_margins')),
                debt_to_equity=analysis.get('debt_to_equity', fundamentals.get('debt_to_equity')),
                return_on_equity=analysis.get('return_on_equity', fundamentals.get('return_on_equity')),
                free_cash_flow=fundamentals.get('free_cash_flow'),  # Total FCF from yfinance
                
                # Quarter Information
                latest_quarter_date=fundamentals.get('latest_quarter_date'),
                latest_quarter_label=fundamentals.get('latest_quarter_label'),
                latest_eps=fundamentals.get('latest_eps'),
                
                # Valuation Metrics
                current_pe=analysis.get('current_pe', fundamentals.get('pe_ratio')),
                forward_pe=analysis.get('forward_pe', fundamentals.get('forward_pe')),
                historical_pe_avg=analysis.get('historical_pe_avg', fundamentals_data.get('pe_historical_avg')),
                pe_vs_industry=analysis.get('pe_vs_industry'),
                pe_vs_market=analysis.get('pe_vs_market'),
                
                # Growth Analysis
                revenue_growth_trend=analysis.get('revenue_growth_trend', 'Stable'),
                earnings_consistency=analysis.get('earnings_consistency', 0.7),
                guidance_outlook=analysis.get('guidance_outlook', 'Neutral'),
                
                # Competitive Position
                market_share_trend=analysis.get('market_share_trend', 'Stable'),
                competitive_advantages=analysis.get('competitive_advantages', []),
                competitive_threats=analysis.get('competitive_threats', []),
                
                # Economic Context
                economic_impact_assessment=f"Analysis considering {fundamentals_data.get('economic_cycle')} economic environment",
                sector_fundamentals_context=fundamentals_data.get('market_fundamentals_context', {}),
                interest_rate_sensitivity=analysis.get('interest_rate_sensitivity', 'Medium'),
                
                # Key Insights
                fundamental_strengths=analysis.get('fundamental_strengths', []),
                fundamental_concerns=analysis.get('fundamental_concerns', []),
                valuation_conclusion=analysis.get('valuation_conclusion', 'Fair Value'),
                
                # Agent Metadata
                agent_id=self.agent_id,
                market_fundamentals_context=fundamentals_data.get('market_fundamentals_context', {}),
                data_quality_score=1.0 if fundamentals_data.get('data_quality') == 'high' else 0.8
            )
            
            db.add(fundamentals_analysis)
            db.commit()
            
            logger.info(f"[{self.agent_id}] Stored fundamentals analysis for {self.ticker}")
            
        except Exception as e:
            logger.error(f"Error storing fundamentals analysis: {e}")
        finally:
            db.close()
    
    async def get_latest_fundamentals_analysis(self) -> Dict:
        """Get latest fundamentals analysis for this stock"""
        try:
            db = SessionLocal()
            
            latest_fundamentals = db.query(StockFundamentalsAnalysis).filter(
                StockFundamentalsAnalysis.ticker == self.ticker
            ).order_by(StockFundamentalsAnalysis.analysis_date.desc()).first()
            
            if not latest_fundamentals:
                return {'error': f'No fundamentals analysis available for {self.ticker}'}
            
            return {
                'ticker': self.ticker,
                'analysis_date': latest_fundamentals.analysis_date.isoformat(),
                'revenue_growth': latest_fundamentals.revenue_growth,
                'earnings_growth': latest_fundamentals.earnings_growth,
                'valuation_conclusion': latest_fundamentals.valuation_conclusion,
                'current_pe': latest_fundamentals.current_pe,
                'pe_vs_industry': latest_fundamentals.pe_vs_industry,
                'competitive_advantages': latest_fundamentals.competitive_advantages,
                'competitive_threats': latest_fundamentals.competitive_threats,
                'fundamental_strengths': latest_fundamentals.fundamental_strengths,
                'fundamental_concerns': latest_fundamentals.fundamental_concerns,
                'interest_rate_sensitivity': latest_fundamentals.interest_rate_sensitivity
            }
            
        except Exception as e:
            logger.error(f"Error getting latest fundamentals analysis: {e}")
            return {'error': str(e)}
        finally:
            db.close() 