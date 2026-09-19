import React from 'react';
import { ShieldCheck, Scale, Lock, FileText, Sparkles, BookOpen, UserCheck, ArrowRight } from 'lucide-react';

export default function LandingPage({ onSelectLogin, onSelectRegister, onExplorePublic }) {
  return (
    <div className="space-y-12 py-6">
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white rounded-3xl p-8 sm:p-12 shadow-2xl relative overflow-hidden">
        <div className="absolute -right-12 -bottom-12 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>

        <div className="max-w-3xl space-y-6 relative z-10">
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-indigo-500/20 border border-indigo-400/30 rounded-full text-xs font-medium text-indigo-300">
            <Sparkles className="w-3.5 h-3.5" />
            <span>B.Tech Major Project • Secure AI Assistant for Legal Data Analysis</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-tight text-white">
            Permission-Aware AI Legal Intelligence & Grounded Analysis Engine
          </h1>

          <p className="text-sm sm:text-base text-slate-300 leading-relaxed font-light">
            Designed for legal professionals and public information access. Combines pre-generation authorization filtering, local Small Language Models (SLM), 5-layer prompt injection defense, and grounded citation verification.
          </p>

          <div className="flex flex-wrap gap-3 pt-4">
            <button
              onClick={onExplorePublic}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl flex items-center space-x-2 transition-all shadow-lg hover:shadow-indigo-500/30"
            >
              <span>Explore Public Legal AI</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              onClick={onSelectLogin}
              className="px-6 py-3 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold rounded-xl border border-white/20 transition-colors"
            >
              Sign In to Workspace
            </button>

            <button
              onClick={onSelectRegister}
              className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl transition-colors shadow-md"
            >
              Register Account
            </button>
          </div>
        </div>
      </section>

      {/* Core Architectural Feature Cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow space-y-3">
          <div className="p-3 bg-indigo-50 border border-indigo-100 rounded-xl text-indigo-600 w-max">
            <Lock className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-900">Pre-Generation Authorization</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            FAISS vector search enforces owner-level security during retrieval. Unauthorized document chunks are purged BEFORE reaching prompt construction.
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow space-y-3">
          <div className="p-3 bg-emerald-50 border border-emerald-100 rounded-xl text-emerald-600 w-max">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-900">5-Layer Security Firewall</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Protects against direct jailbreaks, indirect document injections, system prompt leaks, PII disclosures, and ungrounded hallucinations.
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow space-y-3">
          <div className="p-3 bg-purple-50 border border-purple-100 rounded-xl text-purple-600 w-max">
            <Scale className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-900">Decoupled Citation Engine</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Independent 5-tier citation validator ensures all responses are grounded in authorized sources with interactive source document inspection.
          </p>
        </div>
      </section>
    </div>
  );
}
