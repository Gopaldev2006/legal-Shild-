import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  X, FileText, Layers, Download, Hash, FileCode,
  CheckCircle2, AlertCircle, Clock, Loader2, Info,
  ChevronDown, ChevronUp, Copy, Check
} from 'lucide-react';

const STATUS_STYLES = {
  COMPLETED:  'bg-emerald-50 text-emerald-800 border-emerald-200',
  FAILED:     'bg-red-50 text-red-800 border-red-200',
  PROCESSING: 'bg-amber-50 text-amber-800 border-amber-200',
  UPLOADING:  'bg-blue-50 text-blue-800 border-blue-200',
};

function ChunkCard({ chk, index }) {
  const [expanded, setExpanded] = useState(index === 0);
  const [copied, setCopied]     = useState(false);

  const copyText = async () => {
    await navigator.clipboard.writeText(chk.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-[11px] hover:bg-slate-50/80 transition-colors"
      >
        <div className="flex items-center space-x-3">
          <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded font-bold font-mono">
            #{chk.chunk_index + 1}
          </span>
          <span className="text-slate-500 font-medium">
            Page {chk.page_number || 1} · {chk.text.length.toLocaleString()} chars
          </span>
          <span className="text-slate-400 font-mono hidden sm:inline truncate max-w-[120px]">
            {chk.chunk_id}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100">
          <div className="flex justify-end pt-2 pb-1.5">
            <button
              onClick={copyText}
              className="flex items-center space-x-1 text-[10px] text-slate-400 hover:text-indigo-600 transition-colors font-semibold"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>
          </div>
          <p className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap font-sans bg-slate-50 p-3 rounded-lg border border-slate-100">
            {chk.text}
          </p>
        </div>
      )}
    </div>
  );
}

