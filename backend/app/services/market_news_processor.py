import asyncio
import aiohttp
import feedparser
from bs4 import BeautifulSoup
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import re
from urllib.parse import quote_plus, urljoin
import google.generativeai as genai
from ..config import settings
from loguru import logger
import hashlib
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from ..database import SessionLocal
from ..models import MarketArticle


class MarketNewsProcessor:
    """
    Advanced market news processing engine for general financial news.
    Collects, summarizes, deduplicates, and ranks news by market relevance.
    """
    
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=settings.google_api_key)
        self.llm_model = genai.GenerativeModel(settings.llm_model)
        
        # General financial news sources (not stock-specific)
        self.news_sources = {
            "reuters_markets": "https://feeds.reuters.com/reuters/businessNews",
            "bloomberg_rss": "https://feeds.bloomberg.com/markets/news.rss",
            "cnbc_markets": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
            "marketwatch_rss": "https://feeds.marketwatch.com/marketwatch/marketpulse/",
            "ft_markets": "https://www.ft.com/markets?format=rss",
            "wsj_markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "yahoo_finance": "https://feeds.finance.yahoo.com/rss/2.0/headline",
            "google_finance": "https://news.google.com/rss/search?q=stock market finance&hl=en-US&gl=US&ceid=US:en"
        }
        
        # Keywords for market relevance scoring
        self.high_impact_keywords = [
            "federal reserve", "fed", "interest rates", "inflation", "gdp", "unemployment",
            "earnings", "recession", "market crash", "bull market", "bear market",
            "s&p 500", "dow jones", "nasdaq", "volatility", "central bank", "economic data",
            "trade war", "geopolitical", "oil prices", "gold", "crypto", "bitcoin"
        ]
        
        self.market_keywords = [
            "stock market", "stocks", "shares", "trading", "investment", "portfolio",
            "analyst", "upgrade", "downgrade", "price target", "dividend", "buyback",
            "merger", "acquisition", "ipo", "financial results", "guidance", "outlook"
        ]
        
        # Source credibility weights for relevance scoring
        self.source_weights = {
            "Reuters": 1.0,
            "Bloomberg": 1.0,
            "Wall Street Journal": 0.95,
            "Financial Times": 0.95,
            "CNBC": 0.85,
            "MarketWatch": 0.8,
            "Yahoo Finance": 0.75,
            "Google News": 0.7
        }
    
    async def collect_market_news(self, hours_lookback: int = 12, max_articles: int = 50) -> List[Dict]:
        """
        Collect general market news from multiple sources with intelligent database caching.
        Only processes new articles through LLM, reuses cached processed articles.
        
        Args:
            hours_lookback: How many hours back to collect news
            max_articles: Maximum number of articles to return
            
        Returns:
            List of processed news articles ranked by relevance
        """
        try:
            logger.info(f"Collecting market news for the last {hours_lookback} hours")
            cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
            
            # Step 1: Get already processed articles from database
            db = SessionLocal()
            try:
                existing_articles = db.query(MarketArticle).filter(
                    MarketArticle.published_at >= cutoff_time
                ).order_by(desc(MarketArticle.relevance_score)).all()
                
                logger.info(f"Found {len(existing_articles)} already processed articles in database")
                
                # Convert to our standard format
                cached_articles = []
                for article in existing_articles:
                    cached_articles.append({
                        "title": article.title,
                        "implication_title": article.implication_title,
                        "url": article.url,
                        "source": article.source,
                        "published_at": article.published_at,
                        "ai_summary": article.ai_summary,
                        "market_impact": article.market_impact,
                        "sentiment": article.sentiment,
                        "mentioned_tickers": article.mentioned_tickers or [],
                        "affected_sectors": article.affected_sectors or [],
                        "relevance_score": article.relevance_score
                    })
                
            finally:
                db.close()
            
            # Step 2: Collect fresh articles from RSS feeds
            collection_tasks = [
                self._collect_reuters_markets(),
                self._collect_cnbc_markets(),
                self._collect_marketwatch_rss(),
                self._collect_yahoo_finance(),
                self._collect_google_finance_news(),
                self._collect_wsj_markets()
            ]
            
            collection_results = await asyncio.gather(*collection_tasks, return_exceptions=True)
            
            # Combine all fresh articles
            fresh_articles = []
            for result in collection_results:
                if isinstance(result, list):
                    fresh_articles.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"News collection error: {str(result)}")
            
            # Filter fresh articles by time window
            recent_fresh_articles = [
                article for article in fresh_articles 
                if article.get("published_at", datetime.min) > cutoff_time
            ]
            
            logger.info(f"Collected {len(recent_fresh_articles)} fresh articles from RSS feeds")
            
            # Step 3: Identify truly NEW articles (not in database)
            cached_urls = {article["url"] for article in cached_articles}
            new_articles = [
                article for article in recent_fresh_articles 
                if article["url"] not in cached_urls
            ]
            
            logger.info(f"Found {len(new_articles)} new articles not yet processed")
            
            # Step 4: Only process NEW articles through LLM
            newly_processed_articles = []
            if new_articles:
                # Deduplicate new articles
                unique_new_articles = await self._deduplicate_articles(new_articles)
                logger.info(f"After deduplication: {len(unique_new_articles)} unique new articles")
                
                # Process new articles through LLM
                for article in unique_new_articles:
                    try:
                        enhanced = await self._enhance_article_with_llm(article)
                        if enhanced:
                            # Calculate relevance score for the enhanced article
                            enhanced["relevance_score"] = await self._calculate_relevance_score(enhanced)
                            newly_processed_articles.append(enhanced)
                            
                            # Store in database with relevance score
                            await self._store_processed_article(enhanced)
                            
                    except Exception as e:
                        logger.warning(f"Error enhancing article: {str(e)}")
                        # Include original article if enhancement fails with basic relevance score
                        article["relevance_score"] = await self._calculate_relevance_score(article)
                        newly_processed_articles.append(article)
            
            # Step 5: Combine cached + newly processed articles
            all_processed_articles = cached_articles + newly_processed_articles
            
            # Step 6: Sort by relevance and return top articles
            # Re-rank all articles together (cached scores + new scores)
            ranked_articles = sorted(
                all_processed_articles, 
                key=lambda x: x.get("relevance_score", 0), 
                reverse=True
            )
            
            # Return top articles
            top_articles = ranked_articles[:max_articles]
            logger.info(f"Returning top {len(top_articles)} articles ({len(cached_articles)} cached + {len(newly_processed_articles)} newly processed)")
            
            return top_articles
            
        except Exception as e:
            logger.error(f"Error collecting market news: {str(e)}")
            return []
    
    async def _store_processed_article(self, article: Dict) -> None:
        """Store a processed article in the database."""
        try:
            db = SessionLocal()
            try:
                # Create content hash for deduplication
                content_for_hash = f"{article['title']}{article.get('ai_summary', '')}"
                content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
                
                # Check if article already exists (by URL)
                existing = db.query(MarketArticle).filter(
                    MarketArticle.url == article["url"]
                ).first()
                
                if not existing:
                    db_article = MarketArticle(
                        url=article["url"],
                        title=article["title"],
                        source=article["source"],
                        published_at=article["published_at"],
                        implication_title=article.get("implication_title", article["title"]),
                        ai_summary=article.get("ai_summary", ""),
                        market_impact=article.get("market_impact", "Medium"),
                        sentiment=article.get("sentiment", "neutral"),
                        mentioned_tickers=article.get("mentioned_tickers", []),
                        affected_sectors=article.get("affected_sectors", []),
                        relevance_score=article.get("relevance_score", 0.0),
                        content_hash=content_hash,
                        processing_version="1.0"
                    )
                    
                    db.add(db_article)
                    db.commit()
                    logger.debug(f"Stored article in database: {article['title'][:50]}...")
                else:
                    logger.debug(f"Article already exists in database: {article['title'][:50]}...")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(f"Error storing article in database: {str(e)}")
    
    async def _collect_reuters_markets(self) -> List[Dict]:
        """Collect Reuters business/markets news."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                async with session.get(self.news_sources["reuters_markets"], headers=headers) as response:
                    rss_content = await response.text()
            
            feed = feedparser.parse(rss_content)
            articles = []
            
            for entry in feed.entries[:20]:
                try:
                    published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                    
                    articles.append({
                        "title": entry.title,
                        "url": entry.link,
                        "source": "Reuters",
                        "published_at": published.replace(tzinfo=None),
                        "summary": entry.get("summary", "")[:500],
                        "raw_content": entry.get("summary", "")
                    })
                except Exception as e:
                    logger.warning(f"Error parsing Reuters entry: {str(e)}")
                    continue
            
            logger.info(f"Collected {len(articles)} articles from Reuters")
            return articles
            
        except Exception as e:
            logger.warning(f"Error collecting Reuters news: {str(e)}")
            return []
    
    async def _collect_cnbc_markets(self) -> List[Dict]:
        """Collect CNBC markets news."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                async with session.get(self.news_sources["cnbc_markets"], headers=headers) as response:
                    rss_content = await response.text()
            
            feed = feedparser.parse(rss_content)
            articles = []
            
            for entry in feed.entries[:20]:
                try:
                    # CNBC uses different date formats
                    published = None
                    for date_format in [
                        "%a, %d %b %Y %H:%M:%S %Z",  # GMT format
                        "%a, %d %b %Y %H:%M:%S %z",  # Timezone format
                        "%a, %d %b %Y %H:%M:%S"      # No timezone
                    ]:
                        try:
                            published = datetime.strptime(entry.published, date_format)
                            if published.tzinfo:
                                published = published.replace(tzinfo=None)
                            break
                        except:
                            continue
                    
                    if not published:
                        published = datetime.now()
                    
                    articles.append({
                        "title": entry.title,
                        "url": entry.link,
                        "source": "CNBC",
                        "published_at": published.replace(tzinfo=None) if published.tzinfo else published,
                        "summary": entry.get("summary", "")[:500],
                        "raw_content": entry.get("summary", "")
                    })
                except Exception as e:
                    logger.warning(f"Error parsing CNBC entry: {str(e)}")
                    continue
            
            logger.info(f"Collected {len(articles)} articles from CNBC")
            return articles
            
        except Exception as e:
            logger.warning(f"Error collecting CNBC news: {str(e)}")
            return []
    
    async def _collect_marketwatch_rss(self) -> List[Dict]:
        """Collect MarketWatch news."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                async with session.get(self.news_sources["marketwatch_rss"], headers=headers) as response:
                    rss_content = await response.text()
            
            feed = feedparser.parse(rss_content)
            articles = []
            
            for entry in feed.entries[:20]:
                try:
                    # Handle multiple date formats
                    published = None
                    for date_format in [
                        "%a, %d %b %Y %H:%M:%S %z",  # With timezone
                        "%a, %d %b %Y %H:%M:%S %Z",  # With GMT
                        "%a, %d %b %Y %H:%M:%S"      # Without timezone
                    ]:
                        try:
                            published = datetime.strptime(entry.published, date_format)
                            if published.tzinfo:
                                published = published.replace(tzinfo=None)
                            break
                        except:
                            continue
                    
                    if not published:
                        # If parsing fails, use current time
                        published = datetime.now()
                    
                    articles.append({
                        "title": entry.title,
                        "url": entry.link,
                        "source": "MarketWatch",
                        "published_at": published,
                        "summary": entry.get("summary", "")[:500],
                        "raw_content": entry.get("summary", "")
                    })
                except Exception as e:
                    logger.warning(f"Error parsing MarketWatch entry: {str(e)}")
                    continue
            
            logger.info(f"Collected {len(articles)} articles from MarketWatch")
            return articles
            
        except Exception as e:
            logger.warning(f"Error collecting MarketWatch news: {str(e)}")
            return []
    
    async def _collect_yahoo_finance(self) -> List[Dict]:
        """Collect Yahoo Finance news."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                async with session.get(self.news_sources["yahoo_finance"], headers=headers) as response:
                    rss_content = await response.text()
            
            feed = feedparser.parse(rss_content)
            articles = []
            
            for entry in feed.entries[:20]:
                try:
                    published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                    
                    articles.append({
                        "title": entry.title,
                        "url": entry.link,
                        "source": "Yahoo Finance",
                        "published_at": published.replace(tzinfo=None),
                        "summary": entry.get("summary", "")[:500],
                        "raw_content": entry.get("summary", "")
                    })
                except Exception as e:
                    logger.warning(f"Error parsing Yahoo Finance entry: {str(e)}")
                    continue
            
            logger.info(f"Collected {len(articles)} articles from Yahoo Finance")
            return articles
            
        except Exception as e:
            logger.warning(f"Error collecting Yahoo Finance news: {str(e)}")
            return []
    
    async def _collect_google_finance_news(self) -> List[Dict]:
        """Collect Google Finance news."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                async with session.get(self.news_sources["google_finance"], headers=headers) as response:
                    rss_content = await response.text()
            
            feed = feedparser.parse(rss_content)
            articles = []
            
            for entry in feed.entries[:15]:
                try:
                    # Google News uses different date formats
                    published = None
                    for date_format in [
                        "%a, %d %b %Y %H:%M:%S %Z",  # GMT format
                        "%a, %d %b %Y %H:%M:%S %z",  # Timezone format
                        "%a, %d %b %Y %H:%M:%S"      # No timezone
                    ]:
                        try:
                            published = datetime.strptime(entry.published, date_format)
                            if published.tzinfo:
                                published = published.replace(tzinfo=None)
                            break
                        except:
                            continue
                    
                    if not published:
                        published = datetime.now()
                    
                    # Clean title (Google often includes source in title)
                    title = entry.title
                    if " - " in title:
                        title = title.split(" - ")[0].strip()
                    
                    # Clean and extract meaningful content
                    summary_html = entry.get("summary", "")
                    raw_content = self._clean_html_content(summary_html)
                    
                    # If we have very little content, try to extract from description or use title
                    if len(raw_content) < 50:
                        description = entry.get("description", "")
                        raw_content = self._clean_html_content(description) or title
                    
                    articles.append({
                        "title": title,
                        "url": entry.link,
                        "source": "Google News",
                        "published_at": published,
                        "summary": raw_content[:500] if raw_content else title,
                        "raw_content": raw_content or title
                    })
                except Exception as e:
                    logger.warning(f"Error parsing Google Finance entry: {str(e)}")
                    continue
            
            logger.info(f"Collected {len(articles)} articles from Google Finance")
            return articles
            
        except Exception as e:
            logger.warning(f"Error collecting Google Finance news: {str(e)}")
            return []
    
    async def _collect_wsj_markets(self) -> List[Dict]:
        """Collect Wall Street Journal markets news."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                async with session.get(self.news_sources["wsj_markets"], headers=headers) as response:
                    rss_content = await response.text()
            
            feed = feedparser.parse(rss_content)
            articles = []
            
            for entry in feed.entries[:15]:
                try:
                    published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                    
                    articles.append({
                        "title": entry.title,
                        "url": entry.link,
                        "source": "Wall Street Journal",
                        "published_at": published.replace(tzinfo=None),
                        "summary": entry.get("summary", "")[:500],
                        "raw_content": entry.get("summary", "")
                    })
                except Exception as e:
                    logger.warning(f"Error parsing WSJ entry: {str(e)}")
                    continue
            
            logger.info(f"Collected {len(articles)} articles from WSJ")
            return articles
            
        except Exception as e:
            logger.warning(f"Error collecting WSJ news: {str(e)}")
            return []
    
    async def _deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicate articles based on title similarity."""
        if not articles:
            return []
        
        unique_articles = []
        seen_hashes = set()
        
        for article in articles:
            # Create hash based on normalized title
            title_normalized = re.sub(r'[^\w\s]', '', article["title"].lower())
            title_hash = hashlib.md5(title_normalized.encode()).hexdigest()
            
            if title_hash not in seen_hashes:
                seen_hashes.add(title_hash)
                unique_articles.append(article)
        
        logger.info(f"Deduplication: {len(articles)} -> {len(unique_articles)} articles")
        return unique_articles
    
    async def _enhance_article_with_llm(self, article: Dict) -> Optional[Dict]:
        """Enhance article with LLM-generated summary and market impact analysis."""
        try:
            # Create a more informative prompt that extracts key facts
            content = article.get('raw_content', article.get('summary', ''))[:1000]  # Use more content
            
            # Create enhanced prompt that works with limited content
            prompt = f"""
            You are a financial news analyst. Analyze this news and create investor-focused insights.

            Original Title: {article['title']}
            Content: {content if content and len(content) > 20 else "Limited content - analyze based on headline"}
            
            Provide a JSON response with:

            1. "implication_title": Create a SHORT, actionable title that tells investors what this means (40-60 characters max)
               Examples: 
               - "Markets rally on strong earnings outlook"
               - "Fed rate hike pressures growth stocks"
               - "Tech sector shows resilience amid volatility"
               - "Banking stocks benefit from rising rates"
            
            2. "summary": 2-3 sentence factual explanation of what happened and its market implications (250-350 characters)
               - ALWAYS include specific stock tickers (e.g., AAPL, MSFT) in the summary when they are mentioned in the article
               - Use ticker symbols rather than full company names in summaries for brevity
            
            3. "market_impact": 
               - "High": Market-moving (Fed decisions, major economic data, broad market events)
               - "Medium": Sector-relevant (company earnings, industry news)
               - "Low": Informational (commentary, minor updates)
            
            4. "sentiment": Overall market sentiment from this news:
               - "bullish": Positive for markets/stocks
               - "bearish": Negative for markets/stocks  
               - "neutral": Mixed or unclear impact
            
            5. "mentioned_tickers": Any stock symbols mentioned (extract ALL tickers mentioned, including both obvious and subtle references)
            
            6. "affected_sectors": Relevant sectors

            CRITICAL REQUIREMENTS:
            - ALWAYS include stock tickers in the summary when they're mentioned in the article
            - Focus ONLY on stating facts and explaining what happened
            - Never include advisory language like "Investors should monitor...", "Watch for...", etc.
            - Simply explain WHAT happened and WHY it matters to markets, without telling anyone what to do

            Respond with valid JSON only:
            {{
                "implication_title": "Short actionable title here",
                "summary": "Investment analysis here...",
                "market_impact": "High",
                "sentiment": "bullish",
                "mentioned_tickers": ["TICK1"],
                "affected_sectors": ["Sector1"]
            }}
            """
            
            response = await self.llm_model.generate_content_async(prompt)
            
            # Parse LLM response with robust JSON extraction
            try:
                response_text = response.text.strip()
                logger.info(f"LLM response for '{article['title'][:50]}...': {response_text[:200]}...")
                
                # Try to extract JSON from response (sometimes LLM adds extra text)
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    llm_analysis = json.loads(json_str)
                else:
                    raise json.JSONDecodeError("No JSON found", response_text, 0)
                
                # Enhance the original article
                enhanced_article = article.copy()
                enhanced_article.update({
                    "implication_title": llm_analysis.get("implication_title", article["title"])[:60],
                    "ai_summary": llm_analysis.get("summary", article.get("summary", article["title"]))[:400],
                    "market_impact": llm_analysis.get("market_impact", "Medium"),
                    "sentiment": llm_analysis.get("sentiment", "neutral"),
                    "mentioned_tickers": llm_analysis.get("mentioned_tickers", []),
                    "affected_sectors": llm_analysis.get("affected_sectors", [])
                })
                
                logger.info(f"Successfully enhanced article: {article['title'][:50]}...")
                return enhanced_article
                
            except (json.JSONDecodeError, Exception) as e:
                # If JSON parsing fails, create a basic intelligent summary from the title
                logger.warning(f"Failed to parse LLM response for '{article['title']}': {str(e)}")
                
                # Create intelligent fallback based on title keywords
                title_lower = article['title'].lower()
                fallback_summary = self._create_fallback_summary(article['title'])
                fallback_title = self._create_fallback_implication_title(article['title'])
                
                # Determine market impact from title keywords
                market_impact = "Medium"
                if any(word in title_lower for word in ["fed", "federal reserve", "rates", "inflation", "gdp", "unemployment"]):
                    market_impact = "High"
                elif any(word in title_lower for word in ["earnings", "beats", "misses", "guidance"]):
                    market_impact = "Medium"
                elif any(word in title_lower for word in ["analyst", "upgrade", "target"]):
                    market_impact = "Low"
                
                # Determine sentiment from title keywords
                sentiment = "neutral"
                if any(word in title_lower for word in ["rise", "up", "gains", "rally", "surge", "beats", "strong"]):
                    sentiment = "bullish"
                elif any(word in title_lower for word in ["fall", "down", "decline", "drop", "crash", "weak", "miss"]):
                    sentiment = "bearish"
                
                enhanced_article = article.copy()
                enhanced_article.update({
                    "implication_title": fallback_title,
                    "ai_summary": fallback_summary,
                    "market_impact": market_impact,
                    "sentiment": sentiment,
                    "mentioned_tickers": self._extract_tickers_from_title(article['title']),
                    "affected_sectors": []
                })
                return enhanced_article
            
        except Exception as e:
            logger.warning(f"Error enhancing article with LLM: {str(e)}")
            return article
    
    async def _rank_articles_by_relevance(self, articles: List[Dict]) -> List[Dict]:
        """Rank articles by market impact first, then relevance score."""
        scored_articles = []
        
        for article in articles:
            score = await self._calculate_relevance_score(article)
            article["relevance_score"] = score
            scored_articles.append(article)
        
        # Define market impact priority
        impact_priority = {"High": 3, "Medium": 2, "Low": 1}
        
        # Sort by market impact first (High->Medium->Low), then by relevance score (descending)
        ranked_articles = sorted(
            scored_articles, 
            key=lambda x: (
                impact_priority.get(x.get("market_impact", "Medium"), 2),  # Market impact priority
                x["relevance_score"]  # Relevance score as secondary sort
            ), 
            reverse=True
        )
        
        logger.info(f"Ranked {len(ranked_articles)} articles by market impact and relevance")
        return ranked_articles
    
    async def _calculate_relevance_score(self, article: Dict) -> float:
        """
        Calculate relevance score based on multiple factors.
        Total possible score: ~100 points for maximum relevance.
        """
        score = 0.0
        
        # Factor 1: Source credibility (10-20 points based on source quality)
        source_weight = self.source_weights.get(article["source"], 0.5)
        score += source_weight * 20  # Max 20 points for top sources
        
        # Factor 2: Freshness (5-25 points - less harsh penalty)
        published_at = article.get("published_at")
        if published_at:
            hours_old = (datetime.now() - published_at).total_seconds() / 3600
            if hours_old <= 2:
                freshness_score = 25  # Very fresh
            elif hours_old <= 6:
                freshness_score = 20  # Fresh
            elif hours_old <= 12:
                freshness_score = 15  # Recent
            elif hours_old <= 24:
                freshness_score = 10  # Today
            else:
                freshness_score = 5   # Older
            score += freshness_score
        else:
            score += 10  # Default if no timestamp
        
        # Factor 3: Enhanced keyword relevance (0-25 points)
        title_lower = article["title"].lower()
        content_lower = article.get("raw_content", "").lower()
        combined_text = f"{title_lower} {content_lower}"
        
        keyword_score = 0
        
        # High impact keywords (3 points each in title, 1.5 in content)
        for keyword in self.high_impact_keywords:
            if keyword in title_lower:
                keyword_score += 3
            elif keyword in content_lower:
                keyword_score += 1.5
        
        # General market keywords (1.5 points each in title, 0.75 in content)
        for keyword in self.market_keywords:
            if keyword in title_lower:
                keyword_score += 1.5
            elif keyword in content_lower:
                keyword_score += 0.75
        
        # Additional financial terms for broader relevance
        financial_terms = [
            "earnings", "revenue", "profit", "loss", "quarter", "guidance", 
            "forecast", "estimate", "beat", "miss", "growth", "decline",
            "investment", "fund", "etf", "ipo", "merger", "acquisition"
        ]
        
        for term in financial_terms:
            if term in combined_text:
                keyword_score += 0.5
        
        score += min(keyword_score, 25)  # Cap at 25 points
        
        # Factor 4: Market impact assessment (5-20 points)
        market_impact = article.get("market_impact", "Medium")
        impact_scores = {"High": 20, "Medium": 12, "Low": 7}
        score += impact_scores.get(market_impact, 12)
        
        # Factor 5: Mentioned tickers boost (0-10 points)
        mentioned_tickers = article.get("mentioned_tickers", [])
        ticker_score = len(mentioned_tickers) * 1.5
        score += min(ticker_score, 10)
        
        # Factor 6: Content quality bonus (0-5 points)
        # Longer, more detailed content gets bonus points
        content_length = len(article.get("raw_content", ""))
        if content_length > 500:
            score += 5
        elif content_length > 200:
            score += 3
        elif content_length > 100:
            score += 1
        
        return round(score, 1)
    
    def _clean_html_content(self, html_content: str) -> str:
        """Clean HTML content and extract meaningful text."""
        if not html_content:
            return ""
        
        try:
            # Parse HTML and extract text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text and clean it up
            text = soup.get_text()
            
            # Clean up whitespace and formatting
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            logger.warning(f"Error cleaning HTML content: {str(e)}")
            # Fallback: simple regex-based cleaning
            text = re.sub(r'<[^>]*>', '', html_content)
            text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
            text = ' '.join(text.split())
            return text
    
    def _create_fallback_summary(self, title: str) -> str:
        """Create an intelligent fallback summary based on title analysis."""
        title_lower = title.lower()
        
        # Market movement keywords
        if "futures rise" in title_lower or "futures up" in title_lower:
            return f"Market futures are showing positive momentum. Major indices are expected to open higher based on pre-market activity."
        elif "futures fall" in title_lower or "futures down" in title_lower:
            return f"Market futures indicate negative sentiment. Pre-market activity suggests indices may open lower."
        elif "all-time high" in title_lower or "record high" in title_lower:
            return f"Markets or specific stocks are reaching new peaks. This reflects continued bullish sentiment and strong confidence."
        elif "earnings" in title_lower:
            return f"Corporate earnings report is impacting market sentiment. Quarterly results could influence sector performance and expectations."
        elif "jobs report" in title_lower or "employment" in title_lower:
            return f"Employment data release is affecting market outlook. Labor market conditions may influence Federal Reserve policy and economic growth expectations."
        elif "fed" in title_lower or "federal reserve" in title_lower:
            return f"Federal Reserve activity is impacting monetary policy expectations. Central bank actions could affect interest rates and market liquidity."
        else:
            return f"Market development of significance. The news represents important financial information that could influence trading activity."
    
    def _extract_tickers_from_title(self, title: str) -> List[str]:
        """Extract potential stock tickers from article title."""
        # Common pattern: look for 3-5 letter uppercase combinations that could be tickers
        import re
        potential_tickers = re.findall(r'\b[A-Z]{2,5}\b', title)
        
        # Filter out common false positives
        false_positives = {"THE", "AND", "FOR", "WITH", "FROM", "NYSE", "NASDAQ", "DOW", "ALL", "NEW", "SET", "END"}
        tickers = [ticker for ticker in potential_tickers if ticker not in false_positives]
        
        # Add common index references
        title_upper = title.upper()
        if "S&P 500" in title or "S&P500" in title:
            tickers.append("SPY")
        if "DOW JONES" in title_upper or " DOW " in title_upper:
            tickers.append("DIA")
        if "NASDAQ" in title_upper:
            tickers.append("QQQ")
            
        return list(set(tickers))  # Remove duplicates
    
    def _create_fallback_implication_title(self, title: str) -> str:
        """Create a short, actionable implication title from the original headline."""
        title_lower = title.lower()
        
        # Market movement patterns
        if "futures rise" in title_lower or "futures up" in title_lower:
            return "Markets set to open higher on optimism"
        elif "futures fall" in title_lower or "futures down" in title_lower:
            return "Markets face pressure ahead of open"
        elif "all-time high" in title_lower or "record high" in title_lower:
            return "Stocks reach new peaks on bullish sentiment"
        elif "rally" in title_lower:
            return "Market rally extends gains"
        elif "decline" in title_lower or "fall" in title_lower:
            return "Market faces headwinds"
        elif "earnings" in title_lower and ("beat" in title_lower or "strong" in title_lower):
            return "Strong earnings boost sector outlook"
        elif "earnings" in title_lower and ("miss" in title_lower or "weak" in title_lower):
            return "Weak earnings weigh on sentiment"
        elif "jobs report" in title_lower or "employment" in title_lower:
            return "Jobs data impacts Fed policy outlook"
        elif "fed" in title_lower or "federal reserve" in title_lower:
            if "rate" in title_lower:
                return "Fed policy shift affects markets"
            else:
                return "Central bank moves impact outlook"
        elif "inflation" in title_lower:
            return "Inflation data shapes market direction"
        elif "gdp" in title_lower or "economic" in title_lower:
            return "Economic data influences sentiment"
        elif any(word in title_lower for word in ["rise", "up", "gains", "surge"]):
            return "Positive momentum drives market gains"
        elif any(word in title_lower for word in ["down", "drop", "weak"]):
            return "Market weakness raises concerns"
        else:
            # Generic fallback based on first few words
            words = title.split()[:6]
            if len(" ".join(words)) > 50:
                words = words[:4]
            return f"Market watches {' '.join(words).lower()}" 