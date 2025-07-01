#!/usr/bin/env python3
"""
Test script to verify news collection works without NewsAPI
"""

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.news_collector import NewsCollector

async def test_news_collection():
    """Test news collection for a sample stock"""
    
    print("🧪 Testing News Collection (without NewsAPI)")
    print("=" * 50)
    
    collector = NewsCollector()
    
    # Test with a popular stock
    ticker = "AAPL"
    print(f"📰 Collecting news for {ticker}...")
    
    try:
        articles = await collector.collect_stock_news(ticker, hours_lookback=24)
        
        print(f"\n✅ Successfully collected {len(articles)} articles")
        print("\n📊 News Sources Summary:")
        
        sources = {}
        for article in articles:
            source = article.get("source", "Unknown")
            sources[source] = sources.get(source, 0) + 1
        
        for source, count in sources.items():
            print(f"  • {source}: {count} articles")
        
        print("\n📄 Sample Articles:")
        print("-" * 30)
        
        for i, article in enumerate(articles[:5]):  # Show first 5
            print(f"\n{i+1}. {article.get('title', 'No title')}")
            print(f"   Source: {article.get('source', 'Unknown')}")
            print(f"   Published: {article.get('published_at', 'Unknown')}")
            if article.get('sentiment_label'):
                print(f"   Sentiment: {article.get('sentiment_label')} ({article.get('sentiment_score', 0):.2f})")
        
        # Test sentiment calculation
        print(f"\n🎯 Testing sentiment analysis...")
        sentiment_signal = await collector.calculate_news_sentiment_signal(articles)
        
        print(f"📈 Overall Sentiment Score: {sentiment_signal.get('overall_sentiment', 0):.2f}")
        print(f"🔢 Total Articles: {sentiment_signal.get('article_count', 0)}")
        print(f"⚡ High Impact Articles: {sentiment_signal.get('high_impact_count', 0)}")
        print(f"📊 Confidence: {sentiment_signal.get('confidence', 0):.2f}")
        
        print(f"\n🎉 News collection test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during news collection: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Set up environment
    os.environ.setdefault('GOOGLE_API_KEY', 'AIzaSyCb_UCb-qQUXvJs6oac2OvyvsdqC_09sOg')
    os.environ.setdefault('ALPHA_VANTAGE_API_KEY', 'U9NQ5J3D0NR5QTHD')
    os.environ.setdefault('NEWS_API_KEY', '')
    
    asyncio.run(test_news_collection()) 