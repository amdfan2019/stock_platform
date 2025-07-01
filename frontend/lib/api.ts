import axios from 'axios';
import { StockAnalysis, StockRecommendation, NewsArticle, TrendingStock } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds timeout for stock analysis
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    throw new Error(error.response?.data?.detail || error.message || 'API request failed');
  }
);

export const stockAPI = {
  // Search for stock analysis
  searchStock: async (ticker: string): Promise<StockAnalysis> => {
    const response = await api.get(`/api/search?query=${ticker.toUpperCase()}`);
    return response.data;
  },

  // Get recommendation for a stock
  getRecommendation: async (ticker: string): Promise<StockRecommendation> => {
    const response = await api.get(`/api/recommendation/${ticker.toUpperCase()}`);
    return response.data;
  },

  // Get news for a stock
  getStockNews: async (ticker: string, hours: number = 24): Promise<{ articles: NewsArticle[], sentiment_summary: any }> => {
    const response = await api.get(`/api/news/${ticker.toUpperCase()}?hours=${hours}`);
    return response.data;
  },

  // Get detailed analysis
  getAnalysis: async (ticker: string): Promise<{ analysis: any, timestamp: string }> => {
    const response = await api.get(`/api/analysis/${ticker.toUpperCase()}`);
    return response.data;
  },

  // Get trending stocks
  getTrending: async (): Promise<{ trending: TrendingStock[], updated_at: string }> => {
    const response = await api.get('/api/trending');
    return response.data;
  },

  // Get watchlist
  getWatchlist: async (): Promise<{ watchlist: string[], message: string }> => {
    const response = await api.get('/api/watchlist');
    return response.data;
  },

  // Add to watchlist
  addToWatchlist: async (ticker: string): Promise<{ message: string, ticker: string }> => {
    const response = await api.post('/api/watchlist/add', { ticker });
    return response.data;
  },

  // Health check
  healthCheck: async (): Promise<{ status: string, timestamp: string, services: any }> => {
    const response = await api.get('/health');
    return response.data;
  },

  // Get market sentiment
  getMarketSentiment: async (): Promise<any> => {
    const response = await api.get('/api/market-sentiment');
    return response.data;
  },
};

export default api; 