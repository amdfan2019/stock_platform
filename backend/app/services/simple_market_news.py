import asyncio
import aiohttp
import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import google.generativeai as genai
from ..config import settings
from loguru import logger
import hashlib
import json
import re
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..database import SessionLocal
from ..models import MarketArticle, MarketNewsSummary, GeminiApiCallLog
import difflib


class SimpleMarketNews:
    """
    Simple and reliable market news processor that:
    1. Fetches articles from reliable RSS feeds
    2. Extracts full article content (up to 1000 chars)
    3. Uses LLM to generate brief headline + bullet points + market signal
    4. Provides clean, actionable news items
    """
    
    def __init__(self):
        # Configure Gemini API
        genai.configure(api_key=settings.google_api_key)
        self.llm_model = genai.GenerativeModel(settings.llm_model)
        
        # Non-paywalled, high-priority RSS feeds for financial news
        self.news_sources = [
            # BBC Business (not paywalled)
            {
                "name": "BBC Business",
                "url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                "priority": 1,
                "type": "rss"
            },
            # NPR Business (not paywalled)
            {
                "name": "NPR Business",
                "url": "https://feeds.npr.org/1006/rss.xml",
                "priority": 2,
                "type": "rss"
            },
            # CNBC Direct (main news page, not RSS)
            {
                "name": "CNBC (Direct)",
                "url": "https://www.cnbc.com/world/?region=world",
                "priority": 3,
                "type": "listing"
            },
        ]
    
    async def get_market_news(self, hours_back: int = 24, max_articles: int = 10) -> list:
        """
        Always fetch/process new articles, merge/deduplicate with DB, update DB if new articles are more relevant, and return the top 10 most relevant articles from the last 24 hours.
        """
        try:
            async with asyncio.timeout(30):
                extended_hours = max(hours_back, 48)
                logger.info(f"Fetching market news for the last {extended_hours} hours (requested: {hours_back})")
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=extended_hours)

            # 1. Fetch fresh articles from sources
            raw_articles = await self._fetch_raw_articles(extended_hours)
            logger.info(f"Fetched {len(raw_articles)} raw articles from sources")

            # 2. Process new articles through LLM (limit to 10 for speed)
            processed_articles = []
            articles_to_process = raw_articles[:min(10, max_articles)]
            logger.info(f"Processing {len(articles_to_process)} articles through LLM")
            for i, article in enumerate(articles_to_process):
                try:
                    logger.info(f"Processing article {i+1}/{len(articles_to_process)}: {article['title'][:50]}...")
                    processed = await self._process_article_with_llm(article)
                    if processed:
                        processed_articles.append(processed)
                        await self._store_article(processed)
                except Exception as e:
                    logger.warning(f"Failed to process article {i+1}: {str(e)}")
                    continue
            logger.info(f"Successfully processed {len(processed_articles)} articles")

            # 3. Query all articles from DB from last 24h
            db = SessionLocal()
            try:
                all_recent = db.query(MarketArticle).filter(
                    MarketArticle.published_at >= datetime.now(timezone.utc) - timedelta(hours=24)
                ).order_by(desc(MarketArticle.published_at)).all()
                formatted = self._format_articles_for_frontend(all_recent)
                for a in formatted:
                    a['relevance_score'] = self._relevance_score(a)
                # Sort by relevance, then recency, and take top 10
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
                top = sorted(formatted, key=lambda x: (-x['relevance_score'], -utc_ts(x.get('published_at'))))[:max_articles]
                # Resort by recency for frontend
                top = sorted(top, key=lambda x: -utc_ts(x.get('published_at')))

                # --- NEW: Generate and store LLM summary of top 10 articles ---
                if top:
                    try:
                        # Prepare input for LLM: headlines and bullet points
                        summary_input = "\n".join([
                            f"{i+1}. {a['brief_headline']}\n- " + "\n- ".join(a['bullet_points'])
                            for i, a in enumerate(top)
                        ])
                        summary_prompt = f"""
You are a professional financial news analyst. Given the following 10 most relevant market news article summaries, write a concise, actionable overview of what is happening in the markets right now. Your summary MUST be 3-4 sentences, avoid generic statements, and should NOT explain what any indicator or index is. Focus on the most important, actionable themes and developments only.

ARTICLE SUMMARIES:\n{summary_input}\n
SUMMARY (3-4 sentences, no explanations):
"""
                        llm_response = await self.llm_model.generate_content_async(summary_prompt)
                        summary_text = llm_response.text.strip() if hasattr(llm_response, 'text') else str(llm_response)
                        # Store in DB, accumulating all summaries
                        article_ids = [a.get('id') for a in top if a.get('id')]
                        db_summary = MarketNewsSummary(
                            summary=summary_text,
                            article_ids=article_ids
                        )
                        db.add(db_summary)
                        db.commit()
                        logger.info("Stored new market news summary in DB.")
                        # Log Gemini API call
                        try:
                            db_log = SessionLocal()
                            log_entry = GeminiApiCallLog(
                                timestamp=datetime.utcnow(),
                                purpose='market_news_summary',
                                prompt=summary_prompt
                            )
                            db_log.add(log_entry)
                            db_log.commit()
                            db_log.close()
                        except Exception as e:
                            logger.warning(f"Failed to log Gemini API call: {e}")
                    except Exception as e:
                        logger.error(f"Failed to generate/store market news summary: {str(e)}")
                # --- END NEW ---

                return top
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting market news: {str(e)}")
            return []
    
    async def _fetch_raw_articles(self, hours_back: int) -> List[Dict]:
        """Fetch raw articles from RSS feeds and direct listings."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        all_articles = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/rss+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10, connect=5), headers=headers) as session:
            for source in self.news_sources:
                try:
                    logger.info(f"Fetching from {source['name']}")
                    if source.get("type") == "rss":
                        async with session.get(source['url'], verify_ssl=False) as response:
                            logger.info(f"{source['name']} response status: {response.status}")
                            if response.status == 200:
                                rss_content = await response.text()
                                logger.info(f"{source['name']} content length: {len(rss_content)}")
                                feed = feedparser.parse(rss_content)
                                if hasattr(feed, 'bozo_exception'):
                                    logger.warning(f"{source['name']}: Feed parsing error - {feed.bozo_exception}")
                                    continue
                                if not hasattr(feed, 'entries'):
                                    logger.warning(f"{source['name']}: No entries found in feed")
                                    continue
                                logger.info(f"{source['name']}: Found {len(feed.entries)} total entries")
                                source_articles = 0
                                for entry in feed.entries:
                                    published_at = self._parse_date(entry)
                                    logger.debug(f"Entry: {entry.title[:60]}... | Published: {published_at} | Cutoff: {cutoff_time}")
                                    if published_at and published_at > cutoff_time:
                                        content = await self._extract_article_content(session, entry.link)
                                        logger.debug(f"Extracted {len(content)} chars from {entry.link[:50]}...")
                                        article = {
                                            'title': entry.title,
                                            'url': entry.link,
                                            'source': source['name'],
                                            'published_at': published_at,
                                            'content': content,
                                            'priority': source['priority']
                                        }
                                        all_articles.append(article)
                                        source_articles += 1
                                logger.info(f"{source['name']}: Added {source_articles} articles within time window")
                    elif source.get("type") == "listing" and 'cnbc' in source['name'].lower():
                        # Direct scrape CNBC main news page
                        async with session.get(source['url'], timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            html = await resp.text()
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        article_links = []
                        for a in soup.select('a.Card-title, a.LatestNews-headline, a.StoryCard-headline, a[data-analytics="LatestNews-headline"]'):
                            href = a.get('href')
                            if href and href.startswith('/'):
                                href = 'https://www.cnbc.com' + href
                            if href and '/202' in href and href not in article_links:
                                article_links.append(href)
                            if len(article_links) >= 10:
                                break
                        for url in article_links:
                            logger.info(f"Testing CNBC article: {url}")
                            content = await self._extract_article_content(session, url)
                            # Try to extract published date from article HTML
                            published_at = await self._extract_cnbc_published_date(session, url)
                            if not published_at:
                                published_at = datetime.now(timezone.utc)
                            article = {
                                'title': url.split('/')[-1].replace('-', ' ').title(),
                                'url': url,
                                'source': source['name'],
                                'published_at': published_at,
                                'content': content,
                                'priority': source['priority']
                            }
                            if published_at:
                                article['published_at'] = published_at
                            all_articles.append(article)
                        logger.info(f"{source['name']}: Added {len(article_links)} articles from listing page")
                except Exception as e:
                    logger.warning(f"Error fetching from {source['name']}: {str(e)}")
                    continue
        all_articles.sort(key=lambda x: (-x['published_at'].timestamp(), x['priority']))
        unique_articles = self._remove_duplicates(all_articles)
        logger.info(f"After deduplication: {len(unique_articles)} unique articles")
        return unique_articles
    
    async def _extract_article_content(self, session: aiohttp.ClientSession, url: str) -> str:
        """Extract the main content from an article URL, following Google News redirects if needed."""
        try:
            # Handle Google News redirect links
            if "news.google.com/rss/articles/" in url:
                try:
                    # First, try to follow HTTP redirects
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as response:
                        final_url = str(response.url)
                        if final_url != url:
                            logger.debug(f"Google News HTTP redirect: {url[:50]}... -> {final_url[:80]}...")
                            url = final_url
                        else:
                            html = await response.text()
                            # Try to find <meta http-equiv="refresh" content="0;url=...">
                            import re
                            match = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^;]+;url=([^"\']+)["\']', html, re.IGNORECASE)
                            if match:
                                real_url = match.group(1)
                                logger.debug(f"Google News meta refresh: {url[:50]}... -> {real_url[:80]}...")
                                url = real_url
                            else:
                                logger.warning(f"Could not find real article link in Google News page: {url}")
                                return ""
                except Exception as e:
                    logger.warning(f"Error following Google News redirect: {url} ({str(e)})")
                    return ""
            # Check for known paywalled domains
            if any(domain in url for domain in ["marketwatch.com", "wsj.com", "ft.com", "seekingalpha.com"]):
                logger.debug(f"Skipping paywall site: {url}")
                return ""
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    html = await response.text()
                    # Try multiple extraction methods
                    content = self._extract_content_with_newspaper3k(html)
                    if not content:
                        content = self._extract_content_with_bs4(html)
                    extracted_length = len(content)
                    logger.debug(f"Content extraction from {url[:50]}... -> {extracted_length} chars")
                    if content:
                        return content[:1000]
                else:
                    logger.debug(f"HTTP {response.status} for {url}")
        except Exception as e:
            logger.debug(f"Failed to extract content from {url}: {str(e)}")
        return ""
    
    def _extract_content_with_newspaper3k(self, html: str) -> str:
        """Extract content using newspaper3k library."""
        try:
            # Import the correct module name
            from newspaper import Article
            
            article = Article('')
            article.set_html(html)
            article.parse()
            
            if article.text and len(article.text.strip()) > 100:
                logger.debug(f"newspaper3k extracted {len(article.text)} characters")
                return article.text.strip()
            else:
                logger.debug(f"newspaper3k extracted text too short: {len(article.text) if article.text else 0} chars")
                
        except ImportError as e:
            logger.warning(f"newspaper3k not installed: {str(e)}")
        except Exception as e:
            logger.debug(f"newspaper3k extraction failed: {str(e)}")
        
        return ""
    
    def _extract_content_with_bs4(self, html: str) -> str:
        """Fallback content extraction using BeautifulSoup."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Look for main content areas
            content_selectors = [
                'article',
                '[role="main"]',
                '.article-body',
                '.story-body',
                '.content',
                '.post-content',
                'main',
                '.entry-content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    text = content_elem.get_text(strip=True)
                    if len(text) > 100:
                        return text
            
            # Fallback: get all paragraph text
            paragraphs = soup.find_all('p')
            if paragraphs:
                text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                if len(text) > 100:
                    return text
                    
        except Exception as e:
            logger.debug(f"BeautifulSoup extraction failed: {str(e)}")
        
        return ""
    
    async def _process_article_with_llm(self, article: Dict) -> Optional[Dict]:
        """Process article with LLM to generate summary and market signal."""
        try:
            # Prepare content for LLM
            content_to_analyze = article['content'] if article['content'] else article['title']
            
            # Log what content we're actually analyzing
            logger.info(f"LLM analyzing: content_length={len(article['content'])}, using={'full_content' if article['content'] else 'title_only'}")
            logger.debug(f"Content preview: {content_to_analyze[:200]}...")
            
            if len(content_to_analyze.strip()) < 50:
                logger.debug(f"Article content too short, skipping: {article['title']}")
                return None
            
            # Shorter, faster LLM prompt
            prompt = f"""
            Analyze this financial news and respond with ONLY valid JSON:

            Title: {article['title']}
            Content: {content_to_analyze[:500]}

            IMPORTANT: If the article is primarily about events that occurred more than 1 month before the article's published date, or is a retrospective/recap of past events, you MUST set 'market_signal' to 'neutral' regardless of the content's tone or implications. Only assign 'bullish' or 'bearish' if the news is about recent or upcoming events (within 1 month of the article's published date).

            {{
                "brief_headline": "Concise market implication (60 chars max)",
                "bullet_points": ["Key insight 1", "Key insight 2", "Key insight 3"],
                "market_signal": "bullish|bearish|neutral",
                "confidence": 0.8,
                "mentioned_tickers": ["TICKER"],
                "key_theme": "earnings|fed_policy|economic_data|sector_news|other"
            }}
            """
            
            response = await self.llm_model.generate_content_async(prompt)
            
            if response.text:
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    llm_analysis = json.loads(json_match.group())
                    
                    # Combine original article data with LLM analysis
                    processed_article = {
                        'title': article['title'],
                        'brief_headline': llm_analysis.get('brief_headline', article['title'][:80]),
                        'bullet_points': llm_analysis.get('bullet_points', [])[:3],  # Max 3 points
                        'market_signal': llm_analysis.get('market_signal', 'neutral'),
                        'confidence': llm_analysis.get('confidence', 0.5),
                        'mentioned_tickers': llm_analysis.get('mentioned_tickers', []),
                        'key_theme': llm_analysis.get('key_theme', 'other'),
                        'url': article['url'],
                        'source': article['source'],
                        'published_at': article['published_at'],
                        'content_length': len(content_to_analyze),
                        'has_full_content': len(article['content']) > 100
                    }
                    
                    # Log Gemini API call
                    try:
                        db_log = SessionLocal()
                        log_entry = GeminiApiCallLog(
                            timestamp=datetime.utcnow(),
                            purpose='market_news_article',
                            prompt=prompt
                        )
                        db_log.add(log_entry)
                        db_log.commit()
                        db_log.close()
                    except Exception as e:
                        logger.warning(f"Failed to log Gemini API call: {e}")
                    
                    return processed_article
                    
        except Exception as e:
            logger.error(f"LLM processing failed for article: {str(e)}")
        
        return None
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse date from RSS entry and ensure UTC timezone-aware."""
        try:
            import time
            from dateutil import parser
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                parsed_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                logger.debug(f"Parsed date from published_parsed: {parsed_date}")
                return parsed_date
            elif hasattr(entry, 'published'):
                parsed_date = parser.parse(entry.published)
                if parsed_date.tzinfo is None:
                    parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                logger.debug(f"Parsed date from published string '{entry.published}': {parsed_date}")
                return parsed_date
            else:
                logger.debug(f"No date fields found in entry, using current time")
                return datetime.now(timezone.utc)
        except Exception as e:
            logger.warning(f"Date parsing failed for entry: {str(e)}")
            return datetime.now(timezone.utc)
    
    def _normalize_title(self, title: str) -> str:
        # Lowercase, remove punctuation, collapse whitespace
        return re.sub(r'[^\w\s]', '', title.lower()).strip()

    def _is_index_news(self, title: str) -> bool:
        # Heuristic: does the title mention major indices or market updates?
        keywords = ["sensex", "nifty", "market live", "stock market", "market update", "market open", "market close"]
        t = title.lower()
        return any(k in t for k in keywords)

    def _remove_duplicates(self, articles: List[Dict]) -> List[Dict]:
        """Stricter deduplication: fuzzy match, normalized title, and index news grouping."""
        if not articles:
            return []
        unique = []
        seen = []
        for article in articles:
            is_duplicate = False
            for seen_article in seen:
                # Stricter fuzzy matching
                title_ratio = difflib.SequenceMatcher(None, article['title'], seen_article['title']).ratio()
                content_ratio = 0.0
                if article.get('content') and seen_article.get('content'):
                    content_ratio = difflib.SequenceMatcher(None, article['content'], seen_article['content']).ratio()
                # Also group index/market news by normalized title
                if self._is_index_news(article['title']) and self._is_index_news(seen_article['title']):
                    norm1 = self._normalize_title(article['title'])
                    norm2 = self._normalize_title(seen_article['title'])
                    if norm1 == norm2 or title_ratio > 0.6:
                        is_duplicate = True
                        break
                # Stricter threshold for all others
                if title_ratio > 0.7 or content_ratio > 0.5:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(article)
                seen.append(article)
        return unique

    def _relevance_score(self, article: dict) -> float:
        # Score: LLM confidence (0-1), +0.2 if tickers, +0.2 if market_signal not neutral, + recency bonus
        score = float(article.get('confidence', 0.5))
        if article.get('mentioned_tickers'):
            score += 0.2
        if article.get('market_signal', 'neutral') != 'neutral':
            score += 0.2
        # Gentler recency bonus: up to +0.1 for articles within last 24 hours
        now = datetime.now(timezone.utc)
        published = article.get('published_at')
        if published:
            if isinstance(published, str):
                try:
                    published = datetime.fromisoformat(published)
                except Exception:
                    published = now
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            hours_ago = (now - published).total_seconds() / 3600
            if hours_ago < 24:
                score += 0.1 * (1 - hours_ago / 24)
        return min(score, 1.0)
    
    async def _store_article(self, article: Dict) -> None:
        """
        Store processed article in database if not already present (by URL).
        Do NOT remove lower-relevance articles; just add new ones if unique.
        """
        try:
            db = SessionLocal()
            try:
                content_for_hash = f"{article['title']}{article.get('brief_headline', '')}"
                content_hash = hashlib.md5(content_for_hash.encode()).hexdigest()
                existing = db.query(MarketArticle).filter(
                    MarketArticle.url == article['url']
                ).first()
                if existing:
                    logger.debug(f"Article already exists in DB: {article['title'][:50]}...")
                    return
                db_article = MarketArticle(
                    url=article['url'],
                    title=article['title'],
                    source=article['source'],
                    published_at=article['published_at'],
                    implication_title=article.get('brief_headline'),
                    ai_summary='\n'.join(article.get('bullet_points', [])),
                    market_impact=article.get('confidence', 0.5),
                    sentiment=article.get('market_signal', 'neutral'),
                    mentioned_tickers=article.get('mentioned_tickers', []),
                    affected_sectors=[article.get('key_theme', 'other')],
                    relevance_score=article.get('confidence', 0.5),
                    content_hash=content_hash
                )
                db.add(db_article)
                db.commit()
                logger.debug(f"Stored article: {article['title']}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to store article: {str(e)}")
    
    def _format_articles_for_frontend(self, db_articles: List[MarketArticle]) -> List[Dict]:
        """Format database articles for frontend consumption."""
        formatted_articles = []
        
        for article in db_articles:
            # Parse bullet points from ai_summary
            bullet_points = []
            if article.ai_summary:
                bullet_points = [point.strip() for point in article.ai_summary.split('\n') if point.strip()]
            
            formatted_article = {
                'title': article.title,
                'brief_headline': article.implication_title or article.title,
                'bullet_points': bullet_points,
                'market_signal': article.sentiment or 'neutral',
                'confidence': float(article.market_impact) if article.market_impact else 0.5,
                'mentioned_tickers': article.mentioned_tickers or [],
                'key_theme': article.affected_sectors[0] if article.affected_sectors else 'other',
                'url': article.url,
                'source': article.source,
                'published_at': article.published_at,
                'content_length': 0,  # Not stored in DB
                'has_full_content': True  # Assume true for stored articles
            }
            formatted_articles.append(formatted_article)
        
        return formatted_articles
    
    async def _extract_cnbc_published_date(self, session, url) -> Optional[datetime]:
        """Extract the published date from a CNBC article page. If not found, return None (do not fallback to now)."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                html = await resp.text()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            # Try multiple meta tags
            meta_tags = [
                {'itemprop': 'datePublished'},
                {'property': 'article:published_time'},
                {'name': 'pubdate'},
                {'name': 'date'},
                {'name': 'DC.date.issued'},
            ]
            from dateutil import parser
            for attrs in meta_tags:
                meta = soup.find('meta', attrs)
                if meta and meta.get('content'):
                    try:
                        dt = parser.parse(meta['content'])
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except Exception as e:
                        logger.warning(f"Failed to parse date from meta {attrs}: {meta.get('content')} ({str(e)})")
            # Try <time> tag
            time_tag = soup.find('time')
            if time_tag and time_tag.get('datetime'):
                try:
                    dt = parser.parse(time_tag['datetime'])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception as e:
                    logger.warning(f"Failed to parse date from <time>: {time_tag.get('datetime')} ({str(e)})")
            # Log a snippet of HTML for debugging
            logger.warning(f"Could not extract published date from CNBC article: {url}")
        except Exception as e:
            logger.warning(f"Failed to extract CNBC published date: {str(e)}")
        return None 