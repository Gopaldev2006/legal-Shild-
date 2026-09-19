import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Bot, Send, ShieldCheck, Sparkles, AlertTriangle, FileText,
  ChevronDown, ChevronUp, Lock, Eye, Loader2, Search,
  BookOpen, CheckCircle2, Info, AlertCircle, ExternalLink
} from 'lucide-react';

const STEPS = [
  { key: 'retrieving',  label: 'Searching document...' },
  { key: 'building',    label: 'Retrieving relevant clauses...' },
  { key: 'generating',  label: 'Generating answer...' },
];

// ── Source card ───────────────────────────────────────────────────────────────
function SourceCard({ source, index, onInspect }) {
  return (
    <div className="flex items-start space-x-3 bg-indigo-50/60 border border-indigo-100 rounded-xl p-3">
      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-600 text-white text-[10px] font-bold flex items-center justify-center mt-0.5">
        {index + 1}
      </span>
      <div className="flex-grow min-w-0">
        <div className="flex items-center justify-between flex-wrap gap-1">
          <span className="font-bold text-xs text-slate-900 truncate max-w-[200px]" title={source.filename}>
            📄 {source.filename}
          </span>
          <div className="flex items-center space-x-1.5">
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-200 rounded text-[10px] font-bold">
              {Math.round(source.similarity * 100)}% match
            </span>
            {onInspect && (
              <button
                onClick={() => onInspect(source.document_id)}
                className="px-2 py-0.5 bg-white hover:bg-indigo-50 border border-indigo-200 text-indigo-700 rounded text-[10px] font-bold flex items-center space-x-1 transition-colors"
              >
                <Eye className="w-2.5 h-2.5" />
                <span>Inspect</span>
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-2 mt-0.5 text-[10px] text-slate-500 font-medium">
          <span>Page {source.page_number ?? 'N/A'}</span>
          {source.matter_id    && <><span>·</span><span className="font-mono">{source.matter_id}</span></>}
          {source.jurisdiction && <><span>·</span><span>{source.jurisdiction}</span></>}
        </div>
      </div>
    </div>
  );
}

// ── Bot message ───────────────────────────────────────────────────────────────
function BotMessage({ msg, onInspect }) {
  const [showSources, setShowSources] = useState(false);

  return (
    <div className="max-w-[92%] bg-white border border-slate-200 rounded-2xl rounded-tl-none p-4 shadow-sm space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          <span className="text-[11px] font-bold text-slate-700">{msg.provider_used}</span>
        </div>
        <div className="flex items-center space-x-1.5">
          {msg.chunks_retrieved > 0 && (
            <span className="px-2 py-0.5 bg-slate-100 border border-slate-200 text-slate-600 rounded text-[10px] font-semibold">
              {msg.chunks_retrieved} chunk{msg.chunks_retrieved !== 1 ? 's' : ''} retrieved
            </span>
          )}
          {msg.used_rag && (
            <span className="px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded text-[10px] font-bold flex items-center space-x-1">
              <ShieldCheck className="w-2.5 h-2.5" />
              <span>Grounded</span>
            </span>
          )}
          {msg.no_relevant_context && (
            <span className="px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-700 rounded text-[10px] font-bold flex items-center space-x-1">
              <AlertCircle className="w-2.5 h-2.5" />
              <span>No Context</span>
            </span>
          )}
        </div>
      </div>

      {/* Answer */}
      <div className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap font-sans">
        {msg.answer}
      </div>

      {/* Sources accordion */}
      {msg.sources && msg.sources.length > 0 && (
        <div className="pt-2 border-t border-slate-100 space-y-2">
          <button
            onClick={() => setShowSources(v => !v)}
            className="w-full flex items-center justify-between text-[11px] font-bold text-indigo-700 hover:text-indigo-900 transition-colors"
          >
            <span className="flex items-center space-x-1.5">
              <FileText className="w-3.5 h-3.5" />
              <span>Sources ({msg.sources.length})</span>
            </span>
            {showSources ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {showSources && (
            <div className="space-y-2 pt-1">
              {msg.sources.map((src, i) => (
                <SourceCard key={src.chunk_id} source={src} index={i} onInspect={onInspect} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function RAGChatbot({ onInspectDocument, documents = [] }) {
  const { token } = useAuth();
  const [query,      setQuery]      = useState('');
  const [documentId, setDocumentId] = useState('');
  const [topK,       setTopK]       = useState(5);
  const [loading,    setLoading]    = useState(false);
  const [step,       setStep]       = useState(null);   // 'retrieving' | 'building' | 'generating'
  const [error,      setError]      = useState(null);
  const messagesEndRef               = useRef(null);

  const [history, setHistory] = useState([
    {
      id:       1,
      type:     'bot',
      answer:   'Hello Counselor. I am your Grounded Legal RAG Assistant (Phase 4).\n\nAsk any question about your uploaded documents. I will retrieve the most relevant passages, build context, and generate a grounded answer with source citations.\n\n**How to use:**\n1. Optionally select a specific document from the dropdown\n2. Type your legal question\n3. Click Ask RAG',
      provider_used:    'LexGuard RAG Assistant',
      sources:          [],
      used_rag:         false,
      chunks_retrieved: 0,
      no_relevant_context: false,
    }
  ]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, loading]);

  const runStep = async (key, delayMs = 600) => {
    setStep(key);
    await new Promise(r => setTimeout(r, delayMs));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userText = query.trim();
    setHistory(prev => [...prev, {
      id: Date.now(), type: 'user', text: userText
    }]);
    setQuery('');
    setLoading(true);
    setError(null);

    try {
      await runStep('retrieving', 500);
      await runStep('building',   400);
      await runStep('generating', 300);

      const body = {
        query: userText,
        top_k: topK,
      };
      if (documentId) body.document_id = parseInt(documentId, 10);

      const res  = await fetch('/api/v1/rag/query', {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'RAG query failed');
      }

      setHistory(prev => [...prev, {
        id:              Date.now() + 1,
        type:            'bot',
        answer:          data.answer,
        sources:         data.sources || [],
        provider_used:   data.provider_used,
        used_rag:        data.used_rag,
        chunks_retrieved:data.chunks_retrieved,
        no_relevant_context: data.no_relevant_context,
      }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setStep(null);
    }
  };

  const currentStep = STEPS.find(s => s.key === step);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden flex flex-col h-[680px]">

      {/* ── Header ── */}
      <div className="bg-slate-900 text-white px-5 py-3.5 flex items-center justify-between border-b border-slate-700">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-600/30 border border-indigo-400/30 rounded-xl text-indigo-300">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-white">LexGuard Grounded RAG Assistant</h3>
              <span className="px-2 py-0.5 bg-emerald-900/60 border border-emerald-700 text-emerald-300 text-[10px] font-bold rounded flex items-center space-x-1">
                <Lock className="w-2.5 h-2.5" />
                <span>Phase 4</span>
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Retrieval → Context → Gemini / Free Engine → Grounded Answer
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-2">
          {/* Document selector */}
          <div className="flex items-center space-x-1.5 bg-slate-800 border border-slate-700 rounded-xl px-3 py-1.5">
            <BookOpen className="w-3 h-3 text-indigo-400 flex-shrink-0" />
            <select
              value={documentId}
              onChange={e => setDocumentId(e.target.value)}
              className="bg-transparent text-slate-200 text-[11px] focus:outline-none cursor-pointer font-medium max-w-[140px]"
            >
              <option value="">All Documents</option>
              {documents.map(d => (
                <option key={d.id} value={d.id}>
                  {d.filename.length > 20 ? d.filename.slice(0, 18) + '…' : d.filename}
                </option>
              ))}
            </select>
          </div>

          {/* Top-K */}
          <div className="flex items-center space-x-1.5 bg-slate-800 border border-slate-700 rounded-xl px-3 py-1.5">
            <Search className="w-3 h-3 text-indigo-400" />
            <select
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              className="bg-transparent text-slate-200 text-[11px] focus:outline-none cursor-pointer font-medium"
            >
              {[3, 5, 8, 10].map(k => (
                <option key={k} value={k}>Top {k}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 bg-slate-50/40">
        {history.map(msg => (
          <div key={msg.id} className={`flex flex-col ${msg.type === 'user' ? 'items-end' : 'items-start'}`}>
            {msg.type === 'user' ? (
              <div className="max-w-[78%] bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-3 text-xs shadow-md">
                {msg.text}
              </div>
            ) : (
              <BotMessage msg={msg} onInspect={onInspectDocument} />
            )}
          </div>
        ))}

        {/* Step-by-step loading indicator */}
        {loading && (
          <div className="flex items-start space-x-3">
            <div className="bg-white border border-indigo-100 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm space-y-2 text-xs">
              {STEPS.map((s, i) => {
                const stepIdx = STEPS.findIndex(st => st.key === step);
                const done    = i < stepIdx;
                const active  = s.key === step;
                return (
                  <div key={s.key} className={`flex items-center space-x-2 transition-opacity ${active ? 'opacity-100' : done ? 'opacity-60' : 'opacity-30'}`}>
                    {done ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                    ) : active ? (
                      <Loader2 className="w-3.5 h-3.5 text-indigo-500 animate-spin flex-shrink-0" />
                    ) : (
                      <div className="w-3.5 h-3.5 rounded-full border border-slate-300 flex-shrink-0" />
                    )}
                    <span className={`font-medium ${active ? 'text-indigo-700' : done ? 'text-emerald-700' : 'text-slate-400'}`}>
                      {s.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center space-x-2 bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl px-4 py-3">
            <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Info banner when no documents */}
        {documents.length === 0 && (
          <div className="flex items-center space-x-2 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-xl px-4 py-3">
            <Info className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>No documents uploaded yet. Upload a PDF or DOCX in the Documents tab to enable grounded RAG.</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input bar ── */}
      <form onSubmit={handleSubmit} className="px-4 py-3 bg-white border-t border-slate-200 flex items-center space-x-2">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          disabled={loading}
          placeholder={
            documents.length === 0
              ? 'Upload a document first to ask RAG questions...'
              : documentId
                ? `Ask a question about ${documents.find(d => String(d.id) === documentId)?.filename ?? 'selected document'}...`
                : 'Ask a legal question over your documents...'
          }
          className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all placeholder-slate-400 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-all disabled:opacity-50 shadow-md shadow-indigo-600/20 whitespace-nowrap"
        >
          {loading
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Send className="w-3.5 h-3.5" />
          }
          <span>{loading ? 'Processing...' : 'Ask RAG'}</span>
        </button>
      </form>
    </div>
  );
}
