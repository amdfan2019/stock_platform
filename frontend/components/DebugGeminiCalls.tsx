import React, { useEffect, useState } from 'react';

interface GeminiCallLog {
  timestamp: string;
  purpose: string;
}

const DebugGeminiCalls: React.FC = () => {
  const [logs, setLogs] = useState<GeminiCallLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('http://localhost:8000/api/debug/gemini-calls');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLogs(data.logs || data); // support both {logs, total} and array
      setTotal(data.total || (Array.isArray(data) ? data.length : null));
    } catch (err) {
      setError('Failed to fetch Gemini API call logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-neutral-900">Gemini API Call Debug Log</h2>
        <button
          onClick={fetchLogs}
          className="px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
          disabled={loading}
        >
          {loading ? 'Updating...' : 'Update'}
        </button>
      </div>
      <div className="mb-2 text-neutral-800 font-medium">
        Total Gemini API calls: {total !== null ? total : logs.length}
      </div>
      {error && <div className="text-red-600 mb-4">{error}</div>}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-neutral-900">
          <thead>
            <tr className="bg-neutral-100">
              <th className="px-3 py-2 text-left font-semibold">Timestamp</th>
              <th className="px-3 py-2 text-left font-semibold">Purpose</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, idx) => (
              <tr key={idx} className="border-b border-neutral-200">
                <td className="px-3 py-2 whitespace-nowrap">{new Date(log.timestamp).toLocaleString()}</td>
                <td className="px-3 py-2 whitespace-nowrap">{log.purpose}</td>
              </tr>
            ))}
            {logs.length === 0 && !loading && (
              <tr>
                <td colSpan={2} className="px-3 py-4 text-center text-neutral-500">No Gemini API calls logged yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DebugGeminiCalls; 