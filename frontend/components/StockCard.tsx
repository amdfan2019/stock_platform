import React from 'react';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Shield, Clock, DollarSign } from 'lucide-react';
import { StockAnalysis } from '@/types';
import { formatDistanceToNow } from 'date-fns';

interface StockCardProps {
  stock: StockAnalysis;
}

const StockCard: React.FC<StockCardProps> = ({ stock }) => {
  const recommendation = stock.recommendation;
  
  if (!recommendation) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-neutral-200 p-6">
        <div className="text-center py-8">
          <AlertTriangle className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-600">No Recommendation Available</h3>
          <p className="text-neutral-500">Unable to generate analysis for this stock.</p>
        </div>
      </div>
    );
  }

  const getActionColor = (action: string) => {
    switch (action) {
      case 'BUY':
        return {
          bg: 'bg-success-50',
          border: 'border-success-200',
          text: 'text-success-700',
          icon: TrendingUp,
          badge: 'badge-buy'
        };
      case 'SELL':
        return {
          bg: 'bg-danger-50',
          border: 'border-danger-200',
          text: 'text-danger-700',
          icon: TrendingDown,
          badge: 'badge-sell'
        };
      default: // HOLD
        return {
          bg: 'bg-warning-50',
          border: 'border-warning-200',
          text: 'text-warning-700',
          icon: Minus,
          badge: 'badge-hold'
        };
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low':
        return 'text-success-600';
      case 'high':
        return 'text-danger-600';
      default:
        return 'text-warning-600';
    }
  };

  const formatPrice = (price?: number) => {
    if (!price) return 'N/A';
    return `$${price.toFixed(2)}`;
  };

  const formatPercentage = (value?: number) => {
    if (value === undefined || value === null) return 'N/A';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${(value * 100).toFixed(1)}%`;
  };

  const actionConfig = getActionColor(recommendation.action);
  const ActionIcon = actionConfig.icon;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-200 overflow-hidden">
      {/* Header */}
      <div className={`p-6 ${actionConfig.bg} ${actionConfig.border} border-b`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-bold text-neutral-900">{stock.ticker}</h2>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${actionConfig.badge}`}>
                <ActionIcon className="w-4 h-4 inline mr-1" />
                {recommendation.action}
              </span>
            </div>
          </div>
          
          <div className="text-right">
            <div className="text-2xl font-bold text-neutral-900">
              {Math.round(recommendation.confidence_score * 100)}%
            </div>
            <div className="text-sm text-neutral-600">Confidence</div>
          </div>
        </div>
        
        <div className="mt-4">
          <h3 className="text-lg font-medium text-neutral-800 mb-1">{stock.company_name}</h3>
          <p className={`text-sm ${actionConfig.text} font-medium`}>
            {recommendation.reasoning}
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Price Ranges */}
          <div className="space-y-4">
            <h4 className="font-semibold text-neutral-900 flex items-center">
              <DollarSign className="w-4 h-4 mr-2 text-neutral-600" />
              Price Ranges
            </h4>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center p-3 bg-success-50 rounded-lg">
                <span className="text-sm font-medium text-success-800">Buy Range</span>
                <span className="text-sm font-bold text-success-900">
                  {formatPrice(recommendation.buy_range_low)} - {formatPrice(recommendation.buy_range_high)}
                </span>
              </div>
              
              <div className="flex justify-between items-center p-3 bg-danger-50 rounded-lg">
                <span className="text-sm font-medium text-danger-800">Sell Range</span>
                <span className="text-sm font-bold text-danger-900">
                  {formatPrice(recommendation.sell_range_low)} - {formatPrice(recommendation.sell_range_high)}
                </span>
              </div>
            </div>

            {/* Risk Assessment */}
            <div className="pt-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-neutral-600">Risk Level</span>
                <span className={`text-sm font-bold ${getRiskColor(recommendation.risk_level)}`}>
                  {recommendation.risk_level.toUpperCase()}
                </span>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-sm font-medium text-neutral-600">Volatility</span>
                <span className="text-sm font-bold text-neutral-800">
                  {Math.round(recommendation.volatility_score * 100)}%
                </span>
              </div>
            </div>
          </div>

          {/* Signals */}
          <div className="space-y-4">
            <h4 className="font-semibold text-neutral-900 flex items-center">
              <Shield className="w-4 h-4 mr-2 text-neutral-600" />
              Analysis Signals
            </h4>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-neutral-600">Valuation</span>
                <div className="flex items-center space-x-2">
                  <div className={`w-16 h-2 rounded-full bg-neutral-200 overflow-hidden`}>
                    <div 
                      className={`h-full ${recommendation.valuation_signal >= 0 ? 'bg-success-500' : 'bg-danger-500'}`}
                      style={{ width: `${Math.abs(recommendation.valuation_signal) * 50 + 50}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {formatPercentage(recommendation.valuation_signal)}
                  </span>
                </div>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm text-neutral-600">Technical</span>
                <div className="flex items-center space-x-2">
                  <div className={`w-16 h-2 rounded-full bg-neutral-200 overflow-hidden`}>
                    <div 
                      className={`h-full ${recommendation.technical_signal >= 0 ? 'bg-success-500' : 'bg-danger-500'}`}
                      style={{ width: `${Math.abs(recommendation.technical_signal) * 50 + 50}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {formatPercentage(recommendation.technical_signal)}
                  </span>
                </div>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm text-neutral-600">News Sentiment</span>
                <div className="flex items-center space-x-2">
                  <div className={`w-16 h-2 rounded-full bg-neutral-200 overflow-hidden`}>
                    <div 
                      className={`h-full ${recommendation.news_sentiment_signal >= 0 ? 'bg-success-500' : 'bg-danger-500'}`}
                      style={{ width: `${Math.abs(recommendation.news_sentiment_signal) * 50 + 50}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {formatPercentage(recommendation.news_sentiment_signal)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Key Factors */}
        <div className="mt-6 pt-6 border-t border-neutral-200">
          <h4 className="font-semibold text-neutral-900 mb-3">Key Factors</h4>
          <div className="flex flex-wrap gap-2">
            {recommendation.key_factors.map((factor, index) => (
              <span 
                key={index}
                className="px-3 py-1 bg-neutral-100 text-neutral-700 rounded-lg text-sm"
              >
                {factor}
              </span>
            ))}
          </div>
        </div>

        {/* Recent News */}
        {stock.recent_news.length > 0 && (
          <div className="mt-6 pt-6 border-t border-neutral-200">
            <h4 className="font-semibold text-neutral-900 mb-3 flex items-center">
              <Clock className="w-4 h-4 mr-2 text-neutral-600" />
              Recent News
            </h4>
            <div className="space-y-3">
              {stock.recent_news.slice(0, 3).map((article, index) => (
                <div key={index} className="flex items-start space-x-3 p-3 bg-neutral-50 rounded-lg">
                  <div className="flex-1">
                    <h5 className="text-sm font-medium text-neutral-900 line-clamp-2">
                      {article.title}
                    </h5>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-xs text-neutral-500">{article.source}</span>
                      {article.sentiment_label && (
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          article.sentiment_label === 'positive' ? 'bg-success-100 text-success-700' :
                          article.sentiment_label === 'negative' ? 'bg-danger-100 text-danger-700' :
                          'bg-neutral-100 text-neutral-700'
                        }`}>
                          {article.sentiment_label}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Timestamp */}
        <div className="mt-6 pt-4 border-t border-neutral-200 text-center">
          <p className="text-xs text-neutral-500">
            Analysis updated {formatDistanceToNow(new Date(recommendation.created_at))} ago
          </p>
        </div>
      </div>
    </div>
  );
};

export default StockCard; 