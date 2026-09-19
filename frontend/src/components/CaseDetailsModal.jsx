import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { X, Scale, BookOpen, FileText, CheckCircle2, Info, Building2, Calendar, ShieldCheck } from 'lucide-react';

export default function CaseDetailsModal({ caseId, isOpen, onClose }) {
  const { token } = useAuth();
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!caseId || !isOpen) return;

    const fetchCaseDetails = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/v1/cases/${caseId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || 'Failed to load case details');
        }
        setCaseData(data);
      } catch (err) {
        console.error('Case details error:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchCaseDetails();
  }, [caseId, isOpen, token]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-6 border-b border-slate-200 flex items-start justify-between bg-slate-50/80">
          <div className="flex items-start space-x-3">
            <div className="p-3 bg-amber-50 border border-amber-100 rounded-2xl text-amber-600 flex-shrink-0 mt-1 shadow-sm">
              <Scale className="w-6 h-6" />
            </div>
            <div>
              <span className="px-3 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-100 text-amber-900 border border-amber-200 inline-block mb-1">
                {caseData?.case_id || caseId}
              </span>
              <h3 className="text-lg font-extrabold text-slate-900 leading-snug">
                {loading ? 'Loading Legal Case Precedent...' : caseData?.title}
              </h3>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs text-slate-700 flex-1">
          {error && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs">
              {error}
            </div>
          )}

          {loading ? (
            <div className="py-12 text-center text-slate-500 text-sm animate-pulse">
              Retrieving public academic case decision and arguments...
            </div>
          ) : caseData && (
            <>
              {/* Metadata Pills Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-50 p-4 rounded-2xl border border-slate-200">
                <div className="flex items-center space-x-2">
                  <Building2 className="w-4 h-4 text-purple-600" />
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase font-bold">Court</div>
                    <div className="font-extrabold text-slate-900">{caseData.court}</div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <Calendar className="w-4 h-4 text-indigo-600" />
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase font-bold">Judgment Date</div>
                    <div className="font-extrabold text-slate-900">{caseData.date}</div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase font-bold">Jurisdiction</div>
                    <div className="font-extrabold text-slate-900">{caseData.jurisdiction}</div>
                  </div>
                </div>
              </div>

              {/* Case Facts */}
              <div className="space-y-1.5">
                <h4 className="font-bold text-indigo-700 flex items-center space-x-2 text-xs uppercase tracking-wider">
                  <FileText className="w-4 h-4" />
                  <span>Relevant Material Facts</span>
                </h4>
                <p className="bg-slate-50 p-4 rounded-2xl border border-slate-200 leading-relaxed text-slate-800 font-sans font-medium">
                  {caseData.facts}
                </p>
              </div>

              {/* Legal Issues */}
              <div className="space-y-1.5">
                <h4 className="font-bold text-purple-700 flex items-center space-x-2 text-xs uppercase tracking-wider">
                  <BookOpen className="w-4 h-4" />
                  <span>Legal Issues & Statutory Questions</span>
                </h4>
                <p className="bg-slate-50 p-4 rounded-2xl border border-slate-200 leading-relaxed text-slate-800 font-sans font-medium">
                  {caseData.legal_issues}
                </p>
              </div>

              {/* Legal Arguments */}
              <div className="space-y-1.5">
                <h4 className="font-bold text-amber-700 flex items-center space-x-2 text-xs uppercase tracking-wider">
                  <Scale className="w-4 h-4" />
                  <span>Contentions & Arguments</span>
                </h4>
                <p className="bg-slate-50 p-4 rounded-2xl border border-slate-200 leading-relaxed text-slate-800 font-sans font-medium">
                  {caseData.arguments}
                </p>
              </div>

              {/* Decision / Verdict */}
              <div className="space-y-1.5">
                <h4 className="font-bold text-emerald-700 flex items-center space-x-2 text-xs uppercase tracking-wider">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Court Decision & Judicial Verdict</span>
                </h4>
                <p className="bg-emerald-50/70 p-4 rounded-2xl border border-emerald-200 leading-relaxed text-emerald-900 font-sans font-extrabold shadow-sm">
                  {caseData.decision}
                </p>
              </div>

              {/* Source & Reference Citation */}
              <div className="pt-3 border-t border-slate-200 text-[11px] text-slate-500 flex flex-wrap items-center justify-between gap-2 font-medium">
                <div className="flex items-center space-x-1.5">
                  <Info className="w-3.5 h-3.5 text-slate-400" />
                  <span>Source: {caseData.source}</span>
                </div>
                <div className="font-mono bg-slate-100 px-3 py-1 rounded-lg border border-slate-200 text-slate-800 font-bold">
                  Ref: {caseData.source_reference}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
