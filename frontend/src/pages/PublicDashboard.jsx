import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import LegalDisclaimer from '../components/LegalDisclaimer';
import HealthStatus from '../components/HealthStatus';
import VerificationRequestModal from '../components/VerificationRequestModal';
import PersistentChat from '../components/PersistentChat';
import { MessageSquare, ShieldCheck, BookOpen, Send, User, Clock, CheckCircle2, XCircle, Award, AlertCircle, Lock, Info, Sparkles, MessagesSquare } from 'lucide-react';

export default function PublicDashboard() {
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeView, setActiveView] = useState('quick'); // 'quick' | 'persistent'

  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'assistant',
      text: 'Welcome to the Tier 1 Public Educational Legal Assistant. Ask general questions regarding legal concepts, terminology, statutory frameworks, or procedural basics.',
      disclaimer: 'Legal Disclaimer: This information is provided strictly for general educational purposes and does not constitute formal legal advice. Consult a qualified advocate for legal counsel.',
      topic: 'General Educational Information'
    }
  ]);

    const handlePublicSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userText = query.trim();
    const userMsg = { id: Date.now(), sender: 'user', text: userText };

    setMessages((prev) => [...prev, userMsg]);
    setQuery('');
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/rag/public-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userText })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Public query failed');
      }

      const botMsg = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: data.answer,
        disclaimer: data.disclaimer,
        topic: data.topic,
        isSafe: data.is_safe
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error('Public query error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const status = user?.verification_status || 'NOT_REQUIRED';

  return (
    <div className="space-y-6">
      {/* Tier 1 Public Mode Active Header Banner */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between space-y-4 md:space-y-0">
        <div className="flex items-center space-x-4">
          <div className="p-3.5 bg-blue-50 border border-blue-100 rounded-2xl text-blue-600 shadow-sm">
            <User className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-xl font-extrabold text-slate-900">Welcome, {user?.name || 'Public User'}</h2>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200 flex items-center space-x-1">
                <Lock className="w-3 h-3 text-blue-600" />
                <span>TIER 1 — PUBLIC EDUCATIONAL MODE</span>
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              General Legal Information & Terminology • Zero Private Document Access
            </p>
          </div>
        </div>

        {/* Professional Upgrade / Verification Status Box */}
        <div className="w-full md:w-auto bg-slate-50 p-4 rounded-2xl border border-slate-200 flex items-center justify-between space-x-4">
          <div>
            <div className="text-xs font-bold text-slate-700 flex items-center space-x-1.5">
              <Award className="w-4 h-4 text-emerald-600" />
              <span>Professional Verification:</span>
            </div>
            <div className="mt-1 flex items-center space-x-2">
              {status === 'NOT_REQUIRED' && (
                <span className="text-xs text-slate-500 font-medium">Not Requested</span>
              )}
              {status === 'PENDING' && (
                <span className="inline-flex items-center space-x-1 px-3 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded-full text-xs font-bold">
                  <Clock className="w-3 h-3 animate-spin text-amber-600" />
                  <span>Pending Admin Review</span>
                </span>
              )}
              {status === 'VERIFIED' && (
                <span className="inline-flex items-center space-x-1 px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-xs font-bold">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>VERIFIED PROFESSIONAL</span>
                </span>
              )}
              {status === 'REJECTED' && (
                <span className="inline-flex items-center space-x-1 px-3 py-1 bg-red-50 text-red-800 border border-red-200 rounded-full text-xs font-bold">
                  <XCircle className="w-3 h-3 text-red-600" />
                  <span>Verification Rejected</span>
                </span>
              )}
            </div>
          </div>

          {(status === 'NOT_REQUIRED' || status === 'REJECTED') && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl flex items-center space-x-1.5 transition-all shadow-md shadow-emerald-600/20 whitespace-nowrap"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Apply for Professional Tier</span>
            </button>
          )}
        </div>
      </div>

      {/* Mandatory General Legal Disclaimer */}
      <LegalDisclaimer />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tier 1 Public Educational Chat Interface */}
        <div className={`bg-white border border-slate-200 rounded-2xl shadow-sm flex flex-col ${activeView === 'persistent' ? 'lg:col-span-3' : 'lg:col-span-2'}`}
             style={{ height: activeView === 'persistent' ? 'auto' : '550px' }}>

          {/* ── Header ── */}
          <div className="flex items-center justify-between p-6 pb-3 border-b border-slate-200">
            <div className="flex items-center space-x-2">
              <MessageSquare className="w-5 h-5 text-indigo-600" />
              <h3 className="font-bold text-slate-900 text-sm">
                Ask Legal Question (Tier 1 Public Assistant)
              </h3>
            </div>
            <div className="flex items-center space-x-2 flex-wrap gap-y-1">
              {/* View toggle — only for logged-in users */}
              {user && (
                <div className="flex items-center bg-slate-100 border border-slate-200 rounded-xl p-0.5 text-[10px] font-bold">
                  <button
                    onClick={() => setActiveView('quick')}
                    className={`px-2.5 py-1 rounded-lg flex items-center gap-1 transition-all ${
                      activeView === 'quick'
                        ? 'bg-white text-indigo-700 shadow-sm border border-indigo-100'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    <MessageSquare className="w-3 h-3" />
                    Quick Ask
                  </button>
                  <button
                    onClick={() => setActiveView('persistent')}
                    className={`px-2.5 py-1 rounded-lg flex items-center gap-1 transition-all ${
                      activeView === 'persistent'
                        ? 'bg-white text-teal-700 shadow-sm border border-teal-100'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    <MessagesSquare className="w-3 h-3" />
                    Chat History
                  </button>
                </div>
              )}
              <span className="px-2.5 py-1 bg-gradient-to-r from-blue-50 to-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg text-[10px] font-bold flex items-center space-x-1 shadow-sm">
                <Sparkles className="w-3 h-3 text-indigo-600" />
                <span>Powered by Google Gemini AI</span>
              </span>
              <span className="px-2.5 py-1 bg-slate-100 text-slate-600 border border-slate-200 rounded-lg text-[10px] font-semibold">
                No Private Case Files Access
              </span>
            </div>
          </div>

          {/* ── Persistent Chat view (logged-in users only) ── */}
          {activeView === 'persistent' && user && (
            <div className="p-4">
              <PersistentChat
                mode="general"
                title="General Legal Chat History"
              />
            </div>
          )}

          {/* ── Quick Ask view (ephemeral, original UI) ── */}
          {activeView === 'quick' && (
            <>
              <div className="flex-grow overflow-y-auto space-y-4 px-6 py-4 pr-4 mb-0">
                {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
              >
                {msg.sender === 'user' ? (
                  <div className="max-w-[80%] bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-3 text-xs shadow-md">
                    {msg.text}
                  </div>
                ) : (
                  <div className="max-w-[90%] bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-none p-4 text-xs shadow-sm space-y-3">
                    <div className="flex items-center space-x-2 text-[11px] text-indigo-700 font-bold border-b border-slate-200 pb-1.5">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>{msg.topic || 'General Educational Information'}</span>
                    </div>

                    <p className="text-slate-800 leading-relaxed whitespace-pre-wrap font-sans">{msg.text}</p>

                    {msg.disclaimer && (
                      <div className="pt-2 border-t border-slate-200 text-[11px] text-amber-900 italic flex items-start space-x-1.5 bg-amber-50/60 p-2.5 rounded-lg border border-amber-100">
                        <Info className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
                        <span>{msg.disclaimer}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center space-x-2 text-xs text-indigo-700 bg-indigo-50 p-3 rounded-xl border border-indigo-100 w-max animate-pulse">
                <MessageSquare className="w-4 h-4 animate-spin text-indigo-600" />
                <span>Processing general legal educational inquiry...</span>
              </div>
            )}

            {error && (
              <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>

          <form onSubmit={handlePublicSubmit} className="flex space-x-2 px-6 pb-5">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a general legal educational question (e.g., What is Habeas Corpus or Contract Breach?)"
              className="flex-grow bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 transition-all placeholder-slate-400 font-medium"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-all disabled:opacity-50 shadow-md shadow-indigo-600/20"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Ask Tier 1</span>
            </button>
          </form>
            </>
          )}
        </div>

        {/* Sidebar Guidelines & Verification Upgrade Card */}
        {activeView !== 'persistent' && (
        <div className="space-y-6">
          <HealthStatus />

          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-3">
            <h4 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-emerald-600" />
              <span>Tier 1 Public Access Rules</span>
            </h4>
            <ul className="text-xs text-slate-600 space-y-2.5 leading-relaxed">
              <li className="flex items-start space-x-2">
                <span className="text-indigo-600 font-bold">•</span>
                <span>Tier 1 responses provide general legal explanations and terminology definitions.</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-indigo-600 font-bold">•</span>
                <span>Public users cannot upload private documents or execute vector RAG queries.</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-indigo-600 font-bold">•</span>
                <span>Practicing legal professionals can request Tier 2 verification to access RAG case analysis.</span>
              </li>
            </ul>
          </div>
        </div>
        )}
      </div>

      {/* Professional Verification Request Modal */}
      <VerificationRequestModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
}
