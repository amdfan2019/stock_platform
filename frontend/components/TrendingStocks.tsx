import React from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { TrendingStock } from '@/types';

interface TrendingStocksProps {
  stocks: TrendingStock[];
  onStockClick: (ticker: string) => void;
}

const TrendingStocks: React.FC<TrendingStocksProps> = ({ stocks, onStockClick }) => {
  if (!stocks.length) {
    return null;
  }

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment.toLowerCase()) {
      case 'positive':
        return <TrendingUp className="w-4 h-4 text-success-600" />;
      case 'negative':
        return <TrendingDown className="w-4 h-4 text-danger-600" />;
      default:
        return <Activity className="w-4 h-4 text-neutral-600" />;
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment.toLowerCase()) {
      case 'positive':
        return 'text-success-600 bg-success-50';
      case 'negative':
        return 'text-danger-600 bg-danger-50';
      default:
        return 'text-neutral-600 bg-neutral-50';
    }
  };

  return (
    <div className="mt-12">
      <div className="text-center mb-8">
        <h3 className="text-2xl font-bold text-neutral-900 mb-2">
          Trending Stocks
        </h3>
        <p className="text-neutral-600">
          Popular stocks based on news volume and market activity
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {stocks.map((stock, index) => (
          <button
            key={stock.ticker}
            onClick={() => onStockClick(stock.ticker)}
            className="bg-white rounded-xl p-4 border border-neutral-200 shadow-sm 
                     hover:shadow-md hover:border-primary-300 transition-all duration-200
                     text-left group"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-bold text-neutral-900">
                  #{index + 1}
                </span>
                <span className="text-lg font-bold text-neutral-900 group-hover:text-primary-600">
                  {stock.ticker}
                </span>
              </div>
              {getSentimentIcon(stock.sentiment)}
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="text-sm text-neutral-600">Score:</span>
                <span className="text-sm font-semibold text-neutral-900">
                  {stock.score}
                </span>
              </div>
              
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${getSentimentColor(stock.sentiment)}`}>
                {stock.sentiment}
              </span>
            </div>
          </button>
        ))}
      </div>

      <div className="text-center mt-6">
        <p className="text-sm text-neutral-500">
          Click on any ticker to get AI-powered analysis
        </p>
      </div>
    </div>
  );
};

export default TrendingStocks; 