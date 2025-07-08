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
import Fundamentals from '@/components/Fundamentals';
import DebugGeminiCalls from '@/components/DebugGeminiCalls';
import { toast } from 'react-hot-toast';

export default function HomePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<StockAnalysis | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [trendingStocks, setTrendingStocks] = useState<TrendingStock[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('sentiment');

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
      {/* Minimal Header with Expandable Search */}
      <header className="bg-white shadow-sm border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-primary-600 p-2 rounded-xl">
                <BarChart3 className="w-8 h-8 text-white" />
              </div>
              </div>
          <div className="flex items-center">
            <button
              className="p-2 rounded-full hover:bg-neutral-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              onClick={() => setShowSearch((prev) => !prev)}
              aria-label="Search"
            >
              <Search className="w-6 h-6 text-neutral-700" />
            </button>
          </div>
        </div>
        {showSearch && (
          <div className="max-w-2xl mx-auto px-4 pb-4">
          <SearchBar
            query={searchQuery}
            onQueryChange={setSearchQuery}
            onSearch={handleSearch}
            isLoading={isSearching}
            placeholder="Enter stock ticker (e.g., AAPL, GOOGL, MSFT)"
          />
        </div>
        )}
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

        {/* Tab Navigation */}
        <div className="mb-8">
          <div className="border-b border-neutral-200 bg-white rounded-xl shadow-sm">
            <nav className="flex space-x-8 px-6" aria-label="Tabs">
              {[
                { id: 'sentiment', name: 'Market Sentiment', icon: '📊' },
                { id: 'news', name: 'Market News', icon: '📰' },
                { id: 'fundamentals', name: 'Fundamentals', icon: '🏛️' },
                { id: 'debug', name: 'Debug', icon: '🐞' }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span>{tab.icon}</span>
                    <span>{tab.name}</span>
                  </span>
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Tab Content */}
        <div className="min-h-screen">
          {activeTab === 'sentiment' && (
            <div className="animate-fade-in">
              <MarketSentiment />
            </div>
          )}

          {activeTab === 'news' && (
            <div className="animate-fade-in">
          <MarketNews />
            </div>
          )}

          {activeTab === 'fundamentals' && (
            <div className="animate-fade-in">
              <Fundamentals />
            </div>
          )}

          {activeTab === 'debug' && (
            <div className="animate-fade-in">
              <DebugGeminiCalls />
            </div>
          )}
        </div>
      </main>
    </div>
  );
} 