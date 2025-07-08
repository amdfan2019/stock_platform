'use client';

import React, { useState, useEffect } from 'react';
import { Newspaper, ExternalLink, TrendingUp, Clock, AlertTriangle, TrendingDown, Minus } from 'lucide-react';
import { toast } from 'react-hot-toast';

interface MarketNewsArticle {
  title: string;  // Original title
  brief_headline: string;  // LLM-generated brief headline
  bullet_points: string[];  // Key insights as bullet points
  market_signal: 'bullish' | 'bearish' | 'neutral';
  confidence: number;  // 0-1 confidence score
  mentioned_tickers: string[];
  key_theme: string;  // Type of news (earnings, fed_policy, etc)
  url: string;
  source: string;
  published_at: string;
  content_length: number;
  has_full_content: boolean;
}

interface MarketNewsResponse {
  articles: MarketNewsArticle[];
  total_articles: number;
  hours_lookback: number;
  updated_at: string;
  sources_covered: string[];
  cache_status: string;
  news_summary?: string;
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
      setError(null);
      
      const response = await fetch('http://localhost:8000/api/market-news?hours=12&max_articles=15');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data: MarketNewsResponse = await response.json();
      setNews(data);
      setLastUpdated(new Date());
      
      if (data.total_articles === 0) {
        toast('No recent market news found', { icon: '📰' });
      } else {
        toast(`Loaded ${data.total_articles} market insights`, { icon: '🎯' });
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

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'bullish': return 'text-green-700 bg-green-100 border-green-200';
      case 'bearish': return 'text-red-700 bg-red-100 border-red-200';
      case 'neutral': return 'text-gray-700 bg-gray-100 border-gray-200';
      default: return 'text-gray-700 bg-gray-100 border-gray-200';
    }
  };

  const getSignalIcon = (signal: string) => {
    switch (signal) {
      case 'bullish': return <TrendingUp className="w-4 h-4" />;
      case 'bearish': return <TrendingDown className="w-4 h-4" />;
      case 'neutral': return <Minus className="w-4 h-4" />;
      default: return <Minus className="w-4 h-4" />;
    }
  };

  const getThemeColor = (theme: string) => {
    const themes: Record<string, string> = {
      'earnings': 'bg-blue-100 text-blue-800',
      'fed_policy': 'bg-purple-100 text-purple-800',
      'economic_data': 'bg-orange-100 text-orange-800',
      'geopolitical': 'bg-red-100 text-red-800',
      'sector_news': 'bg-green-100 text-green-800',
      'other': 'bg-gray-100 text-gray-800'
    };
    return themes[theme] || themes['other'];
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

  const formatConfidence = (confidence: number) => {
    return `${Math.round(confidence * 100)}%`;
  };

  if (loading && !news) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
        <div className="animate-pulse">
          <div className="flex items-center space-x-3 mb-6">
            <div className="bg-neutral-200 w-8 h-8 rounded-lg"></div>
            <div className="bg-neutral-200 h-6 w-40 rounded"></div>
          </div>
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-3">
                <div className="bg-neutral-200 h-5 w-full rounded"></div>
                <div className="space-y-2">
                  <div className="bg-neutral-200 h-3 w-full rounded"></div>
                  <div className="bg-neutral-200 h-3 w-5/6 rounded"></div>
                  <div className="bg-neutral-200 h-3 w-4/6 rounded"></div>
                </div>
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
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">
            Failed to Load Market News
          </h3>
          <p className="text-neutral-600 mb-4">{error}</p>
          <button
            onClick={loadMarketNews}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Newspaper className="w-4 h-4 mr-2" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-200 relative">
      {/* Loading overlay */}
      {loading && news && (
        <div className="absolute inset-0 bg-white bg-opacity-60 flex items-center justify-center z-10">
          <svg className="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
          </svg>
        </div>
      )}
      {/* Header */}
      <div className="p-6 border-b border-neutral-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-blue-100 p-2 rounded-lg">
              <Newspaper className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-neutral-900 uppercase">
                WHAT'S GOING ON?
              </h2>
            </div>
          </div>
            </div>
        {/* News Summary */}
        {news?.news_summary ? (
          <div className="mt-4 mb-2 text-base text-neutral-900 font-medium leading-relaxed">
            {news.news_summary}
              </div>
        ) : loading && news ? (
          <div className="mt-4 mb-2 animate-pulse">
            <div className="h-5 w-5/6 bg-neutral-200 rounded mb-2"></div>
            <div className="h-5 w-4/6 bg-neutral-200 rounded"></div>
          </div>
        ) : null}
      </div>

      {/* News Articles */}
      <div className="divide-y divide-neutral-200">
        {news?.articles?.length ? (
          news.articles.map((article, index) => (
            <div key={index} className="p-6 hover:bg-neutral-50 transition-colors">
              {/* Article Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1 min-w-0">
                  {/* Brief Headline */}
                  <h3 className="text-lg font-semibold text-neutral-900 mb-2 leading-tight">
                    {article.brief_headline}
                  </h3>
                  
                  {/* Meta info */}
                  <div className="flex items-center space-x-4 text-sm text-neutral-500 mb-3">
                    <span>{formatTimeAgo(article.published_at)}</span>
                    {!article.has_full_content && (
                      <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded-full">
                        Headline Only
                      </span>
                    )}
                  </div>
                </div>
                
                {/* Market Signal */}
                <div className="ml-4 flex flex-col items-end space-y-2">
                  <div className={`inline-flex items-center px-3 py-1.5 border rounded-lg ${getSignalColor(article.market_signal)}`}>
                    {getSignalIcon(article.market_signal)}
                    <span className="ml-2 font-medium capitalize">{article.market_signal}</span>
                  </div>
                </div>
              </div>
              
              {/* Key Insights */}
              {article.bullet_points && article.bullet_points.length > 0 && (
                <div className="mb-4">
                  <ul className="space-y-2">
                    {article.bullet_points.map((point, idx) => (
                      <li key={idx} className="flex items-start space-x-2">
                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full mt-2 flex-shrink-0"></div>
                        <span className="text-sm text-neutral-700 leading-relaxed">{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Tags and Actions */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {/* Theme Tag */}
                  <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded-md ${getThemeColor(article.key_theme)}`}>
                    {article.key_theme.replace('_', ' ')}
                  </span>
                  
                  {/* Ticker Tags */}
                  {article.mentioned_tickers?.slice(0, 3).map((ticker) => (
                    <span
                      key={ticker}
                      className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded-md"
                    >
                      {ticker}
                    </span>
                  ))}
                  
                  {article.mentioned_tickers?.length > 3 && (
                    <span className="text-xs text-neutral-500">
                      +{article.mentioned_tickers.length - 3} more
                    </span>
                  )}
                </div>
                
                {/* Read Article Button */}
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
                >
                  <ExternalLink className="w-4 h-4 mr-1" />
                  Read Full Article
                </a>
              </div>
            </div>
          ))
        ) : (
          <div className="p-8 text-center">
            <Newspaper className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-neutral-900 mb-2">
              No Recent News
            </h3>
            <p className="text-neutral-600">
              No market news found in the last {news?.hours_lookback || 12} hours.
            </p>
            <button
              onClick={loadMarketNews}
              className="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
            >
              <Newspaper className="w-4 h-4 mr-2" />
              Refresh
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
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      )}
    </div>
  );
};

export default MarketNews; 