/**
 * AnalyticsTab.jsx — Admin Analytics Dashboard Panel
 * ====================================================
 * Displays analytics cards, SVG charts, and recent activity feed.
 *
 * Props:
 *   analyticsData     — summary JSON from GET /api/v1/admin/analytics/summary
 *   analyticsActivity — array from GET /api/v1/admin/analytics/recent-activity
 *   loadingAnalytics  — boolean
 *   analyticsError    — string | null
 *   onRefresh         — () => void
 *   timeseriesData    — array from GET /api/v1/admin/analytics/timeseries
 *   timeseriesDays    — number (1 | 7 | 30)
 *   loadingTimeseries — boolean
 *   timeseriesError   — string | null
 *   onDaysChange      — (days: number) => void
 *
 * No external chart libraries — pure SVG + TailwindCSS.
 * No secrets rendered: passwords, tokens, keys are never in analytics responses.
 */

import React from 'react';
import {
  BarChart2, RefreshCw, AlertCircle, Activity, Users, FileText,
  Database, Lock, Sparkles, Bot, CheckCircle2,
} from 'lucide-react';
import TimeseriesChart from './TimeseriesChart';


// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function relativeTime(iso) {
  if (!iso) return '—';
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60)    return `${diff}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

function eventColor(eventType) {
  if (!eventType) return 'bg-slate-50 text-slate-600 border-slate-200';
  if (eventType.includes('FAIL') || eventType.includes('DENIED'))
    return 'bg-red-50 text-red-700 border-red-200';
  if (eventType.includes('DELETE') || eventType.includes('REVOKE'))
    return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-emerald-50 text-emerald-700 border-emerald-200';
}


// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

/** Animated horizontal progress bar */
function Bar({ value, max, colorClass }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="w-full bg-slate-100 rounded-full h-1.5 mt-1">
      <div
        className={`h-1.5 rounded-full transition-all duration-700 ${colorClass}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/** Single metric card */
function MetricCard({ label, value, icon: Icon, valueColor, iconBg, barMax, barColor }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">{label}</span>
        <div className={`p-1.5 rounded-lg border ${iconBg}`}>
          <Icon className={`w-3.5 h-3.5 ${valueColor}`} />
        </div>
      </div>
      <div className={`text-2xl font-extrabold ${valueColor}`}>{value ?? '—'}</div>
      {barMax !== undefined && (
        <Bar value={value ?? 0} max={barMax} colorClass={barColor} />
      )}
    </div>
  );
}

/** Pure-SVG donut chart */
function DonutChart({ percentage, primaryColor, label, total, totalLabel }) {
  const r     = 30;
  const circ  = 2 * Math.PI * r;
  const dash  = Math.max(0, Math.min(100, percentage)) / 100 * circ;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90">
          {/* Track */}
          <circle cx="40" cy="40" r={r} fill="none" stroke="#e2e8f0" strokeWidth="10" />
          {/* Fill */}
          <circle
            cx="40" cy="40" r={r} fill="none"
            stroke={primaryColor} strokeWidth="10"
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="butt"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-base font-extrabold text-slate-900">{total}</span>
          <span className="text-[9px] text-slate-400 leading-none">{totalLabel}</span>
        </div>
      </div>
      <span className="text-[10px] font-semibold text-slate-600 mt-1">{label}</span>
    </div>
  );
}