export default function DocumentDetailsModal({ documentId, isOpen, onClose }) {
  const { token } = useAuth();
  const [doc,     setDoc]     = useState(null);
  const [chunks,  setChunks]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [activeTab, setActiveTab] = useState('chunks');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!isOpen || !documentId) return;
    setActiveTab('chunks');
    setDoc(null);
    setChunks([]);
    setError(null);
    setLoading(true);

    const fetchDetails = async () => {
      try {
        const [resDoc, resChunks] = await Promise.all([
          fetch(`/api/v1/documents/${documentId}`,        { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`/api/v1/documents/${documentId}/chunks`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        if (!resDoc.ok) throw new Error('Failed to load document metadata');
        setDoc(await resDoc.json());
        if (resChunks.ok) setChunks(await resChunks.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchDetails();
  }, [documentId, isOpen, token]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`/api/v1/documents/${documentId}/download`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = doc?.filename || 'document';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
    } finally {
      setDownloading(false);
    }
  };

  if (!isOpen) return null;

  const statusStyle = doc ? (STATUS_STYLES[doc.processing_status] || STATUS_STYLES.PROCESSING) : '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white border border-slate-200 rounded-2xl max-w-3xl w-full shadow-2xl relative max-h-[92vh] flex flex-col">

        {/* Close */}
        <button onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors z-10">
          <X className="w-4 h-4" />
        </button>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 space-y-3 text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
            <span className="text-xs font-semibold">Loading document...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-16 space-y-3 text-red-600">
            <AlertCircle className="w-8 h-8" />
            <span className="text-xs font-semibold">{error}</span>
          </div>
        ) : doc && (
          <>
            {/* ── Header ── */}
            <div className="p-6 border-b border-slate-200">
              <div className="flex items-start space-x-4 pr-8">
                <div className="p-2.5 bg-indigo-50 border border-indigo-100 rounded-xl text-indigo-600 flex-shrink-0">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="flex-grow min-w-0">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <h3 className="text-base font-extrabold text-slate-900 truncate">{doc.filename}</h3>
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${statusStyle}`}>
                      {doc.processing_status}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500 mt-1 font-medium">
                    <span><strong className="uppercase text-slate-700">{doc.file_type}</strong></span>
                    <span>·</span>
                    <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                    <span>·</span>
                    <span className="capitalize">{doc.document_type.replace(/_/g, ' ')}</span>
                    {doc.jurisdiction && <><span>·</span><span>{doc.jurisdiction}</span></>}
                    {doc.matter_id    && <><span>·</span><span className="font-mono">{doc.matter_id}</span></>}
                  </div>
                </div>
              </div>

              {/* SHA-256 */}
              <div className="mt-3 flex items-center space-x-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 font-mono text-[10px] text-slate-600">
                <Hash className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
                <span className="text-slate-400 font-sans font-bold">SHA-256:</span>
                <span className="truncate">{doc.file_hash}</span>
              </div>
            </div>

            {/* ── Tabs ── */}
            <div className="flex space-x-1 px-6 pt-3 border-b border-slate-200">
              <button
                onClick={() => setActiveTab('chunks')}
                className={`pb-2.5 px-3 text-xs font-bold flex items-center space-x-1.5 transition-colors border-b-2 ${
                  activeTab === 'chunks'
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-slate-500 hover:text-slate-900'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Text Chunks ({chunks.length})</span>
              </button>
              <button
                onClick={() => setActiveTab('metadata')}
                className={`pb-2.5 px-3 text-xs font-bold flex items-center space-x-1.5 transition-colors border-b-2 ${
                  activeTab === 'metadata'
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-slate-500 hover:text-slate-900'
                }`}
              >
                <FileCode className="w-3.5 h-3.5" />
                <span>Metadata</span>
              </button>
            </div>

            {/* ── Tab Body ── */}
            <div className="flex-grow overflow-y-auto px-6 py-4">
              {activeTab === 'chunks' ? (
                chunks.length === 0 ? (
                  <div className="py-10 text-center text-slate-500 text-xs space-y-2">
                    {doc.processing_status === 'FAILED' ? (
                      <>
                        <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
                        <p className="font-semibold text-red-600">Processing Failed</p>
                        <p>{doc.error_message || 'Unknown error during text extraction.'}</p>
                      </>
                    ) : (
                      <>
                        <Clock className="w-8 h-8 text-amber-400 mx-auto" />
                        <p>No chunks generated yet.</p>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2 mb-3 text-xs text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-xl px-3 py-2">
                      <Info className="w-3.5 h-3.5 flex-shrink-0" />
                      <span>
                        <strong>{chunks.length}</strong> text chunks extracted · ready for RAG vector indexing.
                        Click any chunk to expand.
                      </span>
                    </div>
                    {chunks.map((chk, i) => (
                      <ChunkCard key={chk.id} chk={chk} index={i} />
                    ))}
                  </div>
                )
              ) : (
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {[
                    ['Document ID',    `#${doc.id}`],
                    ['Owner User ID',  `#${doc.owner_id}`],
                    ['Format',         doc.file_type.toUpperCase()],
                    ['Size',           `${(doc.file_size / 1024).toFixed(1)} KB`],
                    ['Category',       doc.document_type.replace(/_/g, ' ')],
                    ['Jurisdiction',   doc.jurisdiction || '—'],
                    ['Matter ID',      doc.matter_id    || '—'],
                    ['Chunk Count',    `${chunks.length} chunks`],
                    ['Uploaded',       new Date(doc.created_at).toLocaleString()],
                    ['Last Updated',   new Date(doc.updated_at).toLocaleString()],
                  ].map(([label, value]) => (
                    <div key={label} className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block mb-0.5">{label}</span>
                      <span className="font-bold text-slate-900 capitalize">{value}</span>
                    </div>
                  ))}
                  <div className="col-span-2 bg-slate-50 p-3 rounded-xl border border-slate-200">
                    <span className="text-[10px] text-slate-500 font-bold uppercase block mb-0.5">SHA-256 Integrity Hash</span>
                    <span className="font-mono text-[10px] text-slate-700 break-all">{doc.file_hash}</span>
                  </div>
                </div>
              )}
            </div>

            {/* ── Footer ── */}
            <div className="px-6 py-4 border-t border-slate-200 flex items-center justify-between">
              <div className="flex items-center space-x-1.5 text-[11px] text-slate-500">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                <span>Owner-scoped access · Encrypted storage</span>
              </div>
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl flex items-center space-x-1.5 transition-all shadow-md shadow-indigo-600/20 disabled:opacity-60"
              >
                {downloading
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <Download className="w-3.5 h-3.5" />
                }
                <span>{downloading ? 'Downloading...' : 'Download Original'}</span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
