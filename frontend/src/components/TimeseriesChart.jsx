/**
 * TimeseriesChart.jsx — Pure-SVG line chart for time-series analytics
 * =====================================================================
 * No external chart libraries. Renders an SVG polyline chart showing
 * multiple metrics over a date range returned by the backend.
 *
 * Props:
 *   data        — array of { date, users, documents, ai_total, gemini, fallback }
 *   days        — number (1 | 7 | 30)
 *   onDaysChange — (days: number) => void
 *   loading     — boolean
 *   error       — string | null
 *
 * Metric keys shown:
 *   ai_total (teal), gemini (indigo), fallback (slate), documents (purple), users (blue)
 */

import React, { useState } from 'react';
import { TrendingUp, AlertCircle, Loader2 } from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// Chart helpers
// ─────────────────────────────────────────────────────────────────────────────

const METRICS = [
  { key: 'ai_total',  label: 'AI Responses', color: '#14b8a6', dotColor: 'bg-teal-400' },
  { key: 'gemini',    label: 'Gemini',       color: '#6366f1', dotColor: 'bg-indigo-400' },
  { key: 'fallback',  label: 'Fallback',     color: '#94a3b8', dotColor: 'bg-slate-400' },
  { key: 'documents', label: 'Documents',    color: '#a855f7', dotColor: 'bg-purple-400' },
  { key: 'users',     label: 'New Users',    color: '#3b82f6', dotColor: 'bg-blue-400' },
];

