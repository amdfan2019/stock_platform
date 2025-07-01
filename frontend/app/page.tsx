'use client';

import React, { useState, useEffect } from 'react';
import { Search, TrendingUp, TrendingDown, AlertCircle, BarChart3, Clock, DollarSign } from 'lucide-react';
import { stockAPI } from '@/lib/api';
import { StockAnalysis, TrendingStock } from '@/types';
import StockCard from '@/components/StockCard';
import SearchBar from '@/components/SearchBar';
import TrendingStocks from '@/components/TrendingStocks';
import MarketNews from '@/components/MarketNews';
import MarketSentiment from '@/components/MarketSentiment';
import { toast } from 'react-hot-toast';

export default function HomePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<StockAnalysis | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [trendingStocks, setTrendingStocks] = useState<TrendingStock[]>([]);

  // Load trending stocks on component mount
  useEffect(() => {
    loadTrendingStocks();
  }, []);

  const loadTrendingStocks = async () => {
    try {
      const data = await stockAPI.getTrending();
      setTrendingStocks(data.trending);
    } catch (error) {
      console.error('Error loading trending stocks:', error);
    }
  };

  const handleSearch = async (ticker: string) => {
    if (!ticker.trim()) {
      toast.error('Please enter a stock ticker');
      return;
    }

    setIsSearching(true);
    setSearchError(null);
    
    try {
      const data = await stockAPI.searchStock(ticker);
      setSearchResults(data);
      toast.success(`Found analysis for ${data.ticker}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to analyze stock';
      setSearchError(errorMessage);
      setSearchResults(null);
      toast.error(errorMessage);
    } finally {
      setIsSearching(false);
    }
  };

  const handleTrendingClick = (ticker: string) => {
    setSearchQuery(ticker);
    handleSearch(ticker);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-neutral-50 to-neutral-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-primary-600 p-2 rounded-xl">
                <BarChart3 className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-neutral-900">
                  Stock Analysis Platform
                </h1>
                <p className="text-sm text-neutral-600">
                  AI-powered investment insights for long-term investors
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2 text-sm text-neutral-600">
                <Clock className="w-4 h-4" />
                <span>Hourly updates</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search Section */}
        <div className="mb-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-neutral-900 mb-4">
              Smart Stock Analysis & Market Intelligence
            </h2>
            <p className="text-lg text-neutral-600 max-w-2xl mx-auto">
              Understand market dynamics through AI-processed news, valuation analysis, 
              and technical indicators for informed investment decisions.
            </p>
          </div>

          <SearchBar
            query={searchQuery}
            onQueryChange={setSearchQuery}
            onSearch={handleSearch}
            isLoading={isSearching}
            placeholder="Enter stock ticker (e.g., AAPL, GOOGL, MSFT)"
          />
        </div>

        {/* Search Results */}
        {searchResults && (
          <div className="mb-8 animate-fade-in">
            <h3 className="text-xl font-semibold text-neutral-900 mb-4">
              Analysis Results
            </h3>
            <StockCard stock={searchResults} />
          </div>
        )}

        {/* Search Error */}
        {searchError && (
          <div className="mb-8 animate-fade-in">
            <div className="bg-danger-50 border border-danger-200 rounded-xl p-4 flex items-center space-x-3">
              <AlertCircle className="w-5 h-5 text-danger-600 flex-shrink-0" />
              <div>
                <h4 className="font-medium text-danger-800">Analysis Failed</h4>
                <p className="text-danger-700">{searchError}</p>
              </div>
            </div>
          </div>
        )}

        {/* Market News - Full Width */}
        <div className="mb-12">
          <MarketNews />
        </div>
        
        {/* Market Sentiment - Below News */}
        <div className="mb-12">
          <MarketSentiment />
        </div>

        {/* Features Grid - Only show when no search results */}
        {!searchResults && !searchError && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
              <div className="bg-success-100 w-12 h-12 rounded-lg flex items-center justify-center mb-4">
                <TrendingUp className="w-6 h-6 text-success-600" />
              </div>
              <h3 className="text-lg font-semibold text-neutral-900 mb-2">
                Market Intelligence
              </h3>
              <p className="text-neutral-600">
                Stay informed with AI-processed market news ranked by relevance 
                and impact on investment decisions.
              </p>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
              <div className="bg-primary-100 w-12 h-12 rounded-lg flex items-center justify-center mb-4">
                <BarChart3 className="w-6 h-6 text-primary-600" />
              </div>
              <h3 className="text-lg font-semibold text-neutral-900 mb-2">
                Technical Analysis
              </h3>
              <p className="text-neutral-600">
                Advanced technical indicators including RSI, MACD, moving averages, 
                and custom momentum scores.
              </p>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
              <div className="bg-warning-100 w-12 h-12 rounded-lg flex items-center justify-center mb-4">
                <DollarSign className="w-6 h-6 text-warning-600" />
              </div>
              <h3 className="text-lg font-semibold text-neutral-900 mb-2">
                Value Investing
              </h3>
              <p className="text-neutral-600">
                Focus on intrinsic value, margin of safety, and long-term 
                fundamentals for sustainable investing.
              </p>
            </div>
          </div>
        )}

        {/* Trending Stocks */}
        <TrendingStocks
          stocks={trendingStocks}
          onStockClick={handleTrendingClick}
        />

        {/* Footer Info */}
        <div className="mt-12 text-center">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
            <h4 className="text-lg font-semibold text-neutral-900 mb-2">
              How It Works
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4">
              <div className="text-center">
                <div className="bg-primary-600 text-white w-8 h-8 rounded-full flex items-center justify-center mx-auto mb-2 text-sm font-bold">
                  1
                </div>
                <p className="text-sm text-neutral-600">Enter stock ticker</p>
              </div>
              <div className="text-center">
                <div className="bg-primary-600 text-white w-8 h-8 rounded-full flex items-center justify-center mx-auto mb-2 text-sm font-bold">
                  2
                </div>
                <p className="text-sm text-neutral-600">AI analyzes fundamentals</p>
              </div>
              <div className="text-center">
                <div className="bg-primary-600 text-white w-8 h-8 rounded-full flex items-center justify-center mx-auto mb-2 text-sm font-bold">
                  3
                </div>
                <p className="text-sm text-neutral-600">Reviews news sentiment</p>
              </div>
              <div className="text-center">
                <div className="bg-primary-600 text-white w-8 h-8 rounded-full flex items-center justify-center mx-auto mb-2 text-sm font-bold">
                  4
                </div>
                <p className="text-sm text-neutral-600">Generates recommendation</p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
} 