/** Horizontal stacked bar row */
function DistRow({ label, value, pct, colorClass }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px]">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="font-bold text-slate-900">
          {value}{' '}
          <span className="font-normal text-slate-400">({Math.round(pct)}%)</span>
        </span>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-700 ${colorClass}`}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export default function AnalyticsTab({
  analyticsData,
  analyticsActivity,
  loadingAnalytics,
  analyticsError,
  onRefresh,
  timeseriesData = [],
  timeseriesDays = 7,
  loadingTimeseries = false,
  timeseriesError = null,
  onDaysChange,
}) {
  const u   = analyticsData?.users     ?? {};
  const d   = analyticsData?.documents ?? {};
  const ai  = analyticsData?.ai        ?? {};
  const ses = analyticsData?.sessions  ?? {};

  const total       = u.total         ?? 0;
  const pub         = u.public        ?? 0;
  const pro         = u.professionals ?? 0;
  const adm         = u.admins        ?? 0;
  const new7        = u.new_last_7_days  ?? 0;
  const docsTotal   = d.total         ?? 0;
  const aiTotal     = ai.total_ai_responses ?? 0;
  const ragTotal    = ai.total_rag_queries  ?? 0;
  const gemini      = ai.gemini_queries     ?? 0;
  const fallback    = ai.fallback_queries   ?? 0;
  const geminiPct   = ai.gemini_percentage  ?? 0;
  const sessions    = ses.active_sessions   ?? 0;

  return (
    <div className="space-y-6">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-teal-50 border border-teal-100 rounded-xl text-teal-600">
            <BarChart2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Analytics Dashboard</h3>
            <p className="text-xs text-slate-500">
              Live data from users, documents, AI usage, and audit logs
            </p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={loadingAnalytics}
          className="px-3.5 py-2 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingAnalytics ? 'animate-spin' : ''}`} />
          <span>{loadingAnalytics ? 'Loading…' : 'Refresh'}</span>
        </button>
      </div>

      {/* ── Error state ── */}
      {analyticsError && (
        <div className="flex items-center space-x-2 bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-xs">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{analyticsError}</span>
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loadingAnalytics && !analyticsData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-slate-100 animate-pulse rounded-2xl h-24" />
          ))}
        </div>
      )}

      {/* ── Content (only when data is present) ── */}
      {!loadingAnalytics && !analyticsError && analyticsData && (
        <>
          {/* ── User metric cards ── */}
          <section>
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Users</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="Total Users"    value={total} icon={Users}        valueColor="text-indigo-600"  iconBg="bg-indigo-50 border-indigo-100"  barMax={total}   barColor="bg-indigo-400" />
              <MetricCard label="Public Users"   value={pub}   icon={Users}        valueColor="text-blue-600"    iconBg="bg-blue-50 border-blue-100"      barMax={total}   barColor="bg-blue-400" />
              <MetricCard label="Professionals"  value={pro}   icon={CheckCircle2} valueColor="text-emerald-600" iconBg="bg-emerald-50 border-emerald-100" barMax={total}   barColor="bg-emerald-400" />
              <MetricCard label="New (7 days)"   value={new7}  icon={Activity}     valueColor="text-violet-600"  iconBg="bg-violet-50 border-violet-100" />
            </div>
          </section>

          {/* ── Document + AI metric cards ── */}
          <section>
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Documents & AI</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="Documents"      value={docsTotal} icon={FileText}  valueColor="text-purple-600" iconBg="bg-purple-50 border-purple-100" />
              <MetricCard label="AI Responses"   value={aiTotal}   icon={Bot}       valueColor="text-teal-600"   iconBg="bg-teal-50 border-teal-100" />
              <MetricCard label="RAG Queries"    value={ragTotal}  icon={Database}  valueColor="text-slate-700"  iconBg="bg-slate-50 border-slate-200" />
              <MetricCard label="Active Sessions" value={sessions} icon={Lock}      valueColor="text-amber-600"  iconBg="bg-amber-50 border-amber-100" />
            </div>
          </section>

          {/* ── AI Queries: Gemini + Fallback cards ── */}
          <section>
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">AI Provider Breakdown</h4>
            <div className="grid grid-cols-2 gap-4">
              <MetricCard
                label="Gemini Requests"
                value={gemini}
                icon={Sparkles}
                valueColor="text-indigo-600"
                iconBg="bg-indigo-50 border-indigo-100"
                barMax={aiTotal}
                barColor="bg-indigo-400"
              />
              <MetricCard
                label="Fallback Requests"
                value={fallback}
                icon={Bot}
                valueColor="text-slate-600"
                iconBg="bg-slate-50 border-slate-200"
                barMax={aiTotal}
                barColor="bg-slate-400"
              />
            </div>
          </section>

          {/* ── Charts row ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* User Distribution */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
              <h4 className="text-sm font-bold text-slate-900 mb-4 flex items-center space-x-2">
                <Users className="w-4 h-4 text-indigo-600" />
                <span>User Distribution</span>
              </h4>
              {total === 0 ? (
                <p className="text-xs text-slate-400 text-center py-6">No users registered yet.</p>
              ) : (
                <div className="flex items-center space-x-6">
                  <div className="flex-1 space-y-3">
                    <DistRow label="Public"        value={pub} pct={total ? pub / total * 100 : 0} colorClass="bg-blue-400" />
                    <DistRow label="Professionals" value={pro} pct={total ? pro / total * 100 : 0} colorClass="bg-emerald-400" />
                    <DistRow label="Admins"        value={adm} pct={total ? adm / total * 100 : 0} colorClass="bg-amber-400" />
                  </div>
                  {/* SVG donut — public slice + pro slice */}
                  <div className="flex-shrink-0">
                    <div className="relative w-20 h-20">
                      <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90">
                        <circle cx="40" cy="40" r="30" fill="none" stroke="#e2e8f0" strokeWidth="10" />
                        {/* public */}
                        <circle cx="40" cy="40" r="30" fill="none" stroke="#60a5fa" strokeWidth="10"
                          strokeDasharray={`${(pub/total)*2*Math.PI*30} ${2*Math.PI*30}`}
                          strokeLinecap="butt" />
                        {/* professionals */}
                        <circle cx="40" cy="40" r="30" fill="none" stroke="#34d399" strokeWidth="10"
                          strokeDasharray={`${(pro/total)*2*Math.PI*30} ${2*Math.PI*30}`}
                          strokeLinecap="butt"
                          strokeDashoffset={`-${(pub/total)*2*Math.PI*30}`} />
                        {/* admins */}
                        <circle cx="40" cy="40" r="30" fill="none" stroke="#fbbf24" strokeWidth="10"
                          strokeDasharray={`${(adm/total)*2*Math.PI*30} ${2*Math.PI*30}`}
                          strokeLinecap="butt"
                          strokeDashoffset={`-${((pub+pro)/total)*2*Math.PI*30}`} />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-lg font-extrabold text-slate-900">{total}</span>
                        <span className="text-[9px] text-slate-400">total</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* AI Provider Usage */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
              <h4 className="text-sm font-bold text-slate-900 mb-4 flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>AI Provider Usage</span>
              </h4>
              {aiTotal === 0 ? (
                <p className="text-xs text-slate-400 text-center py-6">No AI responses recorded yet.</p>
              ) : (
                <div className="flex items-center space-x-6">
                  <div className="flex-1 space-y-3">
                    <DistRow label="Gemini"   value={gemini}   pct={geminiPct}           colorClass="bg-indigo-400" />
                    <DistRow label="Fallback" value={fallback} pct={100 - geminiPct}     colorClass="bg-slate-400" />
                    <p className="text-[10px] text-slate-400 border-t border-slate-100 pt-2 mt-1">
                      Total AI responses: <span className="font-bold text-slate-700">{aiTotal}</span>
                    </p>
                  </div>
                  {/* SVG donut */}
                  <div className="flex-shrink-0">
                    <div className="relative w-20 h-20">
                      <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90">
                        <circle cx="40" cy="40" r="30" fill="none" stroke="#e2e8f0" strokeWidth="10" />
                        <circle cx="40" cy="40" r="30" fill="none" stroke="#818cf8" strokeWidth="10"
                          strokeDasharray={`${(geminiPct/100)*2*Math.PI*30} ${2*Math.PI*30}`}
                          strokeLinecap="butt" />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-base font-extrabold text-indigo-600">{Math.round(geminiPct)}%</span>
                        <span className="text-[9px] text-slate-400">Gemini</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Time-Series Chart ── */}
          <TimeseriesChart
            data={timeseriesData}
            days={timeseriesDays}
            onDaysChange={onDaysChange}
            loading={loadingTimeseries}
            error={timeseriesError}
          />

          {/* ── Recent Activity ── */}
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
              <h4 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                <Activity className="w-4 h-4 text-teal-600" />
                <span>Recent Activity</span>
              </h4>
              <span className="text-[10px] text-slate-400 font-medium">
                {analyticsActivity.length} events
              </span>
            </div>

            {analyticsActivity.length === 0 ? (
              <div className="py-10 text-center text-slate-400 text-xs">
                No recent activity.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
                {analyticsActivity.map((evt) => (
                  <div
                    key={evt.id}
                    className="px-5 py-3 flex items-center justify-between hover:bg-slate-50/60 transition-colors text-xs"
                  >
                    {/* Left: event type + user + resource */}
                    <div className="flex items-center space-x-3 min-w-0">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border flex-shrink-0 ${eventColor(evt.event_type)}`}>
                        {(evt.event_type || '').replace(/_/g, ' ')}
                      </span>
                      <span className="text-slate-600 truncate max-w-[140px]" title={evt.user_email}>
                        {evt.user_email || '—'}
                      </span>
                      {evt.resource_type && (
                        <span className="text-slate-400 hidden lg:inline text-[10px]">
                          {evt.resource_type}{evt.resource_id ? ` #${evt.resource_id}` : ''}
                        </span>
                      )}
                    </div>

                    {/* Right: OK/FAIL badge + timestamp */}
                    <div className="flex items-center space-x-2 flex-shrink-0 ml-3">
                      <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold ${
                        evt.success
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-red-50 text-red-700'
                      }`}>
                        {evt.success ? 'OK' : 'FAIL'}
                      </span>
                      <span className="text-slate-400 text-[10px] whitespace-nowrap">
                        {relativeTime(evt.created_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
