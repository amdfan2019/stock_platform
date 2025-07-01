'use client';

import { useState, useEffect } from 'react';

export default function TestPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const testAPI = async () => {
      try {
        console.log('Testing API connection...');
        const response = await fetch('http://localhost:8000/api/market-sentiment');
        console.log('Response:', response.status, response.statusText);
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('Data received:', result);
        setData(result);
        setError(null);
      } catch (err) {
        console.error('API test failed:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    testAPI();
  }, []);

  if (loading) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-bold mb-4">API Test - Loading...</h1>
        <div className="animate-pulse bg-gray-200 h-32 rounded"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-bold mb-4 text-red-600">API Test - Error</h1>
        <div className="bg-red-50 border border-red-200 rounded p-4">
          <p className="text-red-700">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4 text-green-600">API Test - Success!</h1>
      
      {data?.sentiment_analysis && (
        <div className="bg-green-50 border border-green-200 rounded p-6 mb-6">
          <h2 className="text-xl font-semibold mb-2">Market Sentiment Analysis</h2>
          <div className="space-y-2">
            <p><strong>Score:</strong> {data.sentiment_analysis.sentiment_score}/10</p>
            <p><strong>Label:</strong> {data.sentiment_analysis.sentiment_label}</p>
            <p><strong>Confidence:</strong> {(data.sentiment_analysis.confidence_level * 100).toFixed(1)}%</p>
            <p><strong>Date:</strong> {new Date(data.sentiment_analysis.analysis_date).toLocaleString()}</p>
          </div>
        </div>
      )}

      {data?.current_indicators && (
        <div className="bg-blue-50 border border-blue-200 rounded p-6 mb-6">
          <h2 className="text-xl font-semibold mb-2">Current Market Indicators</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {Object.entries(data.current_indicators).map(([key, indicator]: [string, any]) => (
              <div key={key} className="bg-white p-3 rounded shadow-sm">
                <h3 className="font-medium text-gray-900 uppercase">{key}</h3>
                <p className="text-lg font-semibold">{indicator.value?.toFixed(2)}</p>
                <p className={`text-sm ${indicator.change_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {indicator.change_pct >= 0 ? '+' : ''}{indicator.change_pct?.toFixed(2)}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-gray-50 border border-gray-200 rounded p-6">
        <h2 className="text-xl font-semibold mb-2">Raw Data</h2>
        <pre className="text-xs overflow-auto max-h-96 bg-white p-4 rounded border">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    </div>
  );
} 