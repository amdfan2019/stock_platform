import asyncio
import aiohttp
import feedparser
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import quote_plus
import google.generativeai as genai
from ..config import settings
from loguru import logger
from ..models import NewsArticle, MarketNewsSummary
from ..models import GeminiApiCallLog


class NewsCollector:
    """
    Service for collecting and analyzing news articles related to stocks.
    Scrapes multiple sources and uses LLM for sentiment analysis and summarization.
    """
    
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=settings.google_api_key)
        self.llm_model = genai.GenerativeModel(settings.llm_model)
        
        # News sources configuration
        self.news_sources = {
            "finviz": "https://finviz.com/news.ashx?t={ticker}",
            "yahoo": "https://finance.yahoo.com/quote/{ticker}/news",
            "reuters": "https://www.reuters.com/search/news?query={ticker}",
            "google_news": "https://news.google.com/rss/search?q={ticker}&hl=en-US&gl=US&ceid=US:en"
        }
    
    async def collect_stock_news(self, ticker: str, hours_lookback: int = 24) -> List[Dict]:
        """
        Collect and analyze news for a specific stock ticker.
        
        Args:
            ticker: Stock ticker symbol
            hours_lookback: How many hours back to look for news
            
        Returns:
            List of processed news articles with sentiment analysis
        """
        try:
            logger.info(f"Collecting news for {ticker}")
            
            # Collect news from multiple sources in parallel
            news_tasks = [
                self._scrape_google_news(ticker, hours_lookback),
                self._scrape_finviz_news(ticker, hours_lookback),
                self._scrape_yahoo_news(ticker, hours_lookback),
                self._scrape_reuters_rss(ticker, hours_lookback),
                self._scrape_marketwatch_news(ticker, hours_lookback)
            ]
            
            # Execute all tasks concurrently
            news_results = await asyncio.gather(*news_tasks, return_exceptions=True)
            
            # Combine all news articles
            all_articles = []
            for result in news_results:
                if isinstance(result, list):
                    all_articles.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"News collection error: {str(result)}")
            
            # Remove duplicates based on title similarity
            unique_articles = await self._deduplicate_articles(all_articles)
            
            # Process articles with LLM analysis
            processed_articles = []
            for article in unique_articles:
                try:
                    processed_article = await self._analyze_article_sentiment(article)
                    if processed_article:
                        processed_articles.append(processed_article)
                except Exception as e:
                    logger.warning(f"Error processing article: {str(e)}")
                    continue
            
            logger.info(f"Collected and processed {len(processed_articles)} articles for {ticker}")
            return processed_articles
            
        except Exception as e:
            logger.error(f"Error collecting news for {ticker}: {str(e)}")
            return []
    
    async def _scrape_google_news(self, ticker: str, hours_lookback: int) -> List[Dict]:
        """Scrape Google News RSS feed for stock-related news."""
        try:
            # Enhanced search queries for better stock coverage
            queries = [
                f'"{ticker}" stock earnings revenue',
                f'"{ticker}" financial results',
                f'"{ticker}" company news'
            ]
            
            all_articles = []
            
            for query in queries:
                try:
                    url = self.news_sources["google_news"].format(ticker=quote_plus(query))
                    
                    async with aiohttp.ClientSession() as session:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }
                        async with session.get(url, headers=headers) as response:
                            rss_content = await response.text()
                    
                    feed = feedparser.parse(rss_content)
                    cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
                    
                    for entry in feed.entries[:10]:  # Limit per query
                        try:
                            # Handle different date formats
                            published = None
                            try:
                                published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %Z")
                            except:
                                try:
                                    published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                                except:
                                    # If we can't parse date, use current time
                                    published = datetime.now()
                            
                            if published < cutoff_time:
                                continue
                            
                            # Clean the title (Google News sometimes has source info in title)
                            title = entry.title
                            if " - " in title:
                                title = title.split(" - ")[0].strip()
                            
                            all_articles.append({
                                "title": title,
                                "url": entry.link,
                                "source": "Google News",
                                "published_at": published,
                                "raw_content": entry.get("summary", title)
                            })
                            
                        except Exception as e:
                            logger.warning(f"Error parsing Google News entry: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Error with Google News query '{query}': {str(e)}")
                    continue
            
            return all_articles
            
        except Exception as e:
            logger.warning(f"Error scraping Google News: {str(e)}")
            return []
    
    async def _scrape_finviz_news(self, ticker: str, hours_lookback: int) -> List[Dict]:
        """Scrape Finviz news for specific ticker."""
        try:
            url = self.news_sources["finviz"].format(ticker=ticker)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url)
                
                # Wait for news table to load
                await page.wait_for_selector("table.fullview-news-outer", timeout=10000)
                
                # Extract news items
                news_items = await page.query_selector_all("tr.cursor-pointer")
                
                articles = []
                cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
                
                for item in news_items[:15]:  # Limit to 15 items
                    try:
                        # Extract time
                        time_elem = await item.query_selector("td")
                        time_text = await time_elem.inner_text() if time_elem else ""
                        
                        # Extract title and link
                        link_elem = await item.query_selector("a")
                        if not link_elem:
                            continue
                        
                        title = await link_elem.inner_text()
                        url = await link_elem.get_attribute("href")
                        
                        # Parse time (Finviz uses relative times like "10h ago")
                        published_at = self._parse_relative_time(time_text)
                        
                        if published_at < cutoff_time:
                            continue
                        
                        articles.append({
                            "title": title,
                            "url": url,
                            "source": "Finviz",
                            "published_at": published_at,
                            "raw_content": title  # Finviz doesn't provide full content
                        })
                        
                    except Exception as e:
                        logger.warning(f"Error parsing Finviz item: {str(e)}")
                        continue
                
                await browser.close()
                return articles
                
        except Exception as e:
            logger.warning(f"Error scraping Finviz: {str(e)}")
            return []
    
    async def _scrape_yahoo_news(self, ticker: str, hours_lookback: int) -> List[Dict]:
        """Scrape Yahoo Finance news."""
        try:
            url = self.news_sources["yahoo"].format(ticker=ticker)
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                async with session.get(url, headers=headers) as response:
                    html = await response.text()
            
            soup = BeautifulSoup(html, "html.parser")
            
            # Find news items (Yahoo's structure may change)
            news_items = soup.find_all("li", class_="js-stream-content")
            
            articles = []
            cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
            
            for item in news_items[:10]:
                try:
                    title_elem = item.find("h3")
                    if not title_elem:
                        continue
                    
                    link_elem = title_elem.find("a")
                    if not link_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = link_elem.get("href")
                    
                    # Yahoo URLs might be relative
                    if url.startswith("/"):
                        url = "https://finance.yahoo.com" + url
                    
                    # Try to find publish time
                    time_elem = item.find("time")
                    published_at = datetime.now()  # Default to now if can't parse
                    
                    if published_at < cutoff_time:
                        continue
                    
                    articles.append({
                        "title": title,
                        "url": url,
                        "source": "Yahoo Finance",
                        "published_at": published_at,
                        "raw_content": title
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing Yahoo item: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.warning(f"Error scraping Yahoo News: {str(e)}")
            return []
    
    async def _scrape_reuters_rss(self, ticker: str, hours_lookback: int) -> List[Dict]:
        """Scrape Reuters RSS feed for business news."""
        try:
            # Use Reuters business RSS feed
            url = "https://feeds.reuters.com/reuters/businessNews"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    rss_content = await response.text()
            
            feed = feedparser.parse(rss_content)
            articles = []
            
            cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
            
            for entry in feed.entries[:15]:  # Limit to 15 most recent
                try:
                    # Check if ticker is mentioned in title or summary
                    title_lower = entry.title.lower()
                    summary_lower = entry.get("summary", "").lower()
                    ticker_lower = ticker.lower()
                    
                    if ticker_lower in title_lower or ticker_lower in summary_lower:
                        published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z").replace(tzinfo=None)
                        if published < cutoff_time:
                            continue
                        
                        articles.append({
                            "title": entry.title,
                            "url": entry.link,
                            "source": "Reuters",
                            "published_at": published,
                            "raw_content": entry.get("summary", "")
                        })
                        
                except Exception as e:
                    logger.warning(f"Error parsing Reuters RSS entry: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.warning(f"Error scraping Reuters RSS: {str(e)}")
            return []

    async def _scrape_marketwatch_news(self, ticker: str, hours_lookback: int) -> List[Dict]:
        """Scrape MarketWatch news for specific ticker."""
        try:
            # MarketWatch search URL
            url = f"https://www.marketwatch.com/search?q={ticker}&m=Keyword&rpp=25&mp=806&bd=false&rs=true"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                async with session.get(url, headers=headers) as response:
                    html = await response.text()
            
            soup = BeautifulSoup(html, "html.parser")
            articles = []
            
            # Find article elements (MarketWatch structure)
            article_elements = soup.find_all("div", class_="searchresult")
            
            cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
            
            for element in article_elements[:10]:  # Limit to 10 articles
                try:
                    title_elem = element.find("h3") or element.find("a")
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link_elem = element.find("a")
                    url = link_elem.get("href") if link_elem else ""
                    
                    if url and not url.startswith("http"):
                        url = "https://www.marketwatch.com" + url
                    
                    # Use current time as published time (MarketWatch doesn't always show dates in search)
                    published_at = datetime.now()
                    
                    articles.append({
                        "title": title,
                        "url": url,
                        "source": "MarketWatch",
                        "published_at": published_at,
                        "raw_content": title
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing MarketWatch article: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.warning(f"Error scraping MarketWatch: {str(e)}")
            return []
    
    async def _analyze_article_sentiment(self, article: Dict) -> Optional[Dict]:
        """Analyze article sentiment and extract key information using LLM."""
        try:
            content = f"Title: {article['title']}\nContent: {article.get('raw_content', '')}"
            
            prompt = f"""
            Analyze this financial news article and provide:
            
            1. Sentiment score (-1 to 1, where -1 is very negative, 0 is neutral, 1 is very positive)
            2. Sentiment label (positive/negative/neutral)
            3. Confidence score (0 to 1)
            4. Impact level (high/medium/low)
            5. Impact categories (list from: earnings, management, regulation, product, market, acquisition, legal, other)
            6. Key actionable signals (list of specific events or changes)
            7. Summary in under 280 characters
            8. Key keywords/entities mentioned
            
            Article: {content}
            
            Respond with valid JSON only:
            {{
                "sentiment_score": float,
                "sentiment_label": "positive|negative|neutral",
                "confidence_score": float,
                "impact_level": "high|medium|low",
                "impact_categories": ["category1", "category2"],
                "extracted_signals": ["signal1", "signal2"],
                "summary": "brief summary under 280 chars",
                "keywords": ["keyword1", "keyword2"]
            }}
            """
            
            response = await self.llm_model.generate_content_async(prompt)
            
            # Log Gemini API call
            try:
                db_log = SessionLocal()
                log_entry = GeminiApiCallLog(
                    timestamp=datetime.utcnow(),
                    purpose='news_collector',
                    prompt=prompt
                )
                db_log.add(log_entry)
                db_log.commit()
                db_log.close()
            except Exception as e:
                logger.warning(f"Failed to log Gemini API call: {e}")
            
            # Parse LLM response
            try:
                analysis = json.loads(response.text)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    raise ValueError("Could not parse LLM response as JSON")
            
            # Combine original article data with analysis
            processed_article = {
                **article,
                **analysis,
                "processed_at": datetime.now()
            }
            
            return processed_article
            
        except Exception as e:
            logger.warning(f"Error analyzing article sentiment: {str(e)}")
            return None
    
    async def _deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicate articles based on title similarity."""
        try:
            if not articles:
                return []
            
            unique_articles = []
            seen_titles = set()
            
            for article in articles:
                title = article.get("title", "").lower()
                
                # Simple deduplication - check if similar title already exists
                is_duplicate = False
                for seen_title in seen_titles:
                    # Calculate simple similarity (could be improved with more sophisticated algorithms)
                    similarity = len(set(title.split()) & set(seen_title.split())) / max(len(title.split()), len(seen_title.split()))
                    if similarity > 0.7:  # 70% word overlap threshold
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unique_articles.append(article)
                    seen_titles.add(title)
            
            return unique_articles
            
        except Exception as e:
            logger.warning(f"Error deduplicating articles: {str(e)}")
            return articles
    
    def _parse_relative_time(self, time_str: str) -> datetime:
        """Parse relative time strings like '2h ago', '30m ago'."""
        try:
            now = datetime.now()
            time_str = time_str.lower().strip()
            
            if "ago" not in time_str:
                return now
            
            # Extract number and unit
            match = re.search(r'(\d+)([hm])', time_str)
            if not match:
                return now
            
            value = int(match.group(1))
            unit = match.group(2)
            
            if unit == 'h':
                return now - timedelta(hours=value)
            elif unit == 'm':
                return now - timedelta(minutes=value)
            else:
                return now
                
        except Exception:
            return datetime.now()
    
    async def calculate_news_sentiment_signal(self, articles: List[Dict]) -> Dict:
        """Calculate aggregate sentiment signal from multiple news articles."""
        try:
            if not articles:
                return {
                    "overall_sentiment": 0.0,
                    "confidence": 0.0,
                    "article_count": 0,
                    "high_impact_count": 0,
                    "recent_sentiment_trend": 0.0
                }
            
            # Weight articles by recency and impact
            weighted_sentiment = 0.0
            total_weight = 0.0
            high_impact_count = 0
            
            for article in articles:
                # Calculate recency weight (more recent = higher weight)
                hours_old = (datetime.now() - article.get("published_at", datetime.now())).total_seconds() / 3600
                recency_weight = max(0.1, 1.0 - (hours_old / 24))  # Decay over 24 hours
                
                # Impact weight
                impact_weight = {"high": 3.0, "medium": 2.0, "low": 1.0}.get(
                    article.get("impact_level", "low"), 1.0
                )
                
                # Confidence weight
                confidence_weight = article.get("confidence_score", 0.5)
                
                # Combined weight
                weight = recency_weight * impact_weight * confidence_weight
                
                sentiment = article.get("sentiment_score", 0.0)
                weighted_sentiment += sentiment * weight
                total_weight += weight
                
                if article.get("impact_level") == "high":
                    high_impact_count += 1
            
            # Calculate overall sentiment
            overall_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0.0
            
            # Calculate confidence based on number of articles and consistency
            confidence = min(1.0, len(articles) / 10.0)  # Higher confidence with more articles
            
            # Calculate recent trend (last 6 hours vs overall)
            recent_articles = [
                a for a in articles
                if (datetime.now() - a.get("published_at", datetime.now())).total_seconds() < 6 * 3600
            ]
            
            recent_sentiment = 0.0
            if recent_articles:
                recent_sentiment = sum(a.get("sentiment_score", 0.0) for a in recent_articles) / len(recent_articles)
            
            return {
                "overall_sentiment": overall_sentiment,
                "confidence": confidence,
                "article_count": len(articles),
                "high_impact_count": high_impact_count,
                "recent_sentiment_trend": recent_sentiment - overall_sentiment
            }
            
        except Exception as e:
            logger.error(f"Error calculating news sentiment signal: {str(e)}")
            return {
                "overall_sentiment": 0.0,
                "confidence": 0.0,
                "article_count": 0,
                "high_impact_count": 0,
                "recent_sentiment_trend": 0.0
            } 