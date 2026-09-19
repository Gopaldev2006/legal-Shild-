import React, { useState, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  UploadCloud, X, FileText, CheckCircle, AlertCircle,
  FileCode, Loader2, Hash, Layers, Info
} from 'lucide-react';

const ALLOWED_EXTS = ['pdf', 'docx', 'txt'];
const MAX_SIZE_MB = 15;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

const DOC_TYPES = [
  { value: 'case_brief',   label: 'Case Brief' },
  { value: 'statute',      label: 'Statute / Law' },
  { value: 'court_order',  label: 'Court Order / Judgment' },
  { value: 'contract',     label: 'Legal Contract' },
  { value: 'general',      label: 'General Legal Text' },
];

function FileIcon({ ext }) {
  const colors = { pdf: 'text-red-500', docx: 'text-blue-500', txt: 'text-slate-500' };
  return <FileText className={`w-5 h-5 ${colors[ext] || 'text-indigo-500'} flex-shrink-0`} />;
}

export default function DocumentUploadModal({ isOpen, onClose, onSuccess }) {
  const { token } = useAuth();

  const [file, setFile]               = useState(null);
  const [documentType, setDocumentType] = useState('case_brief');
  const [jurisdiction, setJurisdiction] = useState('');
  const [matterId, setMatterId]         = useState('');
  const [uploading, setUploading]       = useState(false);
  const [progress, setProgress]         = useState(0);   // 0-100
  const [error, setError]               = useState(null);
  const [result, setResult]             = useState(null);
  const [isDragging, setIsDragging]     = useState(false);

  const inputRef = useRef(null);

  // ── validation ────────────────────────────────────────────────
  const validateFile = (selected) => {
    if (!selected) return 'No file selected.';
    const ext = selected.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext))
      return `Unsupported format ".${ext}". Allowed: PDF, DOCX, TXT`;
    if (selected.size > MAX_SIZE_BYTES)
      return `File exceeds ${MAX_SIZE_MB} MB limit (${(selected.size / 1024 / 1024).toFixed(1)} MB).`;
    if (selected.size === 0)
      return 'File is empty.';
    return null;
  };

  const applyFile = (selected) => {
    setError(null);
    setResult(null);
    const err = validateFile(selected);
    if (err) { setError(err); setFile(null); return; }
    setFile(selected);
  };

  // ── input change ──────────────────────────────────────────────
  const handleFileChange = (e) => applyFile(e.target.files[0]);

  // ── drag & drop ───────────────────────────────────────────────
  const handleDragOver  = useCallback((e) => { e.preventDefault(); setIsDragging(true);  }, []);
  const handleDragLeave = useCallback((e) => { e.preventDefault(); setIsDragging(false); }, []);
  const handleDrop      = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    applyFile(e.dataTransfer.files[0]);
  }, []);

  // ── upload ────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) { setError('Please select a document.'); return; }

    setUploading(true);
    setError(null);
    setResult(null);
    setProgress(10);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    if (jurisdiction.trim()) formData.append('jurisdiction', jurisdiction.trim());
    if (matterId.trim())     formData.append('matter_id',    matterId.trim());

    // Use XHR so we get upload progress events
    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable)
        setProgress(Math.round((ev.loaded / ev.total) * 70));   // 0-70 during upload
    };

    xhr.onload = () => {
      setProgress(90);
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          setProgress(100);
          setResult(data);
          setUploading(false);
          setTimeout(() => {
            if (onSuccess) onSuccess();
            handleClose();
          }, 2000);
        } else {
          setError(data.detail || 'Upload failed.');
          setUploading(false);
        }
      } catch {
        setError('Unexpected server response.');
        setUploading(false);
      }
    };

    xhr.onerror = () => {
      setError('Network error. Is the backend running?');
      setUploading(false);
    };

    xhr.open('POST', '/api/v1/documents/upload');
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(formData);
  };

  // ── reset & close ─────────────────────────────────────────────
  const handleClose = () => {
    setFile(null);
    setDocumentType('case_brief');
    setJurisdiction('');
    setMatterId('');
    setUploading(false);
    setProgress(0);
    setError(null);
    setResult(null);
    setIsDragging(false);
    onClose();
  };

  if (!isOpen) return null;

  const ext = file ? file.name.split('.').pop().toLowerCase() : '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white border border-slate-200 rounded-2xl max-w-lg w-full shadow-2xl relative flex flex-col max-h-[92vh]">

        {/* ── Header ── */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-50 border border-indigo-100 rounded-xl text-indigo-600">
              <FileCode className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">Upload Legal Document</h3>
              <p className="text-[11px] text-slate-500">PDF · DOCX · TXT — up to {MAX_SIZE_MB} MB</p>
            </div>
          </div>
          <button onClick={handleClose} disabled={uploading}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-40">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="overflow-y-auto p-6 space-y-4 flex-grow">

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 p-3 rounded-xl text-red-800 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Success */}
          {result && (
            <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-xl text-emerald-900 text-xs space-y-2">
              <div className="flex items-center space-x-2 font-bold text-sm">
                <CheckCircle className="w-5 h-5 text-emerald-600" />
                <span>Document processed successfully!</span>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-1">
                <div className="bg-white rounded-lg p-2.5 border border-emerald-100">
                  <span className="text-[10px] text-emerald-700 font-bold uppercase block">Status</span>
                  <span className="font-extrabold text-emerald-900">{result.processing_status}</span>
                </div>
                <div className="bg-white rounded-lg p-2.5 border border-emerald-100">
                  <span className="text-[10px] text-emerald-700 font-bold uppercase block">Text Chunks</span>
                  <span className="font-extrabold text-emerald-900 flex items-center space-x-1">
                    <Layers className="w-3 h-3" />
                    <span>{result.chunk_count} chunks created</span>
                  </span>
                </div>
              </div>
              <div className="bg-white rounded-lg p-2.5 border border-emerald-100 font-mono text-[10px] text-slate-600 flex items-center space-x-1.5 truncate">
                <Hash className="w-3 h-3 text-indigo-500 flex-shrink-0" />
                <span className="truncate">{result.file_hash}</span>
              </div>
            </div>
          )}

          {/* Drag & Drop Zone */}
          {!result && (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !uploading && inputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-7 text-center transition-all cursor-pointer select-none
                ${isDragging
                  ? 'border-indigo-500 bg-indigo-50/60 scale-[1.01]'
                  : 'border-slate-200 hover:border-indigo-400 hover:bg-slate-50/50 bg-slate-50/30'}
                ${uploading ? 'pointer-events-none opacity-60' : ''}`}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
                className="hidden"
              />

              {file ? (
                <div className="flex items-center justify-between bg-white border border-indigo-100 rounded-xl px-4 py-3 shadow-sm text-left">
                  <div className="flex items-center space-x-3 truncate">
                    <FileIcon ext={ext} />
                    <div className="truncate">
                      <p className="font-bold text-xs text-slate-900 truncate">{file.name}</p>
                      <p className="text-[10px] text-slate-500 font-mono">
                        {(file.size / 1024).toFixed(1)} KB · {ext.toUpperCase()}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setFile(null); setError(null); }}
                    className="ml-2 p-1 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <>
                  <UploadCloud className={`w-10 h-10 mx-auto mb-2 transition-colors ${isDragging ? 'text-indigo-500' : 'text-slate-400'}`} />
                  <p className="text-xs font-bold text-slate-700">
                    {isDragging ? 'Drop your file here' : 'Drag & drop your document here'}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    or <span className="text-indigo-600 font-semibold underline">click to browse</span>
                  </p>
                  <p className="text-[10px] text-slate-400 mt-2 font-mono">PDF · DOCX · TXT · max {MAX_SIZE_MB} MB</p>
                </>
              )}
            </div>
          )}

          {/* Upload Progress Bar */}
          {uploading && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px] text-slate-600 font-semibold">
                <span className="flex items-center space-x-1.5">
                  <Loader2 className="w-3 h-3 animate-spin text-indigo-600" />
                  <span>{progress < 70 ? 'Uploading...' : progress < 95 ? 'Extracting text & chunking...' : 'Finalizing...'}</span>
                </span>
                <span className="font-mono">{progress}%</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-600 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Form Fields */}
          {!result && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">Document Category</label>
                  <select
                    value={documentType}
                    onChange={(e) => setDocumentType(e.target.value)}
                    disabled={uploading}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-medium disabled:opacity-60"
                  >
                    {DOC_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">Matter / Case ID <span className="text-slate-400 font-normal">(optional)</span></label>
                  <input
                    type="text"
                    value={matterId}
                    onChange={(e) => setMatterId(e.target.value)}
                    placeholder="e.g. CAS-2026-901"
                    disabled={uploading}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-medium disabled:opacity-60"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">Jurisdiction <span className="text-slate-400 font-normal">(optional)</span></label>
                <input
                  type="text"
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                  placeholder="e.g. Supreme Court of India · High Court of Delhi"
                  disabled={uploading}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-medium disabled:opacity-60"
                />
              </div>

              {/* Info Note */}
              <div className="flex items-start space-x-2 bg-blue-50 border border-blue-100 rounded-xl p-3 text-[11px] text-blue-800">
                <Info className="w-3.5 h-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
                <span>
                  Text will be extracted, cleaned, and split into searchable chunks.
                  SHA-256 hash is computed for integrity verification.
                  Files are stored securely outside the public web directory.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        {!result && (
          <div className="p-6 pt-0 flex space-x-3">
            <button
              type="button"
              onClick={handleClose}
              disabled={uploading}
              className="flex-1 py-2.5 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl transition-colors border border-slate-200 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={uploading || !file}
              className="flex-1 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl transition-all disabled:opacity-50 flex items-center justify-center space-x-2 shadow-md shadow-indigo-600/20"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Upload & Extract Text</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
