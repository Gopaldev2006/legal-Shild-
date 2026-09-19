/**
 * PersistentChat.jsx — Phase 5: Chat History Dashboard
 * ======================================================
 * Self-contained persistent AI chat panel for LexGuard AI.
 *
 * Layout (2-column, responsive):
 *   LEFT  – History sidebar   (grouped by date, + New Chat, rename, delete)
 *   RIGHT – Message thread    (full history, step indicator, source cards)
 *
 * Modes:
 *   general  → Tier 1 public-query engine (no docs required)
 *   document → RAG scoped to one linked document
 *   rag      → RAG across all user documents
 *
 * Props:
 *   mode        'general' | 'document' | 'rag'   (default: 'general')
 *   documentId  number | null  — pre-link a document (document mode)
 *   documents   array          — list of user's docs for selector
 *   title       string         — panel heading
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  MessageSquare, Plus, Trash2, Edit3, Check, X, Send, Loader2,
  Bot, User, ChevronRight, FileText, Sparkles, Shield, AlertCircle,
  MoreVertical, RefreshCw, Info, BookOpen, Link2, Clock, Search,
  Zap, MessageSquarePlus,
} from 'lucide-react';
import {
  createConversation,
  listConversations,
  getConversation,
  renameConversation,
  deleteConversation,
  sendMessage,
} from '../services/chatApi';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Short relative time (e.g. "3m ago", "2h ago", "5d ago") */
function relativeTime(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/** Absolute timestamp for tooltip / subtitle (e.g. "Today, 10:32 AM") */
function absoluteTime(iso) {
  if (!iso) return '';
  const d    = new Date(iso);
  const now  = new Date();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const isToday =
    d.getDate()     === now.getDate()     &&
    d.getMonth()    === now.getMonth()    &&
    d.getFullYear() === now.getFullYear();

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    d.getDate()     === yesterday.getDate()     &&
    d.getMonth()    === yesterday.getMonth()    &&
    d.getFullYear() === yesterday.getFullYear();

  if (isToday)     return `Today, ${time}`;
  if (isYesterday) return `Yesterday, ${time}`;
  return `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })}, ${time}`;
}

/** Classify a conversation into Today / Yesterday / Earlier */
function dateGroup(iso) {
  if (!iso) return 'Earlier';
  const d    = new Date(iso);
  const now  = new Date();
  const diff = Math.floor((now - d) / 86400000);
  if (diff < 1)  return 'Today';
  if (diff < 2)  return 'Yesterday';
  return 'Earlier';
}

function modeLabel(mode) {
  if (mode === 'document') return { text: 'Document', color: 'text-violet-600 bg-violet-50 border-violet-200' };
  if (mode === 'rag')      return { text: 'RAG',      color: 'text-emerald-600 bg-emerald-50 border-emerald-200' };
  return                          { text: 'General',  color: 'text-blue-600 bg-blue-50 border-blue-200' };
}

function providerBadge(model) {
  if (!model || model === 'placeholder') return null;
  if (model === 'gemini')
    return (
      <span className="px-1.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded text-[9px] font-bold flex items-center gap-1">
        <Sparkles className="w-2.5 h-2.5" />Gemini
      </span>
    );
  if (model === 'error-fallback')
    return <span className="px-1.5 py-0.5 bg-red-50 border border-red-200 text-red-700 rounded text-[9px] font-bold">Error Fallback</span>;
  return (
    <span className="px-1.5 py-0.5 bg-slate-100 border border-slate-200 text-slate-600 rounded text-[9px] font-bold flex items-center gap-1">
      <Shield className="w-2.5 h-2.5" />Free Engine
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Source card
// ─────────────────────────────────────────────────────────────────────────────

function SourceCard({ src, index }) {
  return (
    <div className="flex items-start gap-2.5 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-[11px]">
      <div className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-indigo-100 border border-indigo-200 flex items-center justify-center text-[9px] font-bold text-indigo-700">
        {index + 1}
      </div>
      <div className="flex-1 min-w-0 space-y-0.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <FileText className="w-3 h-3 text-indigo-500 flex-shrink-0" />
          <span className="font-semibold text-slate-800 truncate max-w-[180px]" title={src.document_name}>
            {src.document_name || 'Unknown document'}
          </span>
          {src.page_number != null && (
            <span className="px-1.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded text-[9px] font-bold">
              p.{src.page_number}
            </span>
          )}
          {src.similarity != null && (
            <span className="px-1.5 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded text-[9px] font-bold">
              {Math.round(src.similarity * 100)}% match
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap text-[10px] text-slate-400">
          {src.matter_id    && <span>Matter: {src.matter_id}</span>}
          {src.jurisdiction && <span>· {src.jurisdiction}</span>}
          <span className="font-mono text-[9px]">{src.chunk_id?.slice(0, 12)}…</span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Message bubble
// ─────────────────────────────────────────────────────────────────────────────

function MessageBubble({ msg }) {
  const isUser    = msg.role === 'user';
  const [showSrc, setShowSrc] = useState(false);
  const hasSources = msg.sources && msg.sources.length > 0;

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-3 text-xs shadow-md leading-relaxed">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[88%] bg-white border border-slate-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm space-y-2">
        {/* provider badge + timestamp */}
        {msg.model_used && (
          <div className="flex items-center gap-1.5 border-b border-slate-100 pb-1.5">
            <Bot className="w-3 h-3 text-slate-400" />
            {providerBadge(msg.model_used)}
            <span className="text-[9px] text-slate-400 ml-auto">{absoluteTime(msg.created_at)}</span>
          </div>
        )}

        {/* answer text */}
        <p className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap font-sans">
          {msg.content}
        </p>

        {/* sources accordion */}
        {hasSources && (
          <div className="pt-1 border-t border-slate-100">
            <button
              onClick={() => setShowSrc(v => !v)}
              className="flex items-center gap-1.5 text-[10px] font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
            >
              <FileText className="w-3 h-3" />
              {showSrc ? 'Hide' : 'Show'} sources ({msg.sources.length})
              <ChevronRight className={`w-3 h-3 transition-transform ${showSrc ? 'rotate-90' : ''}`} />
            </button>
            {showSrc && (
              <div className="flex flex-col gap-1.5 mt-2">
                {msg.sources.map((s, i) => <SourceCard key={i} src={s} index={i} />)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Step-by-step typing indicator
// ─────────────────────────────────────────────────────────────────────────────

// Steps cycle while the AI is working, giving visual feedback per the spec.
const THINKING_STEPS = [
  { icon: Search, label: 'Searching document…' },
  { icon: FileText, label: 'Retrieving relevant clauses…' },
  { icon: Zap,    label: 'Generating answer…' },
];

function TypingIndicator({ mode }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setStep(s => (s + 1) % THINKING_STEPS.length), 1400);
    return () => clearInterval(id);
  }, []);

  // General mode uses simpler label (no document search steps)
  if (mode === 'general') {
    return (
      <div className="flex justify-start">
        <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
          <div className="flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 text-indigo-500 animate-spin" />
            <span className="text-[11px] text-slate-500 font-medium">LexGuard is thinking…</span>
          </div>
        </div>
      </div>
    );
  }

  const { icon: StepIcon, label } = THINKING_STEPS[step];

  return (
    <div className="flex justify-start">
      <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm min-w-[200px]">
        <div className="flex items-center gap-2">
          <Loader2 className="w-3.5 h-3.5 text-indigo-500 animate-spin flex-shrink-0" />
          <StepIcon className="w-3 h-3 text-indigo-400 flex-shrink-0" />
          <span className="text-[11px] text-slate-500 font-medium transition-all">{label}</span>
        </div>
        {/* progress dots */}
        <div className="flex gap-1 mt-2 pl-0.5">
          {THINKING_STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 rounded-full transition-all duration-300 ${
                i === step ? 'w-4 bg-indigo-500' : 'w-1.5 bg-slate-200'
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sidebar conversation item
// ─────────────────────────────────────────────────────────────────────────────

function ConvItem({ conv, active, onSelect, onRename, onDelete }) {
  const [editing,   setEditing]   = useState(false);
  const [draftTitle, setDraftTitle] = useState(conv.title);
  const [menuOpen,  setMenuOpen]  = useState(false);
  const inputRef = useRef(null);
  const badge    = modeLabel(conv.mode);
  const isDocMode = conv.mode === 'document';

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const commitRename = () => {
    const t = draftTitle.trim();
    if (t && t !== conv.title) onRename(conv.id, t);
    setEditing(false);
    setMenuOpen(false);
  };
  const cancelEdit = () => { setDraftTitle(conv.title); setEditing(false); };

  return (
    <div
      onClick={() => !editing && onSelect(conv.id)}
      className={`group relative flex items-start gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all select-none ${
        active
          ? 'bg-indigo-50 border border-indigo-200 shadow-sm'
          : 'hover:bg-slate-100/70 border border-transparent'
      }`}
    >
      {/* icon — document 📄 vs chat bubble */}
      {isDocMode
        ? <FileText className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${active ? 'text-violet-600' : 'text-slate-400'}`} />
        : <MessageSquare className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${active ? 'text-indigo-600' : 'text-slate-400'}`} />
      }

      <div className="flex-1 min-w-0">
        {editing ? (
          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
            <input
              ref={inputRef}
              value={draftTitle}
              onChange={e => setDraftTitle(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') cancelEdit(); }}
              className="flex-1 text-xs bg-white border border-indigo-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-400 min-w-0"
            />
            <button onClick={commitRename} className="text-emerald-600 hover:text-emerald-700 p-0.5"><Check className="w-3.5 h-3.5" /></button>
            <button onClick={cancelEdit}   className="text-slate-400 hover:text-slate-600 p-0.5"><X className="w-3.5 h-3.5" /></button>
          </div>
        ) : (
          <>
            <p className={`text-xs font-semibold truncate leading-snug ${active ? 'text-indigo-800' : 'text-slate-700'}`}>
              {conv.title || 'Untitled'}
            </p>
            {/* timestamp + mode badge */}
            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
              <span className={`text-[9px] font-bold px-1.5 py-0.5 border rounded flex-shrink-0 ${badge.color}`}>
                {badge.text}
              </span>
              {conv.message_count > 0 && (
                <span className="text-[9px] text-slate-400 flex-shrink-0">{conv.message_count} msg</span>
              )}
            </div>
            {/* absolute timestamp on second line */}
            <p className="text-[9px] text-slate-400 mt-0.5 flex items-center gap-1">
              <Clock className="w-2.5 h-2.5 flex-shrink-0" />
              {absoluteTime(conv.updated_at)}
            </p>
          </>
        )}
      </div>

      {/* kebab menu */}
      {!editing && (
        <div className="relative" onClick={e => e.stopPropagation()}>
          <button
            onClick={() => setMenuOpen(v => !v)}
            className={`p-0.5 rounded transition-colors ${
              menuOpen ? 'text-slate-700 bg-slate-200' : 'text-transparent group-hover:text-slate-400 hover:text-slate-700 hover:bg-slate-200'
            }`}
          >
            <MoreVertical className="w-3.5 h-3.5" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-6 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 w-32 text-xs">
              <button
                onClick={() => { setEditing(true); setMenuOpen(false); }}
                className="w-full text-left px-3 py-1.5 hover:bg-slate-50 flex items-center gap-2 text-slate-700"
              >
                <Edit3 className="w-3 h-3" /> Rename
              </button>
              <button
                onClick={() => { onDelete(conv.id); setMenuOpen(false); }}
                className="w-full text-left px-3 py-1.5 hover:bg-red-50 flex items-center gap-2 text-red-600"
              >
                <Trash2 className="w-3 h-3" /> Delete
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Date group separator
// ─────────────────────────────────────────────────────────────────────────────

function GroupLabel({ label }) {
  return (
    <div className="px-3 pt-3 pb-1">
      <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">{label}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// New conversation modal
// ─────────────────────────────────────────────────────────────────────────────

function NewConvModal({ defaultMode, defaultDocId, documents, onConfirm, onClose }) {
  const [title, setTitle] = useState('');
  const [mode,  setMode]  = useState(defaultMode || 'general');
  const [docId, setDocId] = useState(defaultDocId ? String(defaultDocId) : '');

  const submit = (e) => {
    e.preventDefault();
    onConfirm({
      title:       title.trim() || 'New Conversation',
      mode,
      document_id: (mode === 'document' || mode === 'rag') && docId ? parseInt(docId, 10) : null,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Plus className="w-4 h-4 text-indigo-600" /> New Conversation
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={submit} className="px-6 py-5 space-y-4">
          {/* Title */}
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1.5">
              Title <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Contract Termination Review"
              className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200 transition-all"
            />
          </div>

          {/* Mode */}
          <div>
            <label className="text-xs font-semibold text-slate-600 block mb-1.5">Mode</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: 'general',  label: 'General',  desc: 'No docs', icon: '💬' },
                { value: 'document', label: 'Document', desc: 'One doc',  icon: '📄' },
                { value: 'rag',      label: 'RAG',      desc: 'All docs', icon: '🔍' },
              ].map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => { setMode(opt.value); if (opt.value === 'general') setDocId(''); }}
                  className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-xl border text-xs font-semibold transition-all ${
                    mode === opt.value
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-md'
                      : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
                  }`}
                >
                  <span>{opt.icon}</span>
                  <span>{opt.label}</span>
                  <span className={`text-[9px] font-normal ${mode === opt.value ? 'text-indigo-200' : 'text-slate-400'}`}>
                    {opt.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Document selector */}
          {(mode === 'document' || mode === 'rag') && documents.length > 0 && (
            <div>
              <label className="text-xs font-semibold text-slate-600 block mb-1.5">
                {mode === 'document' ? 'Select Document *' : 'Scope to Document (optional)'}
              </label>
              <select
                value={docId}
                onChange={e => setDocId(e.target.value)}
                required={mode === 'document'}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-400 transition-all"
              >
                <option value="">All Documents</option>
                {documents.map(d => (
                  <option key={d.id} value={d.id}>{d.filename}</option>
                ))}
              </select>
            </div>
          )}

          {/* No docs warning */}
          {(mode === 'document' || mode === 'rag') && documents.length === 0 && (
            <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 text-xs text-amber-800">
              <Info className="w-3.5 h-3.5 flex-shrink-0" />
              No documents uploaded yet. Upload a PDF/DOCX first.
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 border border-slate-200 text-slate-600 rounded-xl text-xs font-semibold hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition-colors shadow-md shadow-indigo-600/20"
            >
              Start Chat
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty state
// ─────────────────────────────────────────────────────────────────────────────

function EmptyThread({ onNew }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-4">
      <div className="w-16 h-16 bg-indigo-50 border-2 border-indigo-100 rounded-2xl flex items-center justify-center shadow-inner">
        <Bot className="w-8 h-8 text-indigo-400" />
      </div>
      <div>
        <p className="font-bold text-slate-700 text-sm">No conversation selected</p>
        <p className="text-xs text-slate-400 mt-1 max-w-[220px]">
          Select a conversation from the history or start a new one below
        </p>
      </div>
      <button
        onClick={onNew}
        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center gap-2 shadow-md shadow-indigo-600/20 transition-colors"
      >
        <MessageSquarePlus className="w-3.5 h-3.5" /> New Chat
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export default function PersistentChat({
  mode: defaultMode = 'general',
  documentId: defaultDocId = null,
  documents = [],
  title = 'AI Legal Assistant',
}) {
  const { token } = useAuth();

  // Sidebar state
  const [convList,    setConvList]    = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError,   setListError]   = useState(null);
  const [showModal,   setShowModal]   = useState(false);

  // Thread state
  const [activeId,      setActiveId]      = useState(null);
  const [messages,      setMessages]      = useState([]);
  const [threadTitle,   setThreadTitle]   = useState('');
  const [threadMode,    setThreadMode]    = useState(defaultMode);
  const [threadDocId,   setThreadDocId]   = useState(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [sending,       setSending]       = useState(false);
  const [sendError,     setSendError]     = useState(null);
  const [inputText,     setInputText]     = useState('');

  const bottomRef = useRef(null);
  const inputRef  = useRef(null);

  // Auto-open modal when a documentId prop arrives (once per unique doc)
  const autoTriggeredDocRef = useRef(null);
  useEffect(() => {
    if (defaultDocId && defaultDocId !== autoTriggeredDocRef.current && !listLoading) {
      autoTriggeredDocRef.current = defaultDocId;
      setShowModal(true);
    }
  }, [defaultDocId, listLoading]);

  // ── Load conversation list ──────────────────────────────────────────────────
  const loadList = useCallback(async () => {
    if (!token) return;
    setListLoading(true);
    setListError(null);
    try {
      const data = await listConversations(token, { page_size: 50 });
      setConvList(data.conversations || []);
    } catch (err) {
      setListError(err.message);
    } finally {
      setListLoading(false);
    }
  }, [token]);

  useEffect(() => { loadList(); }, [loadList]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // ── Select conversation ─────────────────────────────────────────────────────
  const selectConversation = async (id) => {
    if (id === activeId) return;
    setActiveId(id);
    setMessages([]);
    setSendError(null);
    setThreadLoading(true);
    try {
      const data = await getConversation(token, id);
      setMessages(data.conversation.messages || []);
      setThreadTitle(data.conversation.title);
      setThreadMode(data.conversation.mode);
      setThreadDocId(data.conversation.document_id ?? null);
    } catch (err) {
      setSendError(err.message);
    } finally {
      setThreadLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  // ── Create conversation ─────────────────────────────────────────────────────
  const handleCreate = async (payload) => {
    setShowModal(false);
    try {
      const conv = await createConversation(token, payload);
      await loadList();
      await selectConversation(conv.id);
    } catch (err) {
      setListError(err.message);
    }
  };

  // ── Rename conversation ─────────────────────────────────────────────────────
  const handleRename = async (id, newTitle) => {
    try {
      await renameConversation(token, id, newTitle);
      setConvList(prev => prev.map(c => c.id === id ? { ...c, title: newTitle } : c));
      if (id === activeId) setThreadTitle(newTitle);
    } catch {
      // non-critical — sidebar re-syncs on next load
    }
  };

  // ── Delete conversation ─────────────────────────────────────────────────────
  const handleDelete = async (id) => {
    if (!window.confirm('Delete this conversation and all its messages?')) return;
    try {
      await deleteConversation(token, id);
      setConvList(prev => prev.filter(c => c.id !== id));
      if (id === activeId) {
        setActiveId(null);
        setMessages([]);
        setThreadTitle('');
        setThreadDocId(null);
      }
    } catch (err) {
      setListError(err.message);
    }
  };

  // ── Send message ────────────────────────────────────────────────────────────
  const handleSend = async (e) => {
    e.preventDefault();
    const text = inputText.trim();
    if (!text || !activeId || sending) return;

    setSendError(null);
    setSending(true);
    setInputText('');

    // Optimistic user bubble
    const tempId = `tmp-${Date.now()}`;
    setMessages(prev => [...prev, { id: tempId, role: 'user', content: text, created_at: new Date().toISOString() }]);

    try {
      const data = await sendMessage(token, activeId, text);
      setMessages(prev => [
        ...prev.filter(m => m.id !== tempId),
        data.user_message,
        data.assistant_message,
      ]);

      const updatedTitle = data.conversation.title;
      setThreadTitle(updatedTitle);
      setConvList(prev =>
        prev
          .map(c =>
            c.id === activeId
              ? { ...c, title: updatedTitle, updated_at: data.conversation.updated_at, message_count: (c.message_count || 0) + 2 }
              : c
          )
          .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
      );
    } catch (err) {
      setMessages(prev => prev.filter(m => m.id !== tempId));
      setSendError(err.message);
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  // ── Group conversations by date ─────────────────────────────────────────────
  const grouped = convList.reduce((acc, conv) => {
    const g = dateGroup(conv.updated_at);
    if (!acc[g]) acc[g] = [];
    acc[g].push(conv);
    return acc;
  }, {});
  const GROUP_ORDER = ['Today', 'Yesterday', 'Earlier'];

  // Linked document info for thread header
  const activeBadge = activeId ? modeLabel(threadMode) : null;
  const linkedDoc   = threadDocId ? documents.find(d => d.id === threadDocId) : null;

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden"
         style={{ minHeight: '560px', height: 'calc(100vh - 260px)', maxHeight: '780px' }}>

      {/* ══ SIDEBAR ══════════════════════════════════════════════════════════ */}
      <div className="w-64 flex-shrink-0 flex flex-col border-r border-slate-200 bg-slate-50/60">

        {/* ── Sidebar header ── */}
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-900 space-y-2">
          {/* Title row */}
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-indigo-400 flex-shrink-0" />
            <span className="text-xs font-bold text-white flex-1">AI Legal Assistant</span>
          </div>
          {/* + New Chat button — full width, labelled */}
          <button
            onClick={() => setShowModal(true)}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Chat
          </button>
        </div>

        {/* ── Conversation list ── */}
        <div className="flex-1 overflow-y-auto">

          {listLoading && (
            <div className="flex items-center justify-center py-10 text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              <span className="text-xs">Loading history…</span>
            </div>
          )}

          {listError && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-2 text-[11px] text-red-700 m-2">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span>{listError}</span>
            </div>
          )}

          {/* Rich empty state */}
          {!listLoading && !listError && convList.length === 0 && (
            <div className="flex flex-col items-center text-center py-10 px-4 space-y-3">
              <div className="w-12 h-12 bg-indigo-50 border border-indigo-100 rounded-2xl flex items-center justify-center">
                <MessageSquarePlus className="w-6 h-6 text-indigo-400" />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-700">No conversations yet.</p>
                <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                  Start a new legal AI conversation.
                </p>
              </div>
              <button
                onClick={() => setShowModal(true)}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center gap-1.5 transition-colors"
              >
                <Plus className="w-3 h-3" /> New Chat
              </button>
            </div>
          )}

          {/* Grouped conversation list */}
          {!listLoading && !listError && convList.length > 0 && (
            <>
              {/* Section label */}
              <div className="px-3 pt-3 pb-1">
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">Recent Chats</span>
              </div>

              {GROUP_ORDER.map(group => {
                const items = grouped[group];
                if (!items || items.length === 0) return null;
                return (
                  <div key={group}>
                    <GroupLabel label={group} />
                    <div className="px-2 space-y-0.5 pb-1">
                      {items.map(conv => (
                        <ConvItem
                          key={conv.id}
                          conv={conv}
                          active={conv.id === activeId}
                          onSelect={selectConversation}
                          onRename={handleRename}
                          onDelete={handleDelete}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>

        {/* ── Sidebar footer ── */}
        <div className="px-3 py-2.5 border-t border-slate-200 flex items-center justify-between bg-slate-50">
          <span className="text-[10px] text-slate-400">
            {convList.length} conversation{convList.length !== 1 ? 's' : ''}
          </span>
          <button
            onClick={loadList}
            title="Refresh history"
            className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-200 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* ══ MESSAGE THREAD ═══════════════════════════════════════════════════ */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Thread header */}
        <div className="border-b border-slate-200 bg-slate-900 flex-shrink-0">
          <div className="px-5 py-3.5 flex items-center gap-3">
            <div className="p-1.5 bg-indigo-600/30 border border-indigo-400/30 rounded-xl text-indigo-400">
              <Bot className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white truncate">
                  {activeId ? threadTitle || 'Conversation' : title}
                </h3>
                {activeBadge && (
                  <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded border ${activeBadge.color} bg-opacity-80 flex-shrink-0`}>
                    {activeBadge.text}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 truncate">
                {activeId
                  ? `${messages.length} message${messages.length !== 1 ? 's' : ''} in this conversation`
                  : 'Select a conversation or start a new one'}
              </p>
            </div>
          </div>

          {/* Document-linked banner */}
          {activeId && threadMode === 'document' && (
            <div className="px-5 py-2 bg-teal-900/40 border-t border-teal-700/30 flex items-center gap-2">
              <Link2 className="w-3 h-3 text-teal-400 flex-shrink-0" />
              <FileText className="w-3 h-3 text-teal-400 flex-shrink-0" />
              <span className="text-[11px] text-teal-300 font-semibold truncate">
                {linkedDoc ? linkedDoc.filename : `Document #${threadDocId}`}
              </span>
              <span className="text-[10px] text-teal-500 ml-auto flex-shrink-0">Document Chat</span>
            </div>
          )}
        </div>

        {/* Messages area */}
        {activeId ? (
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 bg-slate-50/30">
            {threadLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                <span className="ml-2 text-xs text-slate-400">Loading history…</span>
              </div>
            )}

            {!threadLoading && messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center py-12 space-y-2">
                <BookOpen className="w-8 h-8 text-slate-300" />
                <p className="text-xs text-slate-400 font-medium">
                  No messages yet — ask your first question below
                </p>
              </div>
            )}

            {!threadLoading && messages.map(msg => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}

            {sending && <TypingIndicator mode={threadMode} />}

            {sendError && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-xs text-red-700">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {sendError}
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        ) : (
          <EmptyThread onNew={() => setShowModal(true)} />
        )}

        {/* Input bar */}
        {activeId && (
          <form
            onSubmit={handleSend}
            className="px-4 py-3 bg-white border-t border-slate-200 flex items-center gap-2 flex-shrink-0"
          >
            <div className="flex-1 flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 focus-within:bg-white focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
              <User className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                disabled={sending}
                placeholder={
                  threadMode === 'general'  ? 'Ask a general legal question…' :
                  threadMode === 'document' ? 'Ask about the linked document…' :
                                             'Search across your documents…'
                }
                className="flex-1 bg-transparent text-xs text-slate-900 focus:outline-none placeholder-slate-400 disabled:opacity-50"
              />
            </div>
            <button
              type="submit"
              disabled={!inputText.trim() || sending}
              className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl flex items-center gap-1.5 shadow-md shadow-indigo-600/20 transition-all whitespace-nowrap"
            >
              {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>{sending ? 'Sending…' : 'Send'}</span>
            </button>
          </form>
        )}
      </div>

      {/* New conversation modal */}
      {showModal && (
        <NewConvModal
          defaultMode={defaultMode}
          defaultDocId={defaultDocId}
          documents={documents}
          onConfirm={handleCreate}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
