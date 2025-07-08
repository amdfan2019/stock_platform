import aiohttp
import asyncio
import feedparser
from bs4 import BeautifulSoup
from newspaper import Article
import re

sources = [
    {"name": "BBC", "rss": "http://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "AP", "rss": "https://feeds.apnews.com/rss/apf-business.rss"},
    {"name": "NPR", "rss": "https://feeds.npr.org/1006/rss.xml"},
    {"name": "Google News (Yahoo)", "rss": "https://news.google.com/rss/search?q=site:finance.yahoo.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News (CNBC)", "rss": "https://news.google.com/rss/search?q=site:cnbc.com&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News (Business)", "rss": "https://news.google.com/rss/search?q=business+stock+market&hl=en-US&gl=US&ceid=US:en"},
    # Direct news listing pages
    {"name": "Yahoo Finance (Direct)", "listing": "https://finance.yahoo.com/news/"},
    {"name": "CNBC (Direct)", "listing": "https://www.cnbc.com/world/?region=world"},
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/rss+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

async def fetch_and_extract(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True, headers=HEADERS, ssl=False) as resp:
            final_url = str(resp.url)
            html = await resp.text()
            # Try newspaper3k
            try:
                art = Article(final_url)
                art.set_html(html)
                art.parse()
                n3k_text = art.text.strip()
            except Exception as e:
                n3k_text = f"newspaper3k error: {e}"
            # Try BeautifulSoup
            try:
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    tag.decompose()
                bs_text = soup.get_text(separator=' ', strip=True)
            except Exception as e:
                bs_text = f"bs4 error: {e}"
            return final_url, n3k_text, bs_text
    except Exception as e:
        return url, f"fetch error: {e}", f"fetch error: {e}"

async def test_source(session, source):
    print(f"\n=== {source['name']} ===")
    # Handle direct listing pages
    if 'listing' in source:
        try:
            # Use minimal headers for Yahoo Finance to avoid header size errors
            custom_headers = HEADERS
            if 'yahoo' in source['name'].lower():
                custom_headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
            else:
                custom_headers = HEADERS
            async with session.get(source['listing'], headers=custom_headers, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
                html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            article_links = []
            if 'yahoo' in source['name'].lower():
                # Yahoo Finance: find news article links
                for a in soup.select('a.js-content-viewer, a[data-test-locator="mega"]'):
                    href = a.get('href')
                    if href and href.startswith('/'):  # relative link
                        href = 'https://finance.yahoo.com' + href
                    if href and '/news/' in href and href not in article_links:
                        article_links.append(href)
                    if len(article_links) >= 2:
                        break
            elif 'cnbc' in source['name'].lower():
                # CNBC: find news article links
                for a in soup.select('a.Card-title, a.LatestNews-headline, a.StoryCard-headline, a[data-analytics="LatestNews-headline"]'):
                    href = a.get('href')
                    if href and href.startswith('/'):
                        href = 'https://www.cnbc.com' + href
                    if href and '/202' in href and href not in article_links:
                        article_links.append(href)
                    if len(article_links) >= 2:
                        break
            if not article_links:
                print("No article links found on listing page.")
                return
            for url in article_links:
                print(f"\nTesting article: {url}")
                final_url, n3k_text, bs_text = await fetch_and_extract(session, url)
                print(f"Final URL: {final_url}")
                print(f"newspaper3k content length: {len(n3k_text) if isinstance(n3k_text, str) else 'error'}")
                print(f"bs4 content length: {len(bs_text) if isinstance(bs_text, str) else 'error'}")
                if isinstance(n3k_text, str) and n3k_text.startswith('newspaper3k error:'):
                    print(n3k_text)
                if isinstance(bs_text, str) and bs_text.startswith('bs4 error:'):
                    print(bs_text)
        except Exception as e:
            print(f"Listing fetch error: {e}")
        return
    try:
        async with session.get(source['rss'], headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
            feed_text = await resp.text()
        feed = feedparser.parse(feed_text)
    except Exception as e:
        print(f"RSS fetch error: {e}")
        return
    if not feed.entries:
        print("No entries found.")
        return
    for entry in feed.entries[:2]:
        url = entry.link
        print(f"\nTesting article: {url}")
        # If Google News, follow redirect
        if "news.google.com/rss/articles/" in url:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True, headers=HEADERS, ssl=False) as resp:
                    real_url = str(resp.url)
                    if real_url != url:
                        print(f"Google News HTTP redirect: {url} -> {real_url}")
                        url = real_url
                    else:
                        html = await resp.text()
                        match = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^;]+;url=([^"\']+)["\']', html, re.IGNORECASE)
                        if match:
                            url = match.group(1)
                            print(f"Google News meta refresh: {entry.link} -> {url}")
                        else:
                            print("Could not resolve real article from Google News.")
            except Exception as e:
                print(f"Google News redirect error: {e}")
                continue
        final_url, n3k_text, bs_text = await fetch_and_extract(session, url)
        print(f"Final URL: {final_url}")
        print(f"newspaper3k content length: {len(n3k_text) if isinstance(n3k_text, str) else 'error'}")
        print(f"bs4 content length: {len(bs_text) if isinstance(bs_text, str) else 'error'}")
        if isinstance(n3k_text, str) and n3k_text.startswith('newspaper3k error:'):
            print(n3k_text)
        if isinstance(bs_text, str) and bs_text.startswith('bs4 error:'):
            print(bs_text)

async def main():
    async with aiohttp.ClientSession() as session:
        for source in sources:
            await test_source(session, source)

if __name__ == "__main__":
    asyncio.run(main()) 