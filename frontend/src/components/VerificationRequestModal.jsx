import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { UploadCloud, X, FileText, CheckCircle, AlertCircle, ShieldCheck, LogOut } from 'lucide-react';

export default function VerificationRequestModal({ isOpen, onClose, onSuccess }) {
  const { token, setUser, logout } = useAuth();
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFile(null);
      setError(null);
      setSuccessMsg(null);
      setUploading(false);
      // Check immediately if session is valid
      const storedToken = token || localStorage.getItem('sec_legal_token');
      setSessionExpired(!storedToken);
    }
  }, [isOpen, token]);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    setError(null);
    if (!selected) return;

    const allowed = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'txt'];
    const ext = selected.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
      setError(`Invalid file type '.${ext}'. Allowed: PDF, PNG, JPG, JPEG, WEBP, TXT`);
      setFile(null);
      return;
    }
    if (selected.size > 10 * 1024 * 1024) {
      setError('File size exceeds 10 MB limit.');
      setFile(null);
      return;
    }
    setFile(selected);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) { setError('Please select a document to upload.'); return; }

    const authToken = token || localStorage.getItem('sec_legal_token');
    if (!authToken) { setSessionExpired(true); return; }

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/v1/verification/request', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` },
        body: formData
      });

      const data = await response.json();
      if (!response.ok) {
        // 401 means token really expired server-side
        if (response.status === 401) { setSessionExpired(true); return; }
        throw new Error(data.detail || 'Failed to submit verification request');
      }

      setSuccessMsg('Verification request submitted! Your document is under Admin review.');
      setUser(prev => prev ? { ...prev, verification_status: 'PENDING' } : prev);

      setTimeout(() => { if (onSuccess) onSuccess(); onClose(); }, 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white border border-slate-200 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">

        {/* Close button */}
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 transition-colors">
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center space-x-3 mb-4">
          <div className="p-3 bg-emerald-50 border border-emerald-100 rounded-2xl text-emerald-600 shadow-sm">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-extrabold text-slate-900">Professional Verification Request</h3>
            <p className="text-xs text-slate-500">Upload Bar Council License or Legal Identity Certificate</p>
          </div>
        </div>

        {/* Session Expired State */}
        {sessionExpired ? (
          <div className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl text-amber-900 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-sm">Session Expired</p>
                <p className="mt-1">Your login session has expired. Please sign out and sign in again to submit your verification request.</p>
              </div>
            </div>
            <div className="flex space-x-3">
              <button type="button" onClick={onClose}
                className="flex-1 py-2.5 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl transition-colors border border-slate-200">
                Cancel
              </button>
              <button type="button" onClick={() => { logout(); onClose(); }}
                className="flex-1 py-2.5 px-4 bg-red-600 hover:bg-red-700 text-white font-bold text-xs rounded-xl transition-all flex items-center justify-center space-x-1.5 shadow-md">
                <LogOut className="w-3.5 h-3.5" />
                <span>Sign Out & Re-login</span>
              </button>
            </div>
          </div>
        ) : (
          /* Normal form */
          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Error */}
            {error && (
              <div className="bg-red-50 border border-red-200 p-3.5 rounded-xl text-red-800 text-xs flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Success */}
            {successMsg && (
              <div className="bg-emerald-50 border border-emerald-200 p-3.5 rounded-xl text-emerald-800 text-xs flex items-start space-x-2">
                <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span>{successMsg}</span>
              </div>
            )}

            {/* Drop zone */}
            <div className="border-2 border-dashed border-slate-200 hover:border-emerald-500/60 rounded-2xl p-6 text-center bg-slate-50/50 transition-colors">
              <UploadCloud className="w-10 h-10 text-emerald-600 mx-auto mb-2" />
              <label className="block text-xs font-bold text-slate-800 mb-1 cursor-pointer">
                <span className="text-emerald-600 hover:underline">Click to choose file</span> or drag &amp; drop
                <input type="file" onChange={handleFileChange} accept=".pdf,.png,.jpg,.jpeg,.webp,.txt" className="hidden" />
              </label>
              <p className="text-[11px] text-slate-500 font-medium">PDF, PNG, JPG, WEBP, TXT up to 10 MB</p>

              {file && (
                <div className="mt-3 p-3 bg-white border border-emerald-100 rounded-xl text-xs text-emerald-900 flex items-center justify-between shadow-sm">
                  <div className="flex items-center space-x-2 truncate font-bold">
                    <FileText className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    <span className="truncate">{file.name}</span>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono ml-2">{(file.size / 1024).toFixed(1)} KB</span>
                </div>
              )}
            </div>

            {/* Info */}
            <div className="bg-slate-50 p-3.5 rounded-xl text-[11px] text-slate-600 space-y-1.5 border border-slate-200 font-medium">
              <div>• SHA-256 cryptographic hash will be calculated for document integrity.</div>
              <div>• Open-source OCR will extract text for Admin verification review.</div>
              <div>• Documents are stored securely outside public web directories.</div>
            </div>

            {/* Buttons */}
            <div className="flex space-x-3 pt-2">
              <button type="button" onClick={onClose}
                className="flex-1 py-2.5 px-4 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl transition-colors border border-slate-200">
                Cancel
              </button>
              <button type="submit" disabled={uploading || !file}
                className="flex-1 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl transition-all disabled:opacity-50 flex items-center justify-center space-x-1.5 shadow-md shadow-emerald-600/20">
                <span>{uploading ? 'Processing OCR & Upload...' : 'Submit Verification'}</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