/** Build SVG polyline points string from data array and metric key. */
function buildPoints(data, metricKey, svgW, svgH, maxVal, padX = 32, padY = 12) {
  if (!data || data.length < 2) return '';
  const innerW = svgW - padX * 2;
  const innerH = svgH - padY * 2;
  const stepX  = innerW / (data.length - 1);

  return data.map((d, i) => {
    const x = padX + i * stepX;
    const y = padY + innerH - (maxVal > 0 ? (d[metricKey] / maxVal) * innerH : 0);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

/** Y-axis grid labels */
function yLabels(maxVal, count = 4) {
  const step = maxVal > 0 ? Math.ceil(maxVal / count) : 1;
  return Array.from({ length: count + 1 }, (_, i) => i * step);
}

/** Format a YYYY-MM-DD date to a short label */
function shortDate(dateStr, days) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00Z');
  if (days === 1) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export default function TimeseriesChart({ data = [], days = 7, onDaysChange, loading, error }) {
  const [activeMetrics, setActiveMetrics] = useState(
    new Set(['ai_total', 'gemini', 'fallback', 'documents'])
  );
  const [tooltip, setTooltip] = useState(null);   // { x, y, entry }

  const toggleMetric = (key) => {
    setActiveMetrics(prev => {
      const next = new Set(prev);
      if (next.has(key)) { if (next.size > 1) next.delete(key); }
      else next.add(key);
      return next;
    });
  };

  // Determine Y-axis max across all active metrics
  const maxVal = data.length > 0
    ? Math.max(1, ...data.flatMap(d =>
        METRICS.filter(m => activeMetrics.has(m.key)).map(m => d[m.key] ?? 0)
      ))
    : 1;

  const SVG_W = 560;
  const SVG_H = 160;
  const PAD_X = 36;
  const PAD_Y = 14;
  const innerW = SVG_W - PAD_X * 2;
  const innerH = SVG_H - PAD_Y * 2;
  const stepX  = data.length > 1 ? innerW / (data.length - 1) : innerW;

  // X-axis date labels — show at most 7 labels
  const labelEvery = Math.max(1, Math.ceil(data.length / 7));
  const xLabels = data
    .map((d, i) => ({ i, date: d.date }))
    .filter(({ i }) => i % labelEvery === 0 || i === data.length - 1);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">

      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h4 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
          <TrendingUp className="w-4 h-4 text-teal-600" />
          <span>Activity Over Time</span>
        </h4>

        {/* Period selector */}
        <div className="flex items-center space-x-1 bg-slate-100 rounded-xl p-0.5 text-[11px] font-bold self-start sm:self-auto">
          {[
            { value: 1,  label: 'Today' },
            { value: 7,  label: '7 Days' },
            { value: 30, label: '30 Days' },
          ].map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onDaysChange(value)}
              className={`px-3 py-1.5 rounded-lg transition-all whitespace-nowrap ${
                days === value
                  ? 'bg-white text-teal-700 shadow-sm border border-teal-100'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Metric toggles */}
      <div className="px-5 pt-3 flex flex-wrap gap-2">
        {METRICS.map(({ key, label, dotColor }) => {
          const on = activeMetrics.has(key);
          return (
            <button
              key={key}
              onClick={() => toggleMetric(key)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-semibold border transition-all ${
                on
                  ? 'bg-slate-50 border-slate-300 text-slate-700'
                  : 'bg-white border-slate-200 text-slate-400'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${on ? dotColor : 'bg-slate-200'}`} />
              {label}
            </button>
          );
        })}
      </div>

      {/* Chart body */}
      <div className="px-5 py-4 relative">

        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 bg-white/80 flex items-center justify-center z-10 rounded-b-2xl">
            <Loader2 className="w-5 h-5 text-teal-500 animate-spin" />
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="flex items-center space-x-2 text-red-600 text-xs py-4">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && data.length === 0 && (
          <p className="text-xs text-slate-400 text-center py-8">No data available for this period.</p>
        )}

        {/* SVG chart */}
        {!error && data.length > 0 && (
          <div className="overflow-x-auto">
            <svg
              width="100%"
              viewBox={`0 0 ${SVG_W} ${SVG_H + 28}`}
              className="min-w-[340px]"
              onMouseLeave={() => setTooltip(null)}
            >
              {/* Grid lines */}
              {yLabels(maxVal, 4).map((val, i) => {
                const y = PAD_Y + innerH - (val / maxVal) * innerH;
                return (
                  <g key={i}>
                    <line
                      x1={PAD_X} x2={SVG_W - PAD_X}
                      y1={y} y2={y}
                      stroke="#f1f5f9" strokeWidth="1"
                    />
                    <text x={PAD_X - 4} y={y + 3} textAnchor="end"
                      fontSize="9" fill="#94a3b8">{val}</text>
                  </g>
                );
              })}

              {/* Metric lines */}
              {METRICS.filter(m => activeMetrics.has(m.key)).map(({ key, color }) => {
                const pts = buildPoints(data, key, SVG_W, SVG_H, maxVal, PAD_X, PAD_Y);
                if (!pts) return null;
                return (
                  <polyline
                    key={key}
                    points={pts}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                );
              })}

              {/* Hover hit zones + dots */}
              {data.map((entry, i) => {
                const x = PAD_X + i * stepX;
                return (
                  <g key={i}>
                    {/* Invisible wide hit zone */}
                    <rect
                      x={x - stepX / 2} y={PAD_Y}
                      width={stepX} height={innerH}
                      fill="transparent"
                      onMouseEnter={(e) => setTooltip({ x, y: PAD_Y, entry })}
                    />
                    {/* Dots for active metrics */}
                    {METRICS.filter(m => activeMetrics.has(m.key)).map(({ key, color }) => {
                      const val = entry[key] ?? 0;
                      const cy  = PAD_Y + innerH - (maxVal > 0 ? (val / maxVal) * innerH : 0);
                      return (
                        <circle key={key} cx={x} cy={cy} r="3"
                          fill={color} stroke="white" strokeWidth="1.5" />
                      );
                    })}
                  </g>
                );
              })}

              {/* X-axis date labels */}
              {xLabels.map(({ i, date }) => (
                <text
                  key={i}
                  x={PAD_X + i * stepX}
                  y={SVG_H + 18}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#94a3b8"
                >
                  {shortDate(date, days)}
                </text>
              ))}

              {/* Tooltip */}
              {tooltip && (() => {
                const { x, entry } = tooltip;
                const lines = METRICS.filter(m => activeMetrics.has(m.key));
                const bW = 120, bH = 14 + lines.length * 14 + 8;
                const tx = Math.min(x, SVG_W - bW - 4);
                const ty = PAD_Y;
                return (
                  <g>
                    <rect x={tx} y={ty} width={bW} height={bH}
                      rx="6" fill="white"
                      stroke="#e2e8f0" strokeWidth="1"
                      filter="drop-shadow(0 2px 4px rgba(0,0,0,0.08))" />
                    <text x={tx + 8} y={ty + 12} fontSize="9" fontWeight="bold" fill="#475569">
                      {entry.date}
                    </text>
                    {lines.map(({ key, label, color }, li) => (
                      <g key={key}>
                        <circle cx={tx + 12} cy={ty + 22 + li * 14} r="3" fill={color} />
                        <text x={tx + 20} y={ty + 26 + li * 14} fontSize="9" fill="#475569">
                          {label}: <tspan fontWeight="bold">{entry[key] ?? 0}</tspan>
                        </text>
                      </g>
                    ))}
                  </g>
                );
              })()}
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}
