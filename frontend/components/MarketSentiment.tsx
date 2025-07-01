'use client';

import React, { useState, useEffect } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, Activity, AlertCircle, BarChart3, Database } from 'lucide-react';

interface MarketSentimentData {
  sentiment_score: number;
  sentiment_label: string;
  confidence_level: number;
  trend_analysis: string;
  historical_context: string;
  market_outlook: string;
  analysis_date: string;
}

interface CurrentIndicators {
  sp500: { value: number; change_pct: number; data_source: string; };
  dow: { value: number; change_pct: number; data_source: string; };
  nasdaq: { value: number; change_pct: number; data_source: string; };
  vix: { value: number; change_pct: number; data_source: string; };
  treasury_10y: { value: number; change_pct: number; data_source: string; };
  dxy: { value: number; change_pct: number; data_source: string; };
  fear_greed_index?: { value: number; label: string; source: string; timestamp: string; };
  news_sentiment?: { overall_sentiment: number; sentiment_label: string; sources_count: number; confidence: number; };
}

interface MarketSentimentResponse {
  sentiment_analysis: MarketSentimentData | null;
  current_indicators: CurrentIndicators;
  data_timestamp: string;
  market_session: string;
}

const MarketSentiment: React.FC = () => {
  const [sentimentData, setSentimentData] = useState<MarketSentimentData | null>(null);
  const [indicators, setIndicators] = useState<CurrentIndicators | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [collectingData, setCollectingData] = useState(false);
  const [analyzingData, setAnalyzingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [marketSession, setMarketSession] = useState<string>('closed');
  const [dataTimestamp, setDataTimestamp] = useState<string>('');
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);

  const fetchMarketSentiment = async (forceRefresh = false) => {
    try {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const endpoint = forceRefresh ? '/api/market-sentiment/refresh' : '/api/market-sentiment';
      const method = forceRefresh ? 'POST' : 'GET';

      console.log('Fetching market sentiment:', `http://localhost:8000${endpoint}`);
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
      });
      console.log('Response status:', response.status, response.statusText);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: MarketSentimentResponse = await response.json();

      setSentimentData(data.sentiment_analysis);
      setIndicators(data.current_indicators);
      setMarketSession(data.market_session);
      setDataTimestamp(data.data_timestamp);
      setLastRefresh(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      console.error('Error fetching market sentiment:', err);
      setError(err instanceof Error ? err.message : 'Failed to connect to sentiment service');
      setSentimentData(null);
      setIndicators(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const collectFreshMarketData = async () => {
    setCollectingData(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/market-data/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to collect data: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Fresh data collected:', result);
      
      // Automatically trigger sentiment analysis after collecting fresh data
      await generateSentimentAnalysis();
      
      // Refresh the main data
      await fetchMarketSentiment();
      
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Error collecting fresh data:', err);
      setError(`Failed to collect fresh data: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setCollectingData(false);
    }
  };

  const generateSentimentAnalysis = async () => {
    setAnalyzingData(true);
    
    try {
      const response = await fetch('http://localhost:8000/api/sentiment-analysis/generate?days_back=30', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to generate analysis: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Fresh analysis generated:', result);
      
      return result;
    } catch (err) {
      console.error('Error generating analysis:', err);
      throw err;
    } finally {
      setAnalyzingData(false);
    }
  };

  useEffect(() => {
    fetchMarketSentiment();
    
    // Auto-refresh every 30 minutes
    const interval = setInterval(() => {
      fetchMarketSentiment();
    }, 30 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const getSentimentColor = (score: number): string => {
    if (score >= 7.5) return 'text-green-600';
    if (score >= 6.5) return 'text-green-500';
    if (score >= 5.5) return 'text-blue-500';
    if (score >= 4.5) return 'text-gray-500';
    if (score >= 3.5) return 'text-orange-500';
    if (score >= 2.5) return 'text-red-500';
    return 'text-red-600';
  };

  const getSentimentBgColor = (score: number): string => {
    if (score >= 7.5) return 'bg-green-100 border-green-200';
    if (score >= 6.5) return 'bg-green-50 border-green-100';
    if (score >= 5.5) return 'bg-blue-50 border-blue-100';
    if (score >= 4.5) return 'bg-gray-50 border-gray-100';
    if (score >= 3.5) return 'bg-orange-50 border-orange-100';
    if (score >= 2.5) return 'bg-red-50 border-red-100';
    return 'bg-red-100 border-red-200';
  };

  const formatChange = (change: number): string => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}%`;
  };

  const getChangeColor = (change: number): string => {
    return change >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const renderScoreBar = (score: number, maxScore: number = 10) => {
    const percentage = (score / maxScore) * 100;
    return (
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${
            score >= 7.5 ? 'bg-green-500' :
            score >= 6.5 ? 'bg-green-400' :
            score >= 5.5 ? 'bg-blue-400' :
            score >= 4.5 ? 'bg-gray-400' :
            score >= 3.5 ? 'bg-orange-400' :
            score >= 2.5 ? 'bg-red-400' : 'bg-red-500'
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    );
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Activity className="h-5 w-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-gray-900">Market Sentiment</h2>
          </div>
          <div className="animate-spin">
            <RefreshCw className="h-4 w-4 text-gray-400" />
          </div>
        </div>
        <div className="space-y-4">
          <div className="animate-pulse bg-gray-200 h-16 rounded"></div>
          <div className="animate-pulse bg-gray-200 h-12 rounded"></div>
          <div className="animate-pulse bg-gray-200 h-12 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Activity className="h-5 w-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-gray-900">Market Sentiment</h2>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => collectFreshMarketData()}
              disabled={collectingData || analyzingData}
              className="flex items-center space-x-1 px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 text-sm"
            >
              <Database className={`h-4 w-4 ${collectingData || analyzingData ? 'animate-spin' : ''}`} />
              <span>{analyzingData ? 'Analyzing...' : 'Collect Live Data & Analyze'}</span>
            </button>
            <button
              onClick={() => fetchMarketSentiment()}
              disabled={refreshing}
              className="flex items-center space-x-1 text-blue-500 hover:text-blue-600 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              <span className="text-sm">Retry</span>
            </button>
          </div>
        </div>
        <div className="flex items-center space-x-2 text-red-600">
          <AlertCircle className="h-5 w-5" />
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!sentimentData || !indicators || !indicators.sp500) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Activity className="h-5 w-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-gray-900">Market Sentiment</h2>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => collectFreshMarketData()}
              disabled={collectingData || analyzingData}
              className="flex items-center space-x-1 px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 text-sm"
            >
              <Database className={`h-4 w-4 ${collectingData || analyzingData ? 'animate-spin' : ''}`} />
              <span>{analyzingData ? 'Analyzing...' : 'Collect Live Data & Analyze'}</span>
            </button>
            <button
              onClick={() => fetchMarketSentiment()}
              disabled={refreshing}
              className="flex items-center space-x-1 text-blue-500 hover:text-blue-600 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              <span className="text-sm">Retry</span>
            </button>
          </div>
        </div>
        <p className="text-gray-500">No sentiment data available. Click "Collect Live Data & Analyze" to gather market data.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-2">
          <Activity className="h-5 w-5 text-blue-500" />
          <h2 className="text-lg font-semibold text-gray-900">Market Sentiment</h2>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-xs text-gray-500">
            <div className="capitalize">{marketSession} Session</div>
            {lastRefresh && <div>Last updated: {lastRefresh}</div>}
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => collectFreshMarketData()}
              disabled={collectingData || analyzingData}
              className="flex items-center space-x-1 px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 text-sm"
            >
              <Database className={`h-4 w-4 ${collectingData || analyzingData ? 'animate-spin' : ''}`} />
              <span>{analyzingData ? 'Analyzing...' : 'Collect Live Data & Analyze'}</span>
            </button>
            <button
              onClick={() => fetchMarketSentiment()}
              disabled={refreshing}
              className="flex items-center space-x-1 text-blue-500 hover:text-blue-600 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              <span className="text-sm">Retry</span>
            </button>
          </div>
        </div>
      </div>

      {/* Overall Sentiment Score */}
      <div className={`rounded-lg border-2 p-4 mb-6 ${getSentimentBgColor(sentimentData.sentiment_score)}`}>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-700">Overall Sentiment</h3>
          <span className={`text-sm font-medium ${getSentimentColor(sentimentData.sentiment_score)}`}>
            {sentimentData.sentiment_label}
          </span>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex-1">
            {renderScoreBar(sentimentData.sentiment_score)}
          </div>
          <div className={`text-2xl font-bold ${getSentimentColor(sentimentData.sentiment_score)}`}>
            {sentimentData.sentiment_score.toFixed(1)}/10
          </div>
        </div>

      </div>

      {/* Market Indicators */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        {/* S&P 500 */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-600">S&P 500</span>
            {indicators.sp500.change_pct >= 0 ? (
              <TrendingUp className="w-4 h-4 text-green-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-500" />
            )}
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-gray-900">
              {indicators.sp500.value.toFixed(2)}
            </div>
            <div className={`text-sm font-medium ${
              indicators.sp500.change_pct >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {indicators.sp500.change_pct >= 0 ? '+' : ''}{indicators.sp500.change_pct.toFixed(2)}% (5d)
            </div>

          </div>
        </div>



        {/* NASDAQ */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-600">NASDAQ</span>
            {indicators.nasdaq.change_pct >= 0 ? (
              <TrendingUp className="w-4 h-4 text-green-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-500" />
            )}
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-gray-900">
              {indicators.nasdaq.value.toFixed(2)}
            </div>
            <div className={`text-sm font-medium ${
              indicators.nasdaq.change_pct >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {indicators.nasdaq.change_pct >= 0 ? '+' : ''}{indicators.nasdaq.change_pct.toFixed(2)}% (5d)
            </div>

          </div>
        </div>

        {/* VIX */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-600">VIX (Volatility)</span>
            {indicators.vix.change_pct >= 0 ? (
              <TrendingUp className="w-4 h-4 text-red-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-green-500" />
            )}
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-gray-900">
              {indicators.vix.value.toFixed(2)}
            </div>
            <div className={`text-sm font-medium ${
              indicators.vix.change_pct >= 0 ? 'text-red-600' : 'text-green-600'
            }`}>
              {indicators.vix.change_pct >= 0 ? '+' : ''}{indicators.vix.change_pct.toFixed(2)}% (5d)
            </div>

          </div>
        </div>

        {/* 10Y Treasury */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-600">10Y Treasury</span>
            {indicators.treasury_10y.change_pct >= 0 ? (
              <TrendingUp className="w-4 h-4 text-red-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-green-500" />
            )}
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-gray-900">
              {indicators.treasury_10y.value.toFixed(3)}%
            </div>
            <div className={`text-sm font-medium ${
              indicators.treasury_10y.change_pct >= 0 ? 'text-red-600' : 'text-green-600'
            }`}>
              {indicators.treasury_10y.change_pct >= 0 ? '+' : ''}{indicators.treasury_10y.change_pct.toFixed(2)}% (5d)
            </div>

          </div>
        </div>

        {/* Dollar Index */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-600">Dollar Index</span>
            {indicators.dxy.change_pct >= 0 ? (
              <TrendingUp className="w-4 h-4 text-green-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-500" />
            )}
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-gray-900">
              {indicators.dxy.value.toFixed(3)}
            </div>
            <div className={`text-sm font-medium ${
              indicators.dxy.change_pct >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {indicators.dxy.change_pct >= 0 ? '+' : ''}{indicators.dxy.change_pct.toFixed(2)}% (5d)
            </div>

          </div>
        </div>

        {/* Fear & Greed Index */}
        {indicators.fear_greed_index && (
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">Fear & Greed Index</span>
              {indicators.fear_greed_index.value >= 50 ? (
                <TrendingUp className="w-4 h-4 text-green-500" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-500" />
              )}
            </div>
            <div className="mt-2">
              <div className="text-2xl font-bold text-gray-900">
                {indicators.fear_greed_index.value.toFixed(0)}
              </div>
              <div className={`text-sm font-medium ${
                indicators.fear_greed_index.value >= 50 ? 'text-green-600' : 'text-red-600'
              }`}>
                {indicators.fear_greed_index.label}
              </div>

            </div>
          </div>
        )}

        {/* News Sentiment */}
        {indicators.news_sentiment && (
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">News Sentiment</span>
              {indicators.news_sentiment.overall_sentiment >= 0 ? (
                <TrendingUp className="w-4 h-4 text-green-500" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-500" />
              )}
            </div>
            <div className="mt-2">
              <div className="text-2xl font-bold text-gray-900">
                {(indicators.news_sentiment.overall_sentiment * 100).toFixed(0)}%
              </div>
              <div className={`text-sm font-medium ${
                indicators.news_sentiment.overall_sentiment >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {indicators.news_sentiment.sentiment_label}
              </div>
              <div className="text-xs mt-1 text-gray-500">
                {indicators.news_sentiment.sources_count} sources
              </div>
            </div>
          </div>
        )}
      </div>

      {/* AI Sentiment Analysis - Key Feature */}
      {sentimentData && (
        <div className="space-y-6 border-t border-gray-200 pt-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">AI Analysis</h3>
          
          {/* Trend Analysis with Historical Context */}
          <div className="bg-gradient-to-r from-gray-50 to-neutral-50 p-6 rounded-xl border border-gray-200">
            <h4 className="text-lg font-semibold text-gray-800 mb-4">
              Trends and Sentiment
            </h4>
            <p className="text-base leading-relaxed text-gray-700">
              {sentimentData.historical_context ? `${sentimentData.trend_analysis} ${sentimentData.historical_context}` : sentimentData.trend_analysis}
            </p>
          </div>
          
          {/* Market Outlook */}
          <div className="bg-gradient-to-r from-gray-50 to-neutral-50 p-6 rounded-xl border border-gray-200">
            <h4 className="text-lg font-semibold text-gray-800 mb-4">
              Outlook
            </h4>
            <p className="text-base leading-relaxed text-gray-700">{sentimentData.market_outlook}</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default MarketSentiment; 