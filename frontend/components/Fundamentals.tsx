'use client';

import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, TrendingDown, RefreshCw, Clock, AlertCircle, Database, Calendar, DollarSign, Briefcase, Home, Factory } from 'lucide-react';
import { toast } from 'react-hot-toast';

interface EconomicIndicator {
  indicator_name: string;
  value: number;
  unit: string;
  reference_date: string;
  previous_value?: number;
  period_type: string;
  source: string;
}

interface FundamentalsAnalysis {
  overall_assessment: string;
  economic_cycle_stage: string;
  inflation_outlook: string;
  employment_outlook: string;
  monetary_policy_stance: string;
  key_insights: string[];
  market_implications: string;
  sector_impacts: Record<string, any>;
  risk_factors: string[];
  confidence_level: number;
  analysis_date: string;
  explanation: string;
}

interface EconomicEvent {
  event_name: string;
  category: string;
  scheduled_date: string;
  importance: string;
  previous_value?: number;
  forecast_value?: number;
  actual_value?: number;
  impact_description: string;
  is_released: boolean;
}

interface FundamentalsData {
  fundamentals_data: Record<string, EconomicIndicator[]>;
  analysis: FundamentalsAnalysis | null;
  data_timestamp: string;
  categories: string[];
}

const Fundamentals: React.FC = () => {
  const [fundamentalsData, setFundamentalsData] = useState<FundamentalsData | null>(null);
  const [upcomingEvents, setUpcomingEvents] = useState<EconomicEvent[]>([]);
  const [dbStats, setDbStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    loadFundamentalsData();
    loadUpcomingEvents();
    loadDatabaseStats();
    
    // Auto-refresh every 60 minutes
    const interval = setInterval(() => {
      loadFundamentalsData();
      loadUpcomingEvents();
      loadDatabaseStats();
    }, 60 * 60 * 1000);
    
    return () => clearInterval(interval);
  }, []);

  const loadFundamentalsData = async () => {
    try {
      setError(null);
      
      const response = await fetch('http://localhost:8000/api/fundamentals');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data: FundamentalsData = await response.json();
      setFundamentalsData(data);
      setLastUpdated(new Date());
      
      const totalIndicators = Object.values(data.fundamentals_data).reduce((sum, indicators) => sum + indicators.length, 0);
      toast(`Loaded ${totalIndicators} economic indicators`, { icon: '📊' });
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load fundamentals data';
      setError(errorMessage);
      toast.error('Failed to load fundamentals data');
      console.error('Fundamentals data error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadUpcomingEvents = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/fundamentals/events');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setUpcomingEvents(data.upcoming_events);
      
    } catch (err) {
      console.error('Error loading upcoming events:', err);
    }
  };

  const loadDatabaseStats = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/fundamentals/stats');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setDbStats(data);
      
    } catch (err) {
      console.error('Error loading database stats:', err);
    }
  };

  const collectFreshData = async () => {
    setCollecting(true);
    setError(null);
    
    try {
      // Step 1: Collect new data
      const response = await fetch('http://localhost:8000/api/fundamentals/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to collect data: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Incremental data collection started:', result);
      
      toast.success('📈 Incremental data collection started - only new dates will be added');
      
      // Step 2: Wait, then trigger LLM analysis
      setTimeout(async () => {
        try {
          const analysisResponse = await fetch('http://localhost:8000/api/fundamentals/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
          if (!analysisResponse.ok) {
            throw new Error(`Failed to generate LLM analysis: ${analysisResponse.statusText}`);
          }
          const analysisResult = await analysisResponse.json();
          console.log('LLM analysis generated:', analysisResult);
          toast.success('🤖 LLM analysis updated');
        } catch (err) {
          console.error('Error generating LLM analysis:', err);
          toast.error('Failed to generate LLM analysis');
        } finally {
          // Always refresh data after analysis
          loadFundamentalsData();
          loadDatabaseStats();
        }
      }, 30000); // 30 seconds delay for data collection
      
    } catch (err) {
      console.error('Error collecting fresh data:', err);
      setError(`Failed to collect fresh data: ${err instanceof Error ? err.message : 'Unknown error'}`);
      toast.error('Failed to start data collection');
    } finally {
      setCollecting(false);
    }
  };

  const backfillHistoricalData = async () => {
    setCollecting(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/fundamentals/backfill?days_back=730', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to backfill data: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Historical backfill started:', result);
      
      toast.success('📚 Historical backfill started - collecting 2 years of time series data');
      
      // Refresh data after a longer delay for historical collection
      setTimeout(() => {
        loadFundamentalsData();
      }, 60000); // 60 seconds delay
      
    } catch (err) {
      console.error('Error backfilling historical data:', err);
      setError(`Failed to backfill data: ${err instanceof Error ? err.message : 'Unknown error'}`);
      toast.error('Failed to start historical data collection');
    } finally {
      setCollecting(false);
    }
  };

  const allowedCategories = ['inflation', 'employment', 'interest_rates', 'gdp', 'retail', 'manufacturing', 'home_prices'];

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'inflation': return <DollarSign className="w-5 h-5" />;
      case 'employment': return <Briefcase className="w-5 h-5" />;
      case 'interest_rates': return <TrendingUp className="w-5 h-5" />;
      case 'gdp': return <BarChart3 className="w-5 h-5" />;
      case 'retail': return <Home className="w-5 h-5" />;
      case 'manufacturing': return <Factory className="w-5 h-5" />;
      case 'home_prices': return <Home className="w-5 h-5" />;
      default: return <BarChart3 className="w-5 h-5" />;
    }
  };

  const getCategoryColor = (category: string) => {
    const colors = {
      'inflation': 'bg-red-100 text-red-800 border-red-200',
      'employment': 'bg-blue-100 text-blue-800 border-blue-200',
      'interest_rates': 'bg-green-100 text-green-800 border-green-200',
      'gdp': 'bg-purple-100 text-purple-800 border-purple-200',
      'retail': 'bg-orange-100 text-orange-800 border-orange-200',
      'manufacturing': 'bg-gray-100 text-gray-800 border-gray-200',
      'home_prices': 'bg-gray-100 text-gray-800 border-gray-200'
    };
    return colors[category as keyof typeof colors] || 'bg-gray-100 text-gray-800 border-gray-200';
  };

  const formatCategoryName = (category: string) => {
    return category.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const formatIndicatorName = (name: string) => {
    return name.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const calculateChange = (current: number, periodType: string, previous?: number) => {
    if (!previous) return null;
    const change = current - previous;
    const changePercent = (change / previous) * 100;
    
    // Determine timeframe context based on period type
    let timeframeLabel = '';
    switch (periodType) {
      case 'daily':
        timeframeLabel = 'vs. prev day';
        break;
      case 'weekly':
        timeframeLabel = 'vs. prev week';
        break;
      case 'monthly':
        timeframeLabel = 'vs. prev month';
        break;
      case 'quarterly':
        timeframeLabel = 'vs. prev quarter';
        break;
      default:
        timeframeLabel = 'vs. previous';
    }
    
    return { change, changePercent, timeframeLabel };
  };

  const formatValue = (value: number, unit: string) => {
    if (unit === '%') {
      return `${value.toFixed(2)}%`;
    } else if (unit === 'index') {
      return value.toFixed(1);
    } else if (unit.includes('thousands')) {
      return `${(value / 1000).toFixed(1)}M`;
    } else if (unit.includes('millions')) {
      return `${(value / 1000000).toFixed(1)}B`;
    } else {
      return value.toFixed(2);
    }
  };

  const getImportanceColor = (importance: string) => {
    switch (importance) {
      case 'high': return 'bg-red-100 text-red-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const filteredCategories = fundamentalsData
    ? (selectedCategory === 'all'
        ? fundamentalsData.categories.filter((cat) => allowedCategories.includes(cat))
        : [selectedCategory])
    : [];

  // Move getQuarterLabel to top-level so it can be reused for all quarterly indicators
  const getQuarterLabel = (dateStr: string) => {
    const d = new Date(dateStr);
    let year = d.getFullYear();
    const month = d.getMonth();
    let q = Math.floor(month / 3) + 1;
    // FRED/BEA/standard convention: Jan = Q4 prev year, Apr = Q1, Jul = Q2, Oct = Q3
    if (month === 0) { // January
      q = 4;
      year = year - 1;
    } else if (month === 3) { // April
      q = 1;
    } else if (month === 6) { // July
      q = 2;
    } else if (month === 9) { // October
      q = 3;
    }
    return `Q${q} ${year}`;
  };

  if (loading && !fundamentalsData) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200">
        <div className="animate-pulse">
          <div className="flex items-center space-x-3 mb-6">
            <div className="bg-neutral-200 w-8 h-8 rounded-lg"></div>
            <div className="bg-neutral-200 h-6 w-48 rounded"></div>
          </div>
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-3">
                <div className="bg-neutral-200 h-5 w-full rounded"></div>
                <div className="space-y-2">
                  <div className="bg-neutral-200 h-3 w-full rounded"></div>
                  <div className="bg-neutral-200 h-3 w-5/6 rounded"></div>
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
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">
            Failed to Load Fundamentals Data
          </h3>
          <p className="text-neutral-600 mb-4">{error}</p>
          <button
            onClick={loadFundamentalsData}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <BarChart3 className="w-4 h-4 mr-2" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Fundamental Analysis Box (LLM) Only */}
      <div className="bg-white rounded-xl shadow-sm border border-neutral-200">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-neutral-900">
              Fundamental analysis
            </h2>
            <button
              onClick={collectFreshData}
              disabled={collecting}
              className="inline-flex items-center px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${collecting ? 'animate-spin' : ''}`} />
              {collecting ? 'Collecting...' : 'Add New Data'}
            </button>
          </div>
          {fundamentalsData?.analysis && (
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-4">
              <div className="flex items-center mb-4">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold mr-3 
                  ${fundamentalsData.analysis.overall_assessment === 'bullish' ? 'bg-green-100 text-green-800 border border-green-200' :
                    fundamentalsData.analysis.overall_assessment === 'bearish' ? 'bg-red-100 text-red-800 border border-red-200' :
                    'bg-gray-100 text-gray-800 border border-gray-200'}`}
                >
                  {fundamentalsData.analysis.overall_assessment.charAt(0).toUpperCase() + fundamentalsData.analysis.overall_assessment.slice(1)}
                </span>
              </div>
              <div className="text-base text-neutral-800 mb-2" style={{ minHeight: '3.5em' }}>
                {fundamentalsData.analysis.explanation}
              </div>
              <div className="text-xs text-neutral-500">
                Analysis as of {fundamentalsData.analysis.analysis_date ? new Date(fundamentalsData.analysis.analysis_date).toLocaleDateString() : ''}
              </div>
            </div>
          )}
        </div>
      </div>
      {/* Economic Indicators Grid (restored) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {filteredCategories.map((category) => {
          let indicators = fundamentalsData?.fundamentals_data[category] || [];
          // GDP: Only show the most recent gdp_yoy_growth_bea, preferring API data, fallback to web if newer
          if (category === 'gdp') {
            let gdpIndicators = indicators.filter((i) => i.indicator_name === 'gdp_yoy_growth_bea');
            if (gdpIndicators.length === 0) return null;
            // Group by reference_date, prefer 'bea' over 'bea_web' for each date
            const byDate: Record<string, EconomicIndicator> = {};
            gdpIndicators.forEach((i) => {
              const key = i.reference_date;
              if (!byDate[key] || (byDate[key].source !== 'bea' && i.source === 'bea')) {
                byDate[key] = i;
              }
            });
            // Sort by reference_date descending
            const sorted = Object.values(byDate).sort((a, b) => new Date(b.reference_date).getTime() - new Date(a.reference_date).getTime());
            const latest = sorted[0];
            const previous = sorted[1];
            const change = previous ? (latest.value - previous.value) : null;
            return (
              <div key={category} className="bg-white rounded-xl shadow-sm border border-neutral-200">
                <div className="p-4 border-b border-neutral-200">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${getCategoryColor(category).split(' ')[0]} ${getCategoryColor(category).split(' ')[1]}`}> 
                      {getCategoryIcon(category)}
                    </div>
                    <h3 className="text-lg font-semibold text-neutral-900">
                      GDP
                    </h3>
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-sm font-medium text-neutral-900">
                      Annual Growth Rate
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-neutral-900">
                        {latest.value.toFixed(2)}%
                      </div>
                      {previous && change !== null && (
                        <div className={`text-sm mt-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}> 
                          <div className="flex items-center justify-end space-x-1">
                            {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            <span>{change >= 0 ? '+' : ''}{change.toFixed(2)}</span>
                          </div>
                          <div className="text-xs text-neutral-500 text-right">vs. {getQuarterLabel(previous.reference_date)}</div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-neutral-500">
                    {latest.reference_date} • {latest.source.toUpperCase()}
                  </div>
                </div>
              </div>
            );
          }
          // Only show the most recent value for each indicator in the category
          if (category === 'inflation') {
            // Show only the most recent cpi_yoy_inflation and its change vs previous month
            let cpiIndicators = indicators.filter((i) => i.indicator_name === 'cpi_yoy_inflation');
            if (cpiIndicators.length === 0) return null;
            // Sort by reference_date descending
            cpiIndicators = cpiIndicators.sort((a, b) => new Date(b.reference_date).getTime() - new Date(a.reference_date).getTime());
            const latest = cpiIndicators[0];
            const previous = cpiIndicators[1];
            const change = previous ? (latest.value - previous.value) : null;
            return (
              <div key={category} className="bg-white rounded-xl shadow-sm border border-neutral-200">
                <div className="p-4 border-b border-neutral-200">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${getCategoryColor(category).split(' ')[0]} ${getCategoryColor(category).split(' ')[1]}`}> 
                      {getCategoryIcon(category)}
                    </div>
                    <h3 className="text-lg font-semibold text-neutral-900">
                      Inflation
                    </h3>
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-sm font-medium text-neutral-900">
                      CPI YoY
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-neutral-900">
                        {latest.value.toFixed(2)}%
                      </div>
                      {previous && change !== null && (
                        <div className={`text-sm mt-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}> 
                          <div className="flex items-center justify-end space-x-1">
                            {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            <span>{change >= 0 ? '+' : ''}{change.toFixed(2)}</span>
                          </div>
                          <div className="text-xs text-neutral-500 text-right">vs. prev month</div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-neutral-500">
                    {latest.reference_date} • {latest.source.toUpperCase()}
                  </div>
                </div>
              </div>
            );
          } else if (category === 'interest_rates') {
            indicators = indicators.filter((i) => i.indicator_name === 'fed_funds_rate');
            indicators = indicators.sort((a, b) => new Date(b.reference_date).getTime() - new Date(a.reference_date).getTime());
            if (indicators.length === 0) return null;
            const latest = indicators[0];
            const previous = indicators[1];
            const change = previous ? (latest.value - previous.value) : null;
            return (
              <div key={category} className="bg-white rounded-xl shadow-sm border border-neutral-200">
                <div className="p-4 border-b border-neutral-200">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${getCategoryColor(category).split(' ')[0]} ${getCategoryColor(category).split(' ')[1]}`}> 
                      {getCategoryIcon(category)}
                    </div>
                    <h3 className="text-lg font-semibold text-neutral-900">
                      Interest
                    </h3>
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-sm font-medium text-neutral-900">
                      Fed Funds Rate
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-neutral-900">
                        {latest.value.toFixed(2)}%
                      </div>
                      {previous && change !== null && (
                        <div className={`text-sm mt-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}> 
                          <div className="flex items-center justify-end space-x-1">
                            {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            <span>{change >= 0 ? '+' : ''}{change.toFixed(2)}</span>
                          </div>
                          <div className="text-xs text-neutral-500 text-right">vs. prev month</div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-neutral-500">
                    {latest.reference_date} • {latest.source.toUpperCase()}
                  </div>
                </div>
              </div>
            );
          } else if (category === 'retail') {
            indicators = indicators.filter((i) => i.indicator_name === 'retail_sales');
            indicators = indicators.slice(0, 1); // Only most recent month
          } else if (category === 'manufacturing') {
            // Only show the most recent value for each indicator in manufacturing
            const seen = new Set();
            indicators = indicators.filter((i) => {
              if (seen.has(i.indicator_name)) return false;
              seen.add(i.indicator_name);
              return true;
            });
            indicators = indicators.slice(0, 2); // Only most recent for each
            if (indicators.length === 0) return null;
            return (
              <div key={category} className="bg-white rounded-xl shadow-sm border border-neutral-200">
                <div className="p-4 border-b border-neutral-200">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${getCategoryColor(category).split(' ')[0]} ${getCategoryColor(category).split(' ')[1]}`}> 
                      {getCategoryIcon(category)}
                    </div>
                    <h3 className="text-lg font-semibold text-neutral-900">
                      Manufacturing
                    </h3>
                  </div>
                </div>
                <div className="p-4 space-y-4">
                  {indicators.map((indicator, index) => {
                    const changeData = calculateChange(indicator.value, indicator.period_type, indicator.previous_value);
                    return (
                      <div key={index} className="border-b border-neutral-100 last:border-b-0 pb-3 last:pb-0">
                        <div className="flex justify-between items-center mb-1">
                          <div className="text-sm font-medium text-neutral-900">
                            {formatIndicatorName(indicator.indicator_name)}
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-semibold text-neutral-900">
                              {formatValue(indicator.value, indicator.unit)}
                            </div>
                            {changeData && (
                              <div className={`text-sm ${changeData.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                <div className="flex items-center justify-end space-x-1">
                                  {changeData.change >= 0 ? (
                                    <TrendingUp className="w-3 h-3" />
                                  ) : (
                                    <TrendingDown className="w-3 h-3" />
                                  )}
                                  <span>{changeData.change >= 0 ? '+' : ''}{changeData.changePercent.toFixed(1)}%</span>
                                </div>
                                <div className="text-xs text-neutral-500 text-right">
                                  {changeData.timeframeLabel}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="text-xs text-neutral-500">
                          {indicator.reference_date} • {indicator.source.toUpperCase()}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          } else if (category === 'employment') {
            // Only show the most recent unemployment rate
            let unempIndicators = indicators.filter((i) => i.indicator_name === 'unemployment_rate');
            if (unempIndicators.length === 0) return null;
            // Sort by reference_date descending
            unempIndicators = unempIndicators.sort((a, b) => new Date(b.reference_date).getTime() - new Date(a.reference_date).getTime());
            const latest = unempIndicators[0];
            const previous = unempIndicators[1];
            const change = previous ? (latest.value - previous.value) : null;
            return (
              <div key={category} className="bg-white rounded-xl shadow-sm border border-neutral-200">
                <div className="p-4 border-b border-neutral-200">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${getCategoryColor(category).split(' ')[0]} ${getCategoryColor(category).split(' ')[1]}`}> 
                      {getCategoryIcon(category)}
                    </div>
                    <h3 className="text-lg font-semibold text-neutral-900">
                      Jobs
                    </h3>
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-sm font-medium text-neutral-900">
                      Unemployment Rate
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-neutral-900">
                        {latest.value.toFixed(2)}%
                      </div>
                      {previous && change !== null && (
                        <div className={`text-sm mt-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}> 
                          <div className="flex items-center justify-end space-x-1">
                            {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            <span>{change >= 0 ? '+' : ''}{change.toFixed(2)}</span>
                          </div>
                          <div className="text-xs text-neutral-500 text-right">vs. prev month</div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-neutral-500">
                    {latest.reference_date} • {latest.source.toUpperCase()}
                  </div>
                </div>
              </div>
            );
          } else if (category === 'home_prices') {
            let homeIndicators = indicators.filter((i) => i.indicator_name === 'home_price_index');
            if (homeIndicators.length === 0) return null;
            // Sort by reference_date descending
            homeIndicators = homeIndicators.sort((a, b) => new Date(b.reference_date).getTime() - new Date(a.reference_date).getTime());
            const latest = homeIndicators[0];
            const previous = homeIndicators[1];
            const change = previous ? (latest.value - previous.value) : null;
            const changePercent = previous ? ((latest.value - previous.value) / previous.value) * 100 : null;
            return (
              <div key={category} className="bg-white rounded-xl shadow-sm border border-neutral-200">
                <div className="p-4 border-b border-neutral-200">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${getCategoryColor(category).split(' ')[0]} ${getCategoryColor(category).split(' ')[1]}`}> 
                      {getCategoryIcon(category)}
                    </div>
                    <h3 className="text-lg font-semibold text-neutral-900">
                      Home Prices
                    </h3>
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex justify-between items-center mb-1">
                    <div className="text-sm font-medium text-neutral-900">
                      Case-Shiller Index
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-neutral-900">
                        {latest.value.toFixed(2)}
                      </div>
                      {previous && changePercent !== null && (
                        <div className={`text-sm mt-1 ${changePercent >= 0 ? 'text-green-600' : 'text-red-600'}`}> 
                          <div className="flex items-center justify-end space-x-1">
                            {changePercent >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            <span>{changePercent >= 0 ? '+' : ''}{changePercent.toFixed(2)}%</span>
                          </div>
                          <div className="text-xs text-neutral-500 text-right">vs. prev month</div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-neutral-500">
                    {latest.reference_date} • {latest.source.toUpperCase()}
                  </div>
                </div>
              </div>
            );
          }
          if (indicators.length === 0) return null;

          return (
            <div key={category} className="bg-white rounded-xl shadow-sm border border-neutral-200">
              <div className="p-4 border-b border-neutral-200">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${getCategoryColor(category).split(' ')[0]} ${getCategoryColor(category).split(' ')[1]}`}> 
                    {getCategoryIcon(category)}
                  </div>
                  <h3 className="text-lg font-semibold text-neutral-900">
                    {formatCategoryName(category)}
                  </h3>
                </div>
              </div>
              <div className="p-4 space-y-4">
                {indicators.map((indicator, index) => {
                  const changeData = calculateChange(indicator.value, indicator.period_type, indicator.previous_value);
                  return (
                    <div key={index} className="border-b border-neutral-100 last:border-b-0 pb-3 last:pb-0">
                      <div className="flex justify-between items-center mb-1">
                        <div className="text-sm font-medium text-neutral-900">
                          {formatIndicatorName(indicator.indicator_name)}
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-semibold text-neutral-900">
                            {formatValue(indicator.value, indicator.unit)}
                          </div>
                          {changeData && (
                            <div className={`text-sm ${changeData.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              <div className="flex items-center justify-end space-x-1">
                                {changeData.change >= 0 ? (
                                  <TrendingUp className="w-3 h-3" />
                                ) : (
                                  <TrendingDown className="w-3 h-3" />
                                )}
                                <span>{changeData.change >= 0 ? '+' : ''}{changeData.changePercent.toFixed(1)}%</span>
                              </div>
                              <div className="text-xs text-neutral-500 text-right">
                                {changeData.timeframeLabel}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="text-xs text-neutral-500">
                        {indicator.reference_date} • {indicator.source.toUpperCase()}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Fundamentals; 