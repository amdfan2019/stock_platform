export interface StockRecommendation {
  ticker: string;
  action: 'BUY' | 'HOLD' | 'SELL';
  confidence_score: number;
  reasoning: string;
  key_factors: string[];
  valuation_signal: number;
  technical_signal: number;
  news_sentiment_signal: number;
  buy_range_low?: number;
  buy_range_high?: number;
  sell_range_low?: number;
  sell_range_high?: number;
  risk_level: 'low' | 'medium' | 'high';
  volatility_score: number;
  created_at: string;
}

export interface NewsArticle {
  title: string;
  summary?: string;
  source: string;
  sentiment_label?: 'positive' | 'negative' | 'neutral';
  sentiment_score?: number;
  impact_level?: 'high' | 'medium' | 'low';
  published_at?: string;
}

export interface StockAnalysis {
  ticker: string;
  company_name: string;
  current_price?: number;
  market_cap?: number;
  pe_ratio?: number;
  quality_score?: number;
  margin_of_safety?: number;
  recommendation?: StockRecommendation;
  recent_news: NewsArticle[];
}

export interface TrendingStock {
  ticker: string;
  score: number;
  sentiment: string;
}

export interface WatchlistItem {
  ticker: string;
  added_at: string;
}

export interface APIResponse<T> {
  data?: T;
  error?: string;
  success: boolean;
}

export interface StockMetrics {
  pe_ratio?: number;
  forward_pe?: number;
  peg_ratio?: number;
  price_to_book?: number;
  debt_to_equity?: number;
  return_on_equity?: number;
  free_cash_flow_per_share?: number;
  quality_score?: number;
  margin_of_safety?: number;
}

export interface SearchState {
  query: string;
  isLoading: boolean;
  results: StockAnalysis | null;
  error: string | null;
} 