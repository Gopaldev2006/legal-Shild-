import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  FileText, Sparkles, AlertTriangle, ShieldCheck, Calendar, Users,
  CheckSquare, BookOpen, Search, Loader2, ChevronDown, ChevronUp,
  AlertCircle, Info, Zap, Scale, ClipboardList, RefreshCw,
  Target, Lightbulb, FileSearch, Hash, Award, Clock, Shield, TrendingUp, XCircle
} from 'lucide-react';

// ── Structured Summary Card (Phase 2) ────────────────────────────────────────
function StructuredSummaryCard({ summary }) {
  const [showSources, setShowSources] = useState(false);

  if (!summary) return null;

  const fields = [
    {
      label: 'Document Type',
      value: summary.document_type,
      icon:  FileSearch,
      color: 'blue',
    },
    {
      label: 'Purpose',
      value: summary.purpose,
      icon:  Target,
      color: 'violet',
    },
    {
      label: 'Main Subject',
      value: summary.main_subject,
      icon:  Hash,
      color: 'indigo',
    },
  ];

  return (
    <div className="space-y-4">
      {/* Executive Summary */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
        <div className="flex items-center space-x-2 mb-2">
          <Sparkles className="w-4 h-4 text-indigo-600" />
          <span className="text-xs font-bold text-indigo-800">Executive Summary</span>
          <span className="px-2 py-0.5 bg-white border border-indigo-200 text-indigo-600 text-[10px] font-bold rounded-lg">
            {summary.provider_used}
          </span>
        </div>
        <p className="text-xs text-slate-800 leading-relaxed">
          {summary.executive_summary || 'Not clearly specified in the document.'}
        </p>
      </div>

      {/* 3-field metadata grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {fields.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className={`bg-${color}-50 border border-${color}-200 rounded-xl p-3`}>
            <div className="flex items-center space-x-1.5 mb-1.5">
              <Icon className={`w-3.5 h-3.5 text-${color}-600`} />
              <span className={`text-[10px] font-bold text-${color}-700 uppercase tracking-wide`}>
                {label}
              </span>
            </div>
            <p className="text-xs text-slate-800 leading-relaxed">
              {value || 'Not clearly specified in the document.'}
            </p>
          </div>
        ))}
      </div>

      {/* Key Takeaways */}
      {summary.key_takeaways && summary.key_takeaways.length > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
          <div className="flex items-center space-x-2 mb-2.5">
            <Lightbulb className="w-4 h-4 text-emerald-600" />
            <span className="text-xs font-bold text-emerald-800">
              Key Takeaways ({summary.key_takeaways.length})
            </span>
          </div>
          <ul className="space-y-1.5">
            {summary.key_takeaways.map((t, i) => (
              <li key={i} className="flex items-start space-x-2 text-xs text-slate-800">
                <span className="w-4 h-4 flex-shrink-0 rounded-full bg-emerald-600 text-white text-[9px] font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <span className="leading-relaxed">{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sources */}
      {summary.sources && summary.sources.length > 0 && (
        <div>
          <button
            onClick={() => setShowSources(v => !v)}
            className="flex items-center space-x-2 text-[11px] font-bold text-slate-600 hover:text-slate-900 transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Sources ({summary.sources.length} chunks used)</span>
            {showSources
              ? <ChevronUp className="w-3 h-3" />
              : <ChevronDown className="w-3 h-3" />}
          </button>
          {showSources && (
            <div className="mt-2 space-y-1">
              {summary.sources.map((src, i) => (
                <div key={i}
                  className="flex items-center space-x-2 text-[10px] text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 font-mono">
                  <FileText className="w-3 h-3 text-indigo-400 flex-shrink-0" />
                  <span>Page {src.page_number ?? 'N/A'}</span>
                  <span className="text-slate-400">·</span>
                  <span className="truncate">{src.chunk_id}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Structured Clauses Card (Phase 3) ────────────────────────────────────────
function StructuredClausesCard({ clauses }) {
  if (!clauses || clauses.length === 0) {
    return <p className="text-xs text-slate-400 italic">No important clauses identified.</p>;
  }

  const importanceColors = {
    high:   { bg: 'bg-red-50',    border: 'border-red-200',    badge: 'bg-red-100 text-red-700',       dot: 'bg-red-500' },
    medium: { bg: 'bg-amber-50',  border: 'border-amber-200',  badge: 'bg-amber-100 text-amber-700',   dot: 'bg-amber-500' },
    low:    { bg: 'bg-slate-50',  border: 'border-slate-200',  badge: 'bg-slate-100 text-slate-700',   dot: 'bg-slate-400' },
  };

  return (
    <div className="space-y-3">
      {clauses.map((clause, i) => {
        const colors = importanceColors[clause.importance] || importanceColors.medium;
        return (
          <div key={i} className={`${colors.bg} ${colors.border} border rounded-xl p-3`}>
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex items-center space-x-2">
                <Award className={`w-3.5 h-3.5 ${colors.dot.replace('bg-', 'text-')}`} />
                <span className="text-xs font-bold text-slate-900">{clause.title}</span>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${colors.badge}`}>
                {clause.importance}
              </span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed mb-2">
              {clause.description}
            </p>
            <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
              <FileText className="w-3 h-3 text-violet-400 flex-shrink-0" />
              <span>Page {clause.source?.page_number ?? 'N/A'}</span>
              <span className="text-slate-300">·</span>
              <span className="truncate text-[9px]">{clause.source?.chunk_id || 'unknown'}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Structured Obligations Card (Phase 3) ────────────────────────────────────
function StructuredObligationsCard({ obligations }) {
  if (!obligations || obligations.length === 0) {
    return <p className="text-xs text-slate-400 italic">No obligations identified.</p>;
  }

  return (
    <div className="space-y-3">
      {obligations.map((obl, i) => (
        <div key={i} className="bg-emerald-50 border border-emerald-200 rounded-xl p-3">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center space-x-2">
              <CheckSquare className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-xs font-bold text-slate-900">{obl.party}</span>
            </div>
            <div className="flex items-center space-x-1.5 text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-0.5">
              <Clock className="w-3 h-3" />
              <span>{obl.deadline}</span>
            </div>
          </div>
          <p className="text-xs text-slate-700 leading-relaxed mb-2">
            {obl.obligation}
          </p>
          <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
            <FileText className="w-3 h-3 text-emerald-400 flex-shrink-0" />
            <span>Page {obl.source?.page_number ?? 'N/A'}</span>
            <span className="text-slate-300">·</span>
            <span className="truncate text-[9px]">{obl.source?.chunk_id || 'unknown'}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Risk Assessment Card (Phase 4) ────────────────────────────────────────────
function RiskAssessmentCard({ assessment }) {
  const [showFactors, setShowFactors] = useState(false);

  if (!assessment) {
    return <p className="text-xs text-slate-400 italic">No risk assessment available.</p>;
  }

  // Overall risk level colors
  const overallColors = {
    'Low':      { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', badge: 'bg-emerald-100 text-emerald-800', icon: 'text-emerald-600' },
    'Moderate': { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700',   badge: 'bg-amber-100 text-amber-800',   icon: 'text-amber-600' },
    'High':     { bg: 'bg-red-50',     border: 'border-red-200',     text: 'text-red-700',     badge: 'bg-red-100 text-red-800',     icon: 'text-red-600' },
  };

  const overall = overallColors[assessment.overall_risk] || overallColors['Moderate'];

  // Severity colors for individual risks
  const severityColors = {
    high:   { bg: 'bg-red-50',    border: 'border-red-200',    badge: 'bg-red-100 text-red-700',       dot: 'bg-red-500',    icon: 'text-red-600' },
    medium: { bg: 'bg-amber-50',  border: 'border-amber-200',  badge: 'bg-amber-100 text-amber-700',   dot: 'bg-amber-500',  icon: 'text-amber-600' },
    low:    { bg: 'bg-blue-50',   border: 'border-blue-200',   badge: 'bg-blue-100 text-blue-700',     dot: 'bg-blue-500',   icon: 'text-blue-600' },
  };

  // Group risks by severity
  const highRisks = assessment.risks.filter(r => r.severity === 'high');
  const mediumRisks = assessment.risks.filter(r => r.severity === 'medium');
  const lowRisks = assessment.risks.filter(r => r.severity === 'low');

  return (
    <div className="space-y-4">
      {/* Overall Risk Header */}
      <div className={`${overall.bg} ${overall.border} border rounded-xl p-4`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Shield className={`w-5 h-5 ${overall.icon}`} />
            <span className="text-sm font-bold text-slate-900">Overall Risk Assessment</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className={`px-3 py-1 rounded-full text-xs font-bold ${overall.badge}`}>
              {assessment.overall_risk.toUpperCase()}
            </span>
            <span className="px-2 py-1 bg-white border border-slate-200 text-slate-600 text-[10px] font-mono rounded-lg">
              Score: {assessment.risk_score.toFixed(1)}/10
            </span>
          </div>
        </div>
        
        {/* Provider */}
        <div className="flex items-center justify-between">
          <span className="px-2 py-0.5 bg-white border border-slate-200 text-slate-600 text-[10px] font-bold rounded-lg">
            {assessment.provider_used}
          </span>
          <button
            onClick={() => setShowFactors(v => !v)}
            className="text-[11px] font-bold text-slate-600 hover:text-slate-900 flex items-center space-x-1"
          >
            <span>Contributing Factors ({assessment.factors.length})</span>
            {showFactors ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>

        {/* Factors */}
        {showFactors && assessment.factors.length > 0 && (
          <div className="mt-3 space-y-1">
            {assessment.factors.map((factor, i) => (
              <div key={i} className="flex items-start space-x-2 text-xs text-slate-700">
                <TrendingUp className="w-3 h-3 text-slate-400 flex-shrink-0 mt-0.5" />
                <span>{factor}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* AI Disclaimer */}
      <div className="flex items-start space-x-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
        <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
        <span className="text-[10px] text-amber-800">
          AI-assisted risk indicator only. Not definitive legal advice. Consult a qualified legal professional.
        </span>
      </div>

      {/* Risk Categories Grid */}
      <div className="grid grid-cols-1 gap-4">
        {/* High Risks */}
        {highRisks.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <XCircle className="w-4 h-4 text-red-600" />
              <span className="text-xs font-bold text-red-900">High Risk ({highRisks.length})</span>
            </div>
            {highRisks.map((risk, i) => (
              <RiskCard key={i} risk={risk} colors={severityColors.high} />
            ))}
          </div>
        )}

        {/* Medium Risks */}
        {mediumRisks.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span className="text-xs font-bold text-amber-900">Medium Risk ({mediumRisks.length})</span>
            </div>
            {mediumRisks.map((risk, i) => (
              <RiskCard key={i} risk={risk} colors={severityColors.medium} />
            ))}
          </div>
        )}

        {/* Low Risks */}
        {lowRisks.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <Info className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-bold text-blue-900">Low Risk ({lowRisks.length})</span>
            </div>
            {lowRisks.map((risk, i) => (
              <RiskCard key={i} risk={risk} colors={severityColors.low} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Individual Risk Card Component
function RiskCard({ risk, colors }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`${colors.bg} ${colors.border} border rounded-lg p-3`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-xs font-bold text-slate-900">{risk.title}</span>
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${colors.badge}`}>
              {risk.category}
            </span>
          </div>
          <p className="text-xs text-slate-700 leading-relaxed">
            {risk.description}
          </p>
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-slate-400 hover:text-slate-600 flex-shrink-0"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="space-y-2 mt-3 pt-3 border-t border-slate-200">
          {/* Reason */}
          <div>
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Why Risky</span>
            <p className="text-xs text-slate-700 mt-1">{risk.reason}</p>
          </div>

          {/* Evidence */}
          <div>
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Evidence</span>
            <div className="bg-white border border-slate-200 rounded p-2 mt-1">
              <p className="text-[11px] text-slate-600 font-mono leading-relaxed">"{risk.evidence}"</p>
            </div>
          </div>

          {/* Confidence + Source */}
          <div className="flex items-center justify-between text-[10px]">
            <div className="flex items-center space-x-2 text-slate-500">
              <FileText className="w-3 h-3 text-slate-400 flex-shrink-0" />
              <span>Page {risk.source?.page_number ?? 'N/A'}</span>
              <span className="text-slate-300">·</span>
              <span className="truncate font-mono text-[9px]">{risk.source?.chunk_id || 'unknown'}</span>
            </div>
            <div className="flex items-center space-x-1">
              <span className="text-slate-500">Confidence:</span>
              <span className="font-bold text-slate-700">{(risk.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Missing & Ambiguous Clause Card (Phase 5) ─────────────────────────────────
function MissingAmbiguousCard({ analysis }) {
  if (!analysis) {
    return <p className="text-xs text-slate-400 italic">No missing/ambiguous clause analysis available.</p>;
  }

  const importanceColors = {
    high:   { bg: 'bg-red-50',    border: 'border-red-200',    badge: 'bg-red-100 text-red-700',       dot: 'bg-red-500' },
    medium: { bg: 'bg-amber-50',  border: 'border-amber-200',  badge: 'bg-amber-100 text-amber-700',   dot: 'bg-amber-500' },
    low:    { bg: 'bg-blue-50',   border: 'border-blue-200',   badge: 'bg-blue-100 text-blue-700',     dot: 'bg-blue-500' },
  };

  return (
    <div className="space-y-4">
      {/* Document Type Detection Header */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FileSearch className="w-5 h-5 text-indigo-600" />
            <span className="text-sm font-bold text-slate-900">Document Type Analysis</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="px-3 py-1 bg-indigo-100 text-indigo-800 text-xs font-bold rounded-full">
              {analysis.document_type}
            </span>
            <span className="px-2 py-1 bg-white border border-slate-200 text-slate-600 text-[10px] font-mono rounded-lg">
              {(analysis.document_type_confidence * 100).toFixed(0)}% confident
            </span>
          </div>
        </div>
        <div className="mt-2">
          <span className="px-2 py-0.5 bg-white border border-indigo-200 text-indigo-600 text-[10px] font-bold rounded-lg">
            {analysis.provider_used}
          </span>
        </div>
      </div>

      {/* AI Disclaimer */}
      <div className="flex items-start space-x-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
        <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
        <span className="text-[10px] text-amber-800">
          Missing clauses do not automatically make a document illegal or invalid. Consult a legal professional for case-specific guidance.
        </span>
      </div>

      {/* Missing Clauses Section */}
      {analysis.missing_clauses && analysis.missing_clauses.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <Search className="w-4 h-4 text-orange-600" />
            <span className="text-xs font-bold text-orange-900">
              Potentially Missing Clauses ({analysis.missing_clauses.length})
            </span>
          </div>
          {analysis.missing_clauses.map((mc, i) => {
            const colors = importanceColors[mc.importance] || importanceColors.medium;
            return (
              <MissingClauseCard key={i} clause={mc} colors={colors} />
            );
          })}
        </div>
      )}

      {/* Ambiguous Language Section */}
      {analysis.ambiguous_clauses && analysis.ambiguous_clauses.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span className="text-xs font-bold text-amber-900">
              Ambiguous Language ({analysis.ambiguous_clauses.length})
            </span>
          </div>
          {analysis.ambiguous_clauses.map((ac, i) => (
            <AmbiguousClauseCard key={i} clause={ac} />
          ))}
        </div>
      )}

      {/* Conflicting Provisions Section */}
      {analysis.conflicts && analysis.conflicts.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <XCircle className="w-4 h-4 text-red-600" />
            <span className="text-xs font-bold text-red-900">
              Potential Conflicts ({analysis.conflicts.length})
            </span>
          </div>
          {analysis.conflicts.map((conflict, i) => (
            <ConflictCard key={i} conflict={conflict} />
          ))}
        </div>
      )}
    </div>
  );
}

// Individual Missing Clause Card
function MissingClauseCard({ clause, colors }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`${colors.bg} ${colors.border} border rounded-lg p-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-xs font-bold text-slate-900">{clause.clause}</span>
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${colors.badge}`}>
              {clause.importance}
            </span>
            <span className="px-2 py-0.5 bg-white border border-slate-200 text-slate-600 text-[9px] font-bold rounded-lg">
              {clause.status.replace('_', ' ').toUpperCase()}
            </span>
          </div>
          {expanded && (
            <div className="mt-2 space-y-2">
              <div>
                <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Explanation</span>
                <p className="text-xs text-slate-700 mt-1">{clause.explanation}</p>
              </div>
              <div className="flex items-center space-x-1 text-[10px]">
                <span className="text-slate-500">Confidence:</span>
                <span className="font-bold text-slate-700">{(clause.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-slate-400 hover:text-slate-600 flex-shrink-0"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}

// Individual Ambiguous Clause Card
function AmbiguousClauseCard({ clause }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-xs font-bold text-slate-900">{clause.clause}</span>
            <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-[9px] font-bold uppercase">
              {clause.issue_type}
            </span>
          </div>
          <div className="bg-white border border-amber-200 rounded p-2 mb-2">
            <p className="text-[11px] text-slate-700 font-mono leading-relaxed">"{clause.text}"</p>
          </div>
          <p className="text-xs text-slate-700">{clause.explanation}</p>
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-slate-400 hover:text-slate-600 flex-shrink-0"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="space-y-2 mt-3 pt-3 border-t border-amber-200">
          {/* Suggested Clarification */}
          <div>
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Suggested Clarification</span>
            <div className="bg-emerald-50 border border-emerald-200 rounded p-2 mt-1">
              <p className="text-xs text-emerald-800">{clause.suggested_clarification}</p>
            </div>
          </div>

          {/* Source */}
          <div className="flex items-center space-x-2 text-[10px] text-slate-500">
            <FileText className="w-3 h-3 text-slate-400 flex-shrink-0" />
            <span>Page {clause.source?.page_number ?? 'N/A'}</span>
            <span className="text-slate-300">·</span>
            <span className="truncate font-mono text-[9px]">{clause.source?.chunk_id || 'unknown'}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// Individual Conflict Card
function ConflictCard({ conflict }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-xs font-bold text-slate-900">{conflict.clause}</span>
            <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-[9px] font-bold uppercase">
              {conflict.issue_type}
            </span>
          </div>
          <p className="text-xs text-slate-700 mb-2">{conflict.explanation}</p>
          
          {/* Preview of both provisions */}  
          <div className="space-y-1.5">
            <div className="bg-white border border-red-200 rounded p-2">
              <div className="text-[9px] font-bold text-red-600 mb-0.5">Provision 1</div>
              <p className="text-[11px] text-slate-700 font-mono">"{conflict.text_1}"</p>
            </div>
            <div className="bg-white border border-red-200 rounded p-2">
              <div className="text-[9px] font-bold text-red-600 mb-0.5">Provision 2</div>
              <p className="text-[11px] text-slate-700 font-mono">"{conflict.text_2}"</p>
            </div>
          </div>
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-slate-400 hover:text-slate-600 flex-shrink-0"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="space-y-2 mt-3 pt-3 border-t border-red-200">
          {/* Sources */}
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="flex items-center space-x-1 text-slate-500">
              <FileText className="w-3 h-3 text-slate-400 flex-shrink-0" />
              <span>Page {conflict.source_1?.page_number ?? 'N/A'}</span>
            </div>
            <div className="flex items-center space-x-1 text-slate-500">
              <FileText className="w-3 h-3 text-slate-400 flex-shrink-0" />
              <span>Page {conflict.source_2?.page_number ?? 'N/A'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Parties Card (Phase 6) ────────────────────────────────────────────────────
function PartiesCard({ entities }) {
  if (!entities || !entities.parties || entities.parties.length === 0) {
    return <p className="text-xs text-slate-400 italic">No parties extracted from the document.</p>;
  }

  return (
    <div className="space-y-3">
      {/* Provider badge */}
      <div className="flex items-center justify-end">
        <span className="px-2 py-0.5 bg-white border border-slate-200 text-slate-600 text-[10px] font-bold rounded-lg">
          {entities.provider_used}
        </span>
      </div>

      {/* Parties grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {entities.parties.map((party, i) => (
          <PartyCard key={i} party={party} />
        ))}
      </div>
    </div>
  );
}

function PartyCard({ party }) {
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <Users className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-bold text-slate-900">{party.name}</span>
          </div>
          {party.role && (
            <span className="inline-block px-2 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-bold rounded-full">
              {party.role}
            </span>
          )}
        </div>
        {party.evidence && (
          <button
            onClick={() => setShowEvidence(v => !v)}
            className="text-slate-400 hover:text-slate-600 flex-shrink-0"
            title="Show evidence"
          >
            {showEvidence ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* Source reference */}
      <div className="flex items-center space-x-2 text-[10px] text-slate-500 mt-2">
        <FileText className="w-3 h-3 text-slate-400" />
        <span>Page {party.source?.page_number ?? 'N/A'}</span>
        <span className="text-slate-300">·</span>
        <span className="font-mono text-[9px]">{party.source?.chunk_id || 'unknown'}</span>
      </div>

      {/* Evidence quote */}
      {showEvidence && party.evidence && (
        <div className="mt-3 pt-3 border-t border-blue-200">
          <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Evidence</span>
          <div className="bg-white border border-blue-200 rounded p-2 mt-1">
            <p className="text-[11px] text-slate-700 leading-relaxed">"{party.evidence}"</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Key Dates Card (Phase 6) ──────────────────────────────────────────────────
function DatesCard({ entities }) {
  if (!entities || !entities.key_dates || entities.key_dates.length === 0) {
    return <p className="text-xs text-slate-400 italic">No key dates extracted from the document.</p>;
  }

  // Group dates by type
  const datesByType = {};
  entities.key_dates.forEach(date => {
    const type = date.type || 'Other';
    if (!datesByType[type]) {
      datesByType[type] = [];
    }
    datesByType[type].push(date);
  });

  return (
    <div className="space-y-3">
      {/* Provider badge */}
      <div className="flex items-center justify-end">
        <span className="px-2 py-0.5 bg-white border border-slate-200 text-slate-600 text-[10px] font-bold rounded-lg">
          {entities.provider_used}
        </span>
      </div>

      {/* Dates by type */}
      <div className="space-y-3">
        {Object.entries(datesByType).map(([type, dates]) => (
          <div key={type} className="space-y-2">
            <div className="flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-amber-600" />
              <span className="text-xs font-bold text-amber-900">{type} ({dates.length})</span>
            </div>
            <div className="space-y-2">
              {dates.map((date, i) => (
                <DateCard key={i} date={date} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DateCard({ date }) {
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            <span className="text-sm font-bold text-slate-900">{date.date}</span>
          </div>

          {/* Source reference */}
          <div className="flex items-center space-x-2 text-[10px] text-slate-500 mt-1">
            <FileText className="w-3 h-3 text-slate-400" />
            <span>Page {date.source?.page_number ?? 'N/A'}</span>
            <span className="text-slate-300">·</span>
            <span className="font-mono text-[9px]">{date.source?.chunk_id || 'unknown'}</span>
          </div>
        </div>

        {date.evidence && (
          <button
            onClick={() => setShowEvidence(v => !v)}
            className="text-slate-400 hover:text-slate-600 flex-shrink-0"
            title="Show evidence"
          >
            {showEvidence ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* Evidence quote */}
      {showEvidence && date.evidence && (
        <div className="mt-3 pt-3 border-t border-amber-200">
          <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Evidence</span>
          <div className="bg-white border border-amber-200 rounded p-2 mt-1">
            <p className="text-[11px] text-slate-700 leading-relaxed">"{date.evidence}"</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Enhanced Obligations Card (Phase 6) ───────────────────────────────────────
function EnhancedObligationsCard({ entities }) {
  if (!entities || !entities.obligations || entities.obligations.length === 0) {
    return <p className="text-xs text-slate-400 italic">No obligations extracted from the document.</p>;
  }

  // Group by party
  const byParty = {};
  entities.obligations.forEach(obl => {
    const party = obl.party || 'Unknown Party';
    if (!byParty[party]) {
      byParty[party] = [];
    }
    byParty[party].push(obl);
  });

  return (
    <div className="space-y-4">
      {/* Provider badge */}
      <div className="flex items-center justify-end">
        <span className="px-2 py-0.5 bg-white border border-slate-200 text-slate-600 text-[10px] font-bold rounded-lg">
          {entities.provider_used}
        </span>
      </div>

      {/* Obligations by party */}
      {Object.entries(byParty).map(([party, obligations]) => (
        <div key={party} className="space-y-2">
          <div className="flex items-center space-x-2">
            <CheckSquare className="w-4 h-4 text-emerald-600" />
            <span className="text-xs font-bold text-emerald-900">{party} ({obligations.length})</span>
          </div>
          <div className="space-y-2">
            {obligations.map((obl, i) => (
              <EnhancedObligationCard key={i} obligation={obl} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function EnhancedObligationCard({ obligation }) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <p className="text-xs text-slate-800 font-medium mb-2">{obligation.obligation}</p>

          <div className="flex items-center space-x-3 text-[10px] text-slate-600">
            {obligation.deadline && obligation.deadline !== 'Not specified' && (
              <div className="flex items-center space-x-1">
                <Clock className="w-3 h-3 text-emerald-600" />
                <span>{obligation.deadline}</span>
              </div>
            )}
            {obligation.condition && (
              <div className="flex items-center space-x-1">
                <Info className="w-3 h-3 text-emerald-600" />
                <span className="italic">{obligation.condition}</span>
              </div>
            )}
          </div>
        </div>

        <button
          onClick={() => setShowDetails(v => !v)}
          className="text-slate-400 hover:text-slate-600 flex-shrink-0"
          title="Show details"
        >
          {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expanded details */}
      {showDetails && (
        <div className="mt-3 pt-3 border-t border-emerald-200 space-y-2">
          {/* Evidence */}
          {obligation.evidence && (
            <div>
              <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">Evidence</span>
              <div className="bg-white border border-emerald-200 rounded p-2 mt-1">
                <p className="text-[11px] text-slate-700 leading-relaxed">"{obligation.evidence}"</p>
              </div>
            </div>
          )}

          {/* Source */}
          <div className="flex items-center space-x-2 text-[10px] text-slate-500">
            <FileText className="w-3 h-3 text-slate-400" />
            <span>Page {obligation.source?.page_number ?? 'N/A'}</span>
            <span className="text-slate-300">·</span>
            <span className="font-mono text-[9px]">{obligation.source?.chunk_id || 'unknown'}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Section config ────────────────────────────────────────────────────────────
const SECTIONS = [
  {
    key:         'structured_summary',
    label:       'Document Summary',
    icon:        Sparkles,
    color:       'indigo',
    type:        'summary',    // ← handled by StructuredSummaryCard
    description: 'Executive summary, type, purpose, subject, key takeaways',
  },
  {
    key:         'structured_risk_assessment',
    label:       'Risk Assessment',
    icon:        Shield,
    color:       'red',
    type:        'risk_assessment', // ← Phase 4: handled by RiskAssessmentCard
    description: 'AI-assisted legal risk analysis with severity and confidence',
  },
  {
    key:         'structured_clauses',
    label:       'Important Clauses',
    icon:        ClipboardList,
    color:       'violet',
    type:        'clauses',    // ← Phase 3: handled by StructuredClausesCard
    description: 'Key contractual provisions with importance classification',
  },
  {
    key:         'structured_obligations',
    label:       'Obligations',
    icon:        CheckSquare,
    color:       'emerald',
    type:        'obligations', // ← Phase 3: handled by StructuredObligationsCard
    description: 'What each party must do with deadlines',
  },
  {
    key:         'structured_entities',
    label:       'Parties & Entities',
    icon:        Users,
    color:       'blue',
    type:        'parties',  // ← Phase 6: handled by PartiesCard
    subtype:     'parties',
    description: 'Extracted parties with roles and evidence',
  },
  {
    key:         'structured_entities',
    label:       'Key Dates',
    icon:        Calendar,
    color:       'amber',
    type:        'dates',    // ← Phase 6: handled by DatesCard
    subtype:     'dates',
    description: 'Important dates with types and sources',
  },
  {
    key:         'structured_entities',
    label:       'Obligations',
    icon:        CheckSquare,
    color:       'emerald',
    type:        'enhanced_obligations', // ← Phase 6: handled by EnhancedObligationsCard
    subtype:     'obligations',
    description: 'Party obligations with deadlines and evidence',
  },
  {
    key:         'structured_missing_ambiguous',
    label:       'Missing & Ambiguous Clauses',
    icon:        Search,
    color:       'orange',
    type:        'missing_ambiguous', // ← Phase 5: handled by MissingAmbiguousCard
    description: 'Document type detection, potentially missing clauses, ambiguous language, conflicts',
  },
  {
    key:   'citations',
    label: 'Evidence & Citations',
    icon:  BookOpen,
    color: 'teal',
    type:  'list',
    description: 'Statutes, case law, clause references',
  },
];

const COLOR_CLASSES = {
  indigo: { bg: 'bg-indigo-50', border: 'border-indigo-200', icon: 'text-indigo-600', badge: 'bg-indigo-100 text-indigo-700', dot: 'bg-indigo-500' },
  blue:   { bg: 'bg-blue-50',   border: 'border-blue-200',   icon: 'text-blue-600',   badge: 'bg-blue-100 text-blue-700',   dot: 'bg-blue-500' },
  violet: { bg: 'bg-violet-50', border: 'border-violet-200', icon: 'text-violet-600', badge: 'bg-violet-100 text-violet-700', dot: 'bg-violet-500' },
  emerald:{ bg: 'bg-emerald-50',border: 'border-emerald-200',icon: 'text-emerald-600',badge: 'bg-emerald-100 text-emerald-700', dot: 'bg-emerald-500' },
  amber:  { bg: 'bg-amber-50',  border: 'border-amber-200',  icon: 'text-amber-600',  badge: 'bg-amber-100 text-amber-700',  dot: 'bg-amber-500' },
  red:    { bg: 'bg-red-50',    border: 'border-red-200',    icon: 'text-red-600',    badge: 'bg-red-100 text-red-700',    dot: 'bg-red-500' },
  orange: { bg: 'bg-orange-50', border: 'border-orange-200', icon: 'text-orange-600', badge: 'bg-orange-100 text-orange-700', dot: 'bg-orange-500' },
  teal:   { bg: 'bg-teal-50',   border: 'border-teal-200',   icon: 'text-teal-600',   badge: 'bg-teal-100 text-teal-700',   dot: 'bg-teal-500' },
};

// ── Section card ──────────────────────────────────────────────────────────────
function SectionCard({ section, data }) {
  const [open, setOpen] = useState(true);
  const c     = COLOR_CLASSES[section.color];
  const Icon  = section.icon;
  const items = Array.isArray(data) ? data : [];
  const isEmpty = section.type === 'list'
    ? items.length === 0
    : section.type === 'summary'
      ? !data
      : section.type === 'clauses' || section.type === 'obligations'
        ? !data || data.length === 0
        : section.type === 'risk_assessment'
          ? !data || !data.risks || data.risks.length === 0
          : section.type === 'missing_ambiguous'
            ? !data || (!data.missing_clauses?.length && !data.ambiguous_clauses?.length && !data.conflicts?.length)
            : section.type === 'parties'
              ? !data || !data.parties || data.parties.length === 0
              : section.type === 'dates'
                ? !data || !data.key_dates || data.key_dates.length === 0
                : section.type === 'enhanced_obligations'
                  ? !data || !data.obligations || data.obligations.length === 0
                  : !data || String(data).trim() === '';

  // Count for badge
  let count = 0;
  if (section.type === 'list') count = items.length;
  else if (section.type === 'clauses' || section.type === 'obligations') count = data?.length || 0;
  else if (section.type === 'risk_assessment') count = data?.risks?.length || 0;
  else if (section.type === 'missing_ambiguous') {
    count = (data?.missing_clauses?.length || 0) + (data?.ambiguous_clauses?.length || 0) + (data?.conflicts?.length || 0);
  }
  else if (section.type === 'parties') count = data?.parties?.length || 0;
  else if (section.type === 'dates') count = data?.key_dates?.length || 0;
  else if (section.type === 'enhanced_obligations') count = data?.obligations?.length || 0;

  return (
    <div className={`border ${c.border} rounded-2xl overflow-hidden shadow-sm`}>
      {/* Header */}
      <button
        onClick={() => setOpen(v => !v)}
        className={`w-full flex items-center justify-between px-4 py-3 ${c.bg} hover:brightness-95 transition-all`}
      >
        <div className="flex items-center space-x-2.5">
          <div className={`p-1.5 rounded-lg bg-white shadow-sm ${c.border} border`}>
            <Icon className={`w-4 h-4 ${c.icon}`} />
          </div>
          <div className="text-left">
            <p className="text-sm font-bold text-slate-900">{section.label}</p>
            <p className="text-[10px] text-slate-500">{section.description}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {(section.type === 'list' || section.type === 'clauses' || section.type === 'obligations' || section.type === 'risk_assessment' || section.type === 'missing_ambiguous' || section.type === 'parties' || section.type === 'dates' || section.type === 'enhanced_obligations') && (
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${c.badge}`}>
              {count}
            </span>
          )}
          {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </button>

      {/* Body */}
      {open && (
        <div className="px-4 py-3 bg-white">
          {isEmpty ? (
            <p className="text-xs text-slate-400 italic">No data found for this section.</p>
          ) : section.type === 'summary' ? (
            /* Phase 2: structured summary */
            <StructuredSummaryCard summary={data} />
          ) : section.type === 'risk_assessment' ? (
            /* Phase 4: risk assessment */
            <RiskAssessmentCard assessment={data} />
          ) : section.type === 'missing_ambiguous' ? (
            /* Phase 5: missing & ambiguous clauses */
            <MissingAmbiguousCard analysis={data} />
          ) : section.type === 'parties' ? (
            /* Phase 6: parties */
            <PartiesCard entities={data} />
          ) : section.type === 'dates' ? (
            /* Phase 6: key dates */
            <DatesCard entities={data} />
          ) : section.type === 'enhanced_obligations' ? (
            /* Phase 6: enhanced obligations */
            <EnhancedObligationsCard entities={data} />
          ) : section.type === 'clauses' ? (
            /* Phase 3: structured clauses */
            <StructuredClausesCard clauses={data} />
          ) : section.type === 'obligations' ? (
            /* Phase 3: structured obligations */
            <StructuredObligationsCard obligations={data} />
          ) : section.type === 'text' ? (
            <p className="text-xs text-slate-800 leading-relaxed">{data}</p>
          ) : (
            <ul className="space-y-2">
              {items.map((item, i) => (
                <li key={i} className="flex items-start space-x-2.5 text-xs text-slate-800">
                  <span className={`w-1.5 h-1.5 rounded-full ${c.dot} flex-shrink-0 mt-1.5`} />
                  <span className="leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ── Loading steps ─────────────────────────────────────────────────────────────
const STEPS = [
  'Extracting document text...',
  'Identifying parties and clauses...',
  'Analysing risks and obligations...',
  'Compiling structured report...',
];

function LoadingSteps({ step }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-6">
      <div className="p-4 bg-indigo-50 border border-indigo-100 rounded-2xl">
        <Sparkles className="w-10 h-10 text-indigo-600 animate-pulse" />
      </div>
      <div className="space-y-3 w-64">
        {STEPS.map((s, i) => {
          const done   = i < step;
          const active = i === step;
          return (
            <div key={i} className={`flex items-center space-x-2.5 transition-opacity ${active ? 'opacity-100' : done ? 'opacity-60' : 'opacity-25'}`}>
              {done ? (
                <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
              ) : active ? (
                <Loader2 className="w-4 h-4 text-indigo-500 animate-spin flex-shrink-0" />
              ) : (
                <div className="w-4 h-4 rounded-full border border-slate-300 flex-shrink-0" />
              )}
              <span className={`text-xs font-medium ${active ? 'text-indigo-700' : done ? 'text-emerald-700' : 'text-slate-400'}`}>{s}</span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-slate-400">This may take a few seconds...</p>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function DocumentAnalysisPanel({ documents = [] }) {
  const { token } = useAuth();
  const [selectedDocId, setSelectedDocId] = useState('');
  const [analysis,      setAnalysis]      = useState(null);
  const [loading,       setLoading]       = useState(false);
  const [loadStep,      setLoadStep]      = useState(0);
  const [error,         setError]         = useState(null);

  const selectedDoc = documents.find(d => String(d.id) === String(selectedDocId));
  const readyDocs   = documents.filter(d =>
    d.processing_status === 'READY' || d.processing_status === 'COMPLETED'
  );

  const runAnalysis = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    setError(null);
    setAnalysis(null);
    setLoadStep(0);

    // Animate through steps while waiting
    const stepInterval = setInterval(() => {
      setLoadStep(prev => Math.min(prev + 1, STEPS.length - 1));
    }, 900);

    try {
      const res  = await fetch(`/api/v1/documents/${selectedDocId}/analyze`, {
        method:  'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      clearInterval(stepInterval);

      if (!res.ok) {
        throw new Error(data.detail || 'Analysis failed');
      }
      setAnalysis(data);
    } catch (err) {
      clearInterval(stepInterval);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">

      {/* ── Header ── */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-50 border border-indigo-100 rounded-xl">
              <Scale className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">Document Analysis Engine</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                AI-powered structured legal analysis — 8 sections
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-[11px] text-slate-500">
            <Zap className="w-3.5 h-3.5 text-indigo-500" />
            <span>Gemini AI · Free Engine fallback</span>
          </div>
        </div>

        {/* Document selector + button */}
        <div className="mt-4 flex items-center space-x-3">
          <div className="flex-grow">
            <label className="block text-[11px] font-bold text-slate-600 mb-1.5">
              Select Document to Analyse
            </label>
            {readyDocs.length === 0 ? (
              <div className="flex items-center space-x-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5 text-xs text-amber-800">
                <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                <span>No ready documents found. Upload a PDF/DOCX in the Documents tab first.</span>
              </div>
            ) : (
              <select
                value={selectedDocId}
                onChange={e => { setSelectedDocId(e.target.value); setAnalysis(null); setError(null); }}
                className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-medium"
              >
                <option value="">— Choose a document —</option>
                {readyDocs.map(d => (
                  <option key={d.id} value={d.id}>
                    {d.filename}  ({d.chunk_count} chunks · {d.embedded_count} embedded)
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="pt-5">
            <button
              onClick={runAnalysis}
              disabled={!selectedDocId || loading}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center space-x-2 transition-all disabled:opacity-50 shadow-md shadow-indigo-600/20 whitespace-nowrap"
            >
              {loading
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Sparkles className="w-3.5 h-3.5" />
              }
              <span>{loading ? 'Analysing...' : 'Analyse Document'}</span>
            </button>
          </div>
        </div>

        {/* Selected doc info */}
        {selectedDoc && !loading && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] font-medium">
            <span className="px-2.5 py-1 bg-slate-100 text-slate-700 border border-slate-200 rounded-lg">
              📄 {selectedDoc.filename}
            </span>
            <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-lg">
              {selectedDoc.chunk_count} chunks
            </span>
            <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-100 rounded-lg">
              {selectedDoc.embedded_count} embeddings
            </span>
            {selectedDoc.jurisdiction && (
              <span className="px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-100 rounded-lg">
                ⚖️ {selectedDoc.jurisdiction}
              </span>
            )}
            {selectedDoc.matter_id && (
              <span className="px-2.5 py-1 bg-slate-100 text-slate-600 border border-slate-200 rounded-lg font-mono">
                {selectedDoc.matter_id}
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-center space-x-2 text-xs text-red-800">
          <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm">
          <LoadingSteps step={loadStep} />
        </div>
      )}

      {/* ── Analysis Result ── */}
      {analysis && !loading && (
        <>
          {/* Result header */}
          <div className="bg-gradient-to-r from-indigo-50 to-violet-50 border border-indigo-200 rounded-2xl px-5 py-4 flex items-center justify-between shadow-sm">
            <div className="flex items-center space-x-3">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              <div>
                <p className="text-sm font-extrabold text-slate-900">Analysis Complete</p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {analysis.filename} · {analysis.document_type.replace(/_/g,' ')}
                  {analysis.jurisdiction ? ` · ${analysis.jurisdiction}` : ''}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <span className="px-2.5 py-1 bg-white border border-indigo-200 text-indigo-700 text-[10px] font-bold rounded-lg flex items-center space-x-1">
                <Sparkles className="w-3 h-3" />
                <span>{analysis.provider_used}</span>
              </span>
              <button
                onClick={runAnalysis}
                className="p-1.5 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500 transition-colors"
                title="Re-run analysis"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* 8 sections grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {SECTIONS.map(section => (
              <div key={section.key}
                className={
                  section.type === 'summary' || section.type === 'risk_assessment' || section.type === 'missing_ambiguous'
                    ? 'lg:col-span-2'
                    : section.type === 'clauses' || section.type === 'obligations'
                      ? 'lg:col-span-1'
                      : ''
                }>
                <SectionCard
                  section={section}
                  data={analysis[section.key]}
                />
              </div>
            ))}
          </div>

          {/* Disclaimer */}               
          <div className="flex items-start space-x-2 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-[11px] text-slate-500">
            <Info className="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" />
            <span>
              This analysis is AI-generated for informational purposes only and does not constitute
              formal legal advice. Consult a qualified legal professional for case-specific guidance.
            </span>
          </div>
        </>
      )}
                                                                                                            
      {/* ── Empty state ── */}
      {!analysis && !loading && !error && (
        <div className="bg-white border border-dashed border-slate-300 rounded-2xl py-16 flex flex-col items-center justify-center space-y-3 text-slate-400">
          <Scale className="w-12 h-12 text-slate-300" />
          <p className="text-sm font-semibold">Select a document and click Analyse</p>
          <p className="text-xs text-center max-w-sm">
            The engine will extract parties, clauses, risks, obligations,
            key dates, and citations from your uploaded document.
          </p>
        </div>
      )}
    </div>
  );
}

