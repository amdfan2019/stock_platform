'use client';

import React, { useState, useEffect } from 'react';
import { Newspaper, ExternalLink, TrendingUp, Clock, AlertTriangle, TrendingDown } from 'lucide-react';
import { toast } from 'react-hot-toast';

interface MarketNewsArticle {
  title: string;  // This is now the implication title
  original_title: string;  // Original headline for reference
  url: string;
  source: string;
  published_at: string;
  ai_summary: string;
  market_impact: 'High' | 'Medium' | 'Low';
  sentiment: 'bullish' | 'bearish' | 'neutral';
  mentioned_tickers: string[];
  affected_sectors: string[];
  relevance_score: number;  // Keep but don't display
}

interface MarketNewsResponse {
  articles: MarketNewsArticle[];
  total_articles: number;
  hours_lookback: number;
  updated_at: string;
  sources_covered: string[];
  cache_status?: string;
}

const MarketNews: React.FC = () => {
  const [news, setNews] = useState<MarketNewsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    loadMarketNews();
    
    // Auto-refresh every 30 minutes
    const interval = setInterval(loadMarketNews, 30 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const loadMarketNews = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch('http://localhost:8000/api/market-news?hours=24&max_articles=20');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data: MarketNewsResponse = await response.json();
      setNews(data);
      setLastUpdated(new Date());
      
      // Show feedback based on cache status
      if (data.cache_status === 'immediate_cached_response') {
        toast('Refreshed with cached articles, scanning for new updates...', { icon: '🔄' });
      } else if (data.total_articles === 0) {
        toast('No recent market news found', { icon: '📰' });
      } else {
        toast(`Loaded ${data.total_articles} articles`, { icon: '📰' });
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load market news';
      setError(errorMessage);
      toast.error('Failed to load market news');
      console.error('Market news error:', err);
    } finally {
      setLoading(false);
    }
  };



  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return 'text-success-600 bg-success-100';
      case 'bearish': return 'text-danger-600 bg-danger-100';
      case 'neutral': return 'text-neutral-600 bg-neutral-100';
      default: return 'text-neutral-600 bg-neutral-100';
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return <TrendingUp className="w-3 h-3" />;
      case 'bearish': return <TrendingDown className="w-3 h-3" />;
      case 'neutral': return <Clock className="w-3 h-3" />;
      default: return <Clock className="w-3 h-3" />;
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffHours > 24) {
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    } else if (diffHours > 0) {
      return `${diffHours}h ago`;
    } else if (diffMinutes > 0) {
      return `${diffMinutes}m ago`;
    } else {
      return 'Just now';
    }
  };

  const cleanSummary = (summary: string) => {
    if (!summary) return '';
    
    // Remove HTML tags and clean up the summary  
    let cleaned = summary
      .replace(/<[^>]*>/g, '')  // Remove HTML tags
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&nbsp;/g, ' ')  // Remove non-breaking spaces
      .replace(/&[a-zA-Z0-9#]+;/g, '')  // Remove other HTML entities
      .trim();
    
    // Remove duplicate text (sometimes RSS feeds duplicate content)
    const sentences = cleaned.split(/[.!?]+/).filter(s => s.trim().length > 0);
    const uniqueSentences = Array.from(new Set(sentences));
    
    return uniqueSentences.join('. ').trim();
  };

  if (loading && !news) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
        <div className="animate-pulse">
          <div className="flex items-center space-x-3 mb-4">
            <div className="bg-neutral-200 w-6 h-6 rounded"></div>
            <div className="bg-neutral-200 h-6 w-32 rounded"></div>
          </div>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <div className="bg-neutral-200 h-4 w-full rounded"></div>
                <div className="bg-neutral-200 h-3 w-3/4 rounded"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
        <div className="text-center py-8">
          <AlertTriangle className="w-12 h-12 text-danger-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">
            Failed to Load Market News
          </h3>
          <p className="text-neutral-600 mb-4">{error}</p>
          <button
            onClick={loadMarketNews}
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Newspaper className="w-4 h-4 mr-2" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-200">
      {/* Header */}
      <div className="p-6 border-b border-neutral-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-primary-100 p-2 rounded-lg">
              <Newspaper className="w-6 h-6 text-primary-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-neutral-900">
                Market News
              </h2>
              <p className="text-sm text-neutral-600">
                Latest financial news and market developments
              </p>
            </div>
          </div>
          
          <div className="text-right">
            <div className="text-sm text-neutral-500">
              {news?.total_articles || 0} articles
            </div>
            {lastUpdated && (
              <div className="text-xs text-neutral-400">
                Updated {formatTimeAgo(lastUpdated.toISOString())}
              </div>
            )}
          </div>
        </div>
        

      </div>

      {/* News Articles */}
      <div className="divide-y divide-neutral-200">
        {news?.articles?.length ? (
          news.articles.map((article, index) => (
            <div key={index} className="p-6 hover:bg-neutral-50 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-base font-semibold text-neutral-900 mb-2 leading-snug">
                    {article.title}
                  </h3>
                  
                  {article.ai_summary && (
                    <p className="text-sm text-neutral-600 mb-3 leading-relaxed">
                      {cleanSummary(article.ai_summary)}
                    </p>
                  )}
                  
                  <div className="flex items-center space-x-4 text-xs text-neutral-500">
                    <span>{formatTimeAgo(article.published_at)}</span>
                  </div>
                </div>
                
                <div className="ml-4 flex flex-col items-end space-y-2">
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
                  >
                    <ExternalLink className="w-4 h-4 mr-1" />
                    Read
                  </a>
                  
                  <div className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded-md ${getSentimentColor(article.sentiment)}`}>
                    {getSentimentIcon(article.sentiment)}
                    <span className="ml-1 capitalize">{article.sentiment}</span>
                  </div>
                </div>
              </div>
              
              {/* Mentioned Tickers & Sectors */}
              {(article.mentioned_tickers?.length > 0 || article.affected_sectors?.length > 0) && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {article.mentioned_tickers?.map((ticker) => (
                    <span
                      key={ticker}
                      className="inline-flex items-center px-2 py-1 bg-primary-100 text-primary-800 text-xs font-medium rounded-md"
                    >
                      {ticker}
                    </span>
                  ))}
                  {article.affected_sectors?.map((sector) => (
                    <span
                      key={sector}
                      className="inline-flex items-center px-2 py-1 bg-secondary-100 text-secondary-800 text-xs rounded-md"
                    >
                      {sector}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="p-8 text-center">
            <Newspaper className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-neutral-900 mb-2">
              No Recent News
            </h3>
            <p className="text-neutral-600">
              No market news found in the last {news?.hours_lookback || 24} hours.
            </p>
            <button
              onClick={loadMarketNews}
              className="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
            >
              <Newspaper className="w-4 h-4 mr-2" />
              Refresh News
            </button>
          </div>
        )}
      </div>
      
      {/* Refresh Button */}
      {news?.articles && news.articles.length > 0 && (
        <div className="p-4 border-t border-neutral-200 text-center">
          <button
            onClick={loadMarketNews}
            disabled={loading}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-neutral-600 bg-neutral-50 rounded-lg hover:bg-neutral-100 transition-colors disabled:opacity-50"
          >
            <Newspaper className="w-4 h-4 mr-2" />
            {loading ? 'Refreshing...' : 'Refresh News'}
          </button>
        </div>
      )}
    </div>
  );
};

export default MarketNews; 