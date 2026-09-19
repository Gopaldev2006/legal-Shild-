import React, { useState, useEffect } from 'react';
import { Activity, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

export default function HealthStatus() {
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/health');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setHealthData(data);
    } catch (err) {
      console.error('Health check failed:', err);
      setError(err.message || 'Unable to connect to backend server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-900">Backend API Health Status</h3>
        </div>
        <button
          onClick={checkHealth}
          disabled={loading}
          className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl flex items-center space-x-1 transition-all border border-slate-200 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Check</span>
        </button>
      </div>

      {loading && !healthData && (
        <div className="py-4 text-center text-slate-500 text-xs animate-pulse">
          Connecting to backend service...
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-800 text-xs flex items-start space-x-2">
          <XCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-bold text-red-900">Backend Disconnected</div>
            <div className="mt-0.5 text-red-700">{error}</div>
            <div className="mt-1 text-[11px] text-red-600">
              Ensure FastAPI backend is running on <code>http://127.0.0.1:8000</code>.
            </div>
          </div>
        </div>
      )}

      {healthData && !error && (
        <div className="space-y-3">
          <div className="flex items-center space-x-2 text-emerald-800 bg-emerald-50 border border-emerald-200 p-2.5 rounded-xl text-xs font-bold">
            <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>Backend Operational (FastAPI + SQLite)</span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
              <span className="text-slate-500 block text-[10px] font-bold uppercase">Service</span>
              <span className="font-extrabold text-slate-900">{healthData.service}</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
              <span className="text-slate-500 block text-[10px] font-bold uppercase">Version</span>
              <span className="font-extrabold text-slate-900">{healthData.version}</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
              <span className="text-slate-500 block text-[10px] font-bold uppercase">Environment</span>
              <span className="font-extrabold text-slate-900 capitalize">{healthData.environment}</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
              <span className="text-slate-500 block text-[10px] font-bold uppercase">Server Time</span>
              <span className="font-bold text-slate-900">{new Date(healthData.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
