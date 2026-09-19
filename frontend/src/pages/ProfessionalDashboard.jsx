import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import DocumentUploadModal from '../components/DocumentUploadModal';
import DocumentDetailsModal from '../components/DocumentDetailsModal';
import CaseDetailsModal from '../components/CaseDetailsModal';
import RAGChatbot from '../components/RAGChatbot';
import DocumentAnalysisPanel from '../components/DocumentAnalysisPanel';
import PersistentChat from '../components/PersistentChat';
import Toast from '../components/Toast';
import { 
  UserCheck, FileText, Database, ShieldCheck, Cpu, UploadCloud, RefreshCw, 
  Eye, Trash2, Search, AlertCircle, Sparkles, Bot, Scale, History, CheckCircle2, 
  Lock, BookOpen, ExternalLink, Calendar, Building2, Layers, Network, Info, Settings as SettingsIcon, Sliders, Shield, MessagesSquare, MessageSquarePlus,
  Monitor, Smartphone, Globe, XCircle, ShieldAlert
} from 'lucide-react';

// ── Active Sessions Panel ─────────────────────────────────────────────────────
function ActiveSessionsPanel({ token, showToast }) {
  const [sessions, setSessions]         = useState([]);
  const [loading, setLoading]           = useState(false);
  const [revoking, setRevoking]         = useState(null); // id of session being revoked
  const [revokingAll, setRevokingAll]   = useState(false);

  const fetchSessions = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch('/api/v1/auth/sessions', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch {
      // silent — non-critical
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSessions(); }, [token]);

  const handleRevoke = async (sessionId) => {
    setRevoking(sessionId);
    try {
      const res = await fetch(`/api/v1/auth/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok || res.status === 204) {
        showToast('success', 'Session revoked.');
        await fetchSessions();
      } else {
        showToast('error', 'Failed to revoke session.');
      }
    } catch {
      showToast('error', 'Network error revoking session.');
    } finally {
      setRevoking(null);
    }
  };

  const handleRevokeAll = async () => {
    if (!window.confirm('Revoke all active sessions? You will be signed out on all devices.')) return;
    setRevokingAll(true);
    try {
      const res = await fetch('/api/v1/auth/sessions/revoke-all', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        showToast('info', data.message || 'All sessions revoked.');
        await fetchSessions();
      } else {
        showToast('error', 'Failed to revoke all sessions.');
      }
    } catch {
      showToast('error', 'Network error.');
    } finally {
      setRevokingAll(false);
    }
  };

  const activeSessions = sessions.filter(s => s.status === 'active');

  const statusBadge = (status) => {
    if (status === 'active')  return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">ACTIVE</span>;
    if (status === 'revoked') return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-50 text-red-700 border border-red-200">REVOKED</span>;
    return                           <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200">EXPIRED</span>;
  };

  return (
    <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="font-bold text-slate-900 flex items-center space-x-2 text-xs uppercase tracking-wider">
          <ShieldAlert className="w-4 h-4 text-indigo-600" />
          <span>Active Sessions</span>
          {activeSessions.length > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-700 border border-indigo-200">
              {activeSessions.length} active
            </span>
          )}
        </h4>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchSessions}
            disabled={loading}
            className="px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded-lg text-[11px] font-bold text-slate-600 flex items-center space-x-1 transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          {activeSessions.length > 0 && (
            <button
              onClick={handleRevokeAll}
              disabled={revokingAll}
              className="px-2.5 py-1 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg text-[11px] font-bold text-red-700 flex items-center space-x-1 transition-colors"
            >
              <XCircle className={`w-3 h-3 ${revokingAll ? 'animate-spin' : ''}`} />
              <span>Revoke All</span>
            </button>
          )}
        </div>
      </div>

      <p className="text-[11px] text-slate-500">
        These are the active login sessions for your account. Revoke any session you don't recognise.
        Revoking a session immediately invalidates that device's token.
      </p>

      {/* Session list */}
      {loading ? (
        <div className="py-6 text-center text-slate-400 text-xs animate-pulse">Loading sessions...</div>
      ) : sessions.length === 0 ? (
        <div className="py-6 text-center text-slate-400 text-xs">No session records found.</div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.id} className="flex items-start justify-between bg-white border border-slate-200 rounded-xl px-4 py-3 text-xs">
              <div className="space-y-0.5 min-w-0">
                <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                  {statusBadge(s.status)}
                  <span className="text-slate-500 truncate max-w-[260px]" title={s.user_agent}>
                    {s.user_agent
                      ? s.user_agent.length > 50
                        ? s.user_agent.slice(0, 50) + '…'
                        : s.user_agent
                      : 'Unknown client'}
                  </span>
                </div>
                <div className="flex items-center space-x-3 text-[10px] text-slate-400 flex-wrap gap-y-0.5">
                  {s.ip_address && <span>IP: {s.ip_address}</span>}
                  <span>Created: {new Date(s.created_at).toLocaleString()}</span>
                  {s.last_used_at && <span>Last used: {new Date(s.last_used_at).toLocaleString()}</span>}
                  <span>Expires: {new Date(s.expires_at).toLocaleString()}</span>
                </div>
              </div>
              {s.status === 'active' && (
                <button
                  onClick={() => handleRevoke(s.id)}
                  disabled={revoking === s.id}
                  className="ml-3 flex-shrink-0 px-2.5 py-1 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg text-[11px] font-bold text-red-700 flex items-center space-x-1 transition-colors disabled:opacity-50"
                >
                  <XCircle className="w-3 h-3" />
                  <span>{revoking === s.id ? '…' : 'Revoke'}</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProfessionalDashboard() {
  const { user, token } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [activeTab, setActiveTab] = useState('rag'); // 'rag', 'documents', 'cases', 'clusters', 'arguments', 'audit', 'settings'
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [selectedCaseId, setSelectedCaseId] = useState(null);

  // Document-linked chat: holds the doc id to pass to PersistentChat when
  // the user clicks "Chat with Document" from the Documents table.
  const [chatDocId, setChatDocId] = useState(null);

  // Toast Notification State
  const [toast, setToast] = useState(null);

  // Settings State
  const [defaultProvider, setDefaultProvider] = useState('local');
  const [defaultTopK, setDefaultTopK] = useState(5);
  const [strictAuthCheck, setStrictAuthCheck] = useState(true);

  // Similar Legal Case Search State
  const [caseQuery, setCaseQuery] = useState('');
  const [caseJurisdictionFilter, setCaseJurisdictionFilter] = useState('');
  const [searchingCases, setSearchingCases] = useState(false);
  const [caseResults, setCaseResults] = useState(null);

  // Case Clustering State
  const [numKClusters, setNumKClusters] = useState(3);
  const [clustering, setClustering] = useState(false);
  const [clusterSummaries, setClusterSummaries] = useState([]);
  const [selectedClusterId, setSelectedClusterId] = useState(null);
  const [selectedClusterDetail, setSelectedClusterDetail] = useState(null);
  const [loadingClusterDetail, setLoadingClusterDetail] = useState(false);

  // Arguments & Verdict Extraction State
  const [extractDocId, setExtractDocId] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [extractedData, setExtractedData] = useState(null);

  // Audit History State
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  const showToast = (type, message) => {
    setToast({ type, message });
  };

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/documents/', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setDocuments(data);
    } catch (err) {
      console.error('Failed to load documents:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchClusters = async () => {
    try {
      const response = await fetch('/api/v1/cases/clusters', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setClusterSummaries(data);
      }
    } catch (err) {
      console.error('Failed to fetch clusters:', err);
    }
  };

  const fetchAuditLogs = async () => {
    setLoadingAudit(true);
    try {
      const response = await fetch('/api/v1/rag/audit-history', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setAuditLogs(data);
      }
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoadingAudit(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [token]);

  useEffect(() => {
    if (activeTab === 'clusters') {
      fetchClusters();
    } else if (activeTab === 'audit') {
      fetchAuditLogs();
    }
  }, [activeTab, token]);

  const handleDelete = async (id, filename) => {
    if (!window.confirm(`Are you sure you want to delete '${filename}'?`)) return;
    try {
      const response = await fetch(`/api/v1/documents/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Delete failed');
      }
      showToast('success', `Document '${filename}' deleted successfully.`);
      await fetchDocuments();
    } catch (err) {
      showToast('error', `Error deleting document: ${err.message}`);
    }
  };

  const handleCaseSearch = async (e) => {
    e.preventDefault();
    if (!caseQuery.trim()) return;

    setSearchingCases(true);
    setCaseResults(null);

    try {
      const response = await fetch('/api/v1/cases/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          query: caseQuery.trim(),
          jurisdiction: caseJurisdictionFilter || undefined,
          top_k: 5
        })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Case search failed');
      }
      setCaseResults(data);
      showToast('info', `Found ${data.total} matching legal precedents.`);
    } catch (err) {
      showToast('error', `Case Search Error: ${err.message}`);
    } finally {
      setSearchingCases(false);
    }
  };

  const handleGenerateClusters = async (e) => {
    if (e) e.preventDefault();
    setClustering(true);
    setSelectedClusterId(null);
    setSelectedClusterDetail(null);

    try {
      const response = await fetch('/api/v1/cases/clusters/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ num_clusters: parseInt(numKClusters) || 3 })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Clustering failed');
      }
      setClusterSummaries(data.clusters || []);
      showToast('success', `K-Means clustering completed into ${numKClusters} clusters.`);
    } catch (err) {
      showToast('error', `Clustering Error: ${err.message}`);
    } finally {
      setClustering(false);
    }
  };

  const handleSelectCluster = async (clusterId) => {
    setSelectedClusterId(clusterId);
    setLoadingClusterDetail(true);

    try {
      const response = await fetch(`/api/v1/cases/clusters/${clusterId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (response.ok) {
        setSelectedClusterDetail(data);
      }
    } catch (err) {
      console.error('Failed to fetch cluster details:', err);
    } finally {
      setLoadingClusterDetail(false);
    }
  };

  const handleExtractArguments = async (e) => {
    e.preventDefault();
    if (!extractDocId) return;

    setExtracting(true);
    setExtractedData(null);

    try {
      const response = await fetch(`/api/v1/rag/extract-arguments/${extractDocId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Arguments extraction failed');
      }
      setExtractedData(data);
      showToast('success', `Extracted legal arguments and verdict summary.`);
    } catch (err) {
      showToast('error', `Extraction error: ${err.message}`);
    } finally {
      setExtracting(false);
    }
  };

  return (
    <div className="space-y-6">
      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}

      {/* Header Banner */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between space-y-4 sm:space-y-0">
        <div className="flex items-center space-x-4">
          <div className="p-3.5 bg-emerald-50 border border-emerald-100 rounded-2xl text-emerald-600 shadow-sm">
            <UserCheck className="w-8 h-8" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-xl font-extrabold text-slate-900">{user?.name || 'Verified Professional'}</h2>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center space-x-1">
                <Lock className="w-3 h-3 text-emerald-600" />
                <span>TIER 2 — VERIFIED LEGAL PROFESSIONAL MODE</span>
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Case-Specific RAG • Authorized Document Repository • Case Clustering Intelligence • Arguments Extraction
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => {
              fetchDocuments();
              showToast('info', 'Document repository refreshed.');
            }}
            disabled={loading}
            className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-all border border-slate-200 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setIsUploadOpen(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center space-x-2 transition-all shadow-md shadow-indigo-600/20"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 space-x-1 overflow-x-auto">
        <button
          onClick={() => setActiveTab('rag')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'rag'
              ? 'bg-white text-indigo-600 border-indigo-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <Bot className="w-4 h-4" />
          <span>Legal Chat</span>
        </button>

        <button
          onClick={() => setActiveTab('chat')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'chat'
              ? 'bg-white text-teal-600 border-teal-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <MessagesSquare className="w-4 h-4" />
          <span>Persistent Chat</span>
        </button>

        <button
          onClick={() => setActiveTab('analysis')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'analysis'
              ? 'bg-white text-violet-600 border-violet-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <Scale className="w-4 h-4" />
          <span>Analysis</span>
        </button>

        <button
          onClick={() => setActiveTab('documents')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'documents'
              ? 'bg-white text-emerald-600 border-emerald-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Documents ({documents.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('cases')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'cases'
              ? 'bg-white text-purple-600 border-purple-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <Scale className="w-4 h-4" />
          <span>Similar Cases</span>
        </button>

        <button
          onClick={() => setActiveTab('clusters')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'clusters'
              ? 'bg-white text-indigo-600 border-indigo-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <Network className="w-4 h-4" />
          <span>Clusters</span>
        </button>

        <button
          onClick={() => setActiveTab('arguments')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'arguments'
              ? 'bg-white text-amber-600 border-amber-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          <span>AI Analysis</span>
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'audit'
              ? 'bg-white text-slate-900 border-slate-900 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Audit</span>
        </button>

        <button
          onClick={() => setActiveTab('settings')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'settings'
              ? 'bg-white text-indigo-600 border-indigo-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <SettingsIcon className="w-4 h-4" />
          <span>Settings</span>
        </button>
      </div>

      {/* Tab 1: Secure RAG Assistant */}
      {activeTab === 'rag' && (
        <RAGChatbot
          onInspectDocument={(docId) => setSelectedDocId(docId)}
          documents={documents}
        />
      )}

      {/* Tab: Persistent Chat — full conversation history */}
      {activeTab === 'chat' && (
        <>
          {/* Document-chat context banner */}
          {chatDocId && (() => {
            const doc = documents.find(d => d.id === chatDocId);
            return doc ? (
              <div className="flex items-center justify-between bg-teal-50 border border-teal-200 rounded-xl px-4 py-2.5 text-xs font-medium text-teal-800">
                <div className="flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-teal-600 flex-shrink-0" />
                  <span className="font-bold">Document Chat:</span>
                  <span className="truncate max-w-[320px]" title={doc.filename}>{doc.filename}</span>
                  <span className="px-2 py-0.5 bg-teal-100 border border-teal-300 text-teal-700 rounded-full text-[10px] font-bold">DOCUMENT MODE</span>
                </div>
                <button
                  onClick={() => setChatDocId(null)}
                  className="px-2.5 py-1 bg-white hover:bg-teal-100 border border-teal-300 text-teal-700 rounded-lg text-[11px] font-bold flex items-center space-x-1 transition-colors"
                  title="Switch to general RAG chat"
                >
                  <MessagesSquare className="w-3 h-3" />
                  <span>Switch to RAG Chat</span>
                </button>
              </div>
            ) : null;
          })()}
          <PersistentChat
            mode={chatDocId ? 'document' : 'rag'}
            documentId={chatDocId}
            documents={documents}
            title={chatDocId ? 'Document Chat' : 'Persistent Legal Chat'}
          />
        </>
      )}

      {/* Tab: Document Analysis Engine */}
      {activeTab === 'analysis' && (
        <DocumentAnalysisPanel documents={documents} />
      )}

      {/* Tab 2: Document Management Table */}
      {activeTab === 'documents' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <FileText className="w-5 h-5 text-indigo-600" />
              <span>My Authorized Legal Documents ({documents.length})</span>
            </h3>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 p-3.5 rounded-xl text-red-800 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="py-12 text-center text-slate-500 text-sm animate-pulse">
              Loading document repository...
            </div>
          ) : documents.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs border-2 border-dashed border-slate-200 rounded-2xl p-6 bg-slate-50/50">
              <UploadCloud className="w-10 h-10 text-slate-400 mx-auto mb-2" />
              <div className="font-bold text-slate-700">No legal documents uploaded yet.</div>
              <p className="text-slate-500 mt-1 mb-3">Upload case briefs, statutory laws, or contracts to enable permission-aware RAG.</p>
              <button
                onClick={() => setIsUploadOpen(true)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
              >
                Upload Your First Document (PDF / DOCX / TXT)
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3.5 px-4 font-bold">Filename</th>
                    <th className="py-3.5 px-4 font-bold">Category</th>
                    <th className="py-3.5 px-4 font-bold">Format & Size</th>
                    <th className="py-3.5 px-4 font-bold">Processing Status</th>
                    <th className="py-3.5 px-4 font-bold">Chunks</th>
                    <th className="py-3.5 px-4 font-bold">Uploaded</th>
                    <th className="py-3.5 px-4 font-bold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-bold text-slate-900 flex items-center space-x-2">
                        <FileText className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                        <span className="truncate max-w-[200px]" title={doc.filename}>{doc.filename}</span>
                      </td>
                      <td className="py-3.5 px-4 capitalize text-slate-600 font-medium">
                        {doc.document_type.replace('_', ' ')}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[11px] text-slate-500">
                        <span className="uppercase text-slate-900 font-bold">{doc.file_type}</span> ({(doc.file_size / 1024).toFixed(1)} KB)
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full font-bold text-[10px] ${
                          doc.processing_status === 'COMPLETED'
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : doc.processing_status === 'FAILED'
                            ? 'bg-red-50 text-red-800 border border-red-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}>
                          {doc.processing_status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="px-2.5 py-1 bg-slate-100 border border-slate-200 rounded-lg text-slate-800 font-mono font-semibold">
                          {doc.chunk_count} chunks
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-[11px] text-slate-500">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3.5 px-4 text-right space-x-2">
                        <button
                          onClick={() => setSelectedDocId(doc.id)}
                          className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-[11px] font-bold inline-flex items-center space-x-1 transition-colors"
                        >
                          <Eye className="w-3 h-3" />
                          <span>Inspect</span>
                        </button>
                        <button
                          onClick={() => {
                            setChatDocId(doc.id);
                            setActiveTab('chat');
                          }}
                          className="px-2.5 py-1 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg text-[11px] font-bold inline-flex items-center space-x-1 transition-colors"
                          title={`Chat with ${doc.filename}`}
                        >
                          <MessageSquarePlus className="w-3 h-3" />
                          <span>Chat</span>
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id, doc.filename)}
                          className="p-1 text-slate-400 hover:text-red-600 transition-colors"
                          title="Delete Document"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Similar Legal Case Retrieval */}
      {activeTab === 'cases' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-purple-50 border border-purple-100 rounded-xl text-purple-600 shadow-sm">
                <Scale className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Similar Legal Case Retrieval Module</h3>
                <p className="text-xs text-slate-500">Semantic similarity search across public academic legal case judgments</p>
              </div>
            </div>
            <span className="px-3 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded-lg text-xs font-bold">
              Public Academic Case Dataset
            </span>
          </div>

          <form onSubmit={handleCaseSearch} className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            <div className="relative flex-grow">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={caseQuery}
                onChange={(e) => setCaseQuery(e.target.value)}
                placeholder="Enter legal facts or query (e.g. arbitration clause in foreign contract or basic structure doctrine)"
                className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:bg-white focus:border-purple-600 focus:ring-2 focus:ring-purple-100 transition-all font-medium"
              />
            </div>

            <input
              type="text"
              value={caseJurisdictionFilter}
              onChange={(e) => setCaseJurisdictionFilter(e.target.value)}
              placeholder="Jurisdiction (Optional)"
              className="w-48 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs text-slate-900 focus:outline-none focus:bg-white focus:border-purple-600 font-medium"
            />

            <button
              type="submit"
              disabled={searchingCases || !caseQuery.trim()}
              className="px-5 py-2.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-xl flex items-center justify-center space-x-1.5 transition-all disabled:opacity-50 shadow-md shadow-purple-600/20"
            >
              <Sparkles className="w-4 h-4" />
              <span>{searchingCases ? 'Searching Cases...' : 'Find Similar Cases'}</span>
            </button>
          </form>

          {caseResults && (
            <div className="mt-4 bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
              <div className="flex items-center justify-between text-xs border-b border-slate-200 pb-2">
                <span className="font-bold text-purple-900">
                  Semantically Matched Cases ({caseResults.total} precedents found)
                </span>
                <span className="text-slate-500">Public Academic Dataset</span>
              </div>

              {caseResults.total === 0 ? (
                <div className="py-6 text-center text-slate-500 text-xs">
                  No matching legal cases found for your query. Try broadening your terms.
                </div>
              ) : (
                <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
                  {caseResults.results.map((c, i) => (
                    <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 text-xs space-y-3 shadow-sm">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="px-2.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200">
                              {c.case_id}
                            </span>
                            <span className="px-2.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                              Score: {c.similarity_score}
                            </span>
                          </div>
                          <h4 className="text-sm font-extrabold text-slate-900">{c.title}</h4>
                          <div className="flex items-center space-x-3 text-[11px] text-slate-500 mt-0.5 font-medium">
                            <span className="flex items-center space-x-1">
                              <Building2 className="w-3 h-3 text-purple-600" />
                              <span>{c.court}</span>
                            </span>
                            <span>•</span>
                            <span className="flex items-center space-x-1">
                              <Calendar className="w-3 h-3 text-indigo-600" />
                              <span>{c.date}</span>
                            </span>
                          </div>
                        </div>

                        <button
                          onClick={() => setSelectedCaseId(c.case_id)}
                          className="px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 rounded-xl text-xs font-bold flex items-center space-x-1 transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          <span>Inspect Precedent</span>
                        </button>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-slate-700 pt-2 border-t border-slate-100">
                        <div>
                          <span className="font-bold text-indigo-700 block mb-1 text-[11px]">Relevant Facts:</span>
                          <p className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 leading-relaxed text-[11px]">
                            {c.relevant_facts}
                          </p>
                        </div>

                        <div>
                          <span className="font-bold text-emerald-700 block mb-1 text-[11px]">Decision & Verdict:</span>
                          <p className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 leading-relaxed text-[11px]">
                            {c.decision}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Case Clusters Intelligence */}
      {activeTab === 'clusters' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-5">
          {/* Header & K-Means Controls */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-slate-200 pb-4 gap-4">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-indigo-50 border border-indigo-100 rounded-xl text-indigo-600 shadow-sm">
                <Network className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">K-Means Case Clustering Intelligence Engine</h3>
                <p className="text-xs text-slate-500">Groups semantically similar cases using K-Means vector embedding proximity</p>
              </div>
            </div>

            <form onSubmit={handleGenerateClusters} className="flex items-center space-x-2">
              <span className="text-xs text-slate-700 font-bold">Clusters (K):</span>
              <select
                value={numKClusters}
                onChange={(e) => setNumKClusters(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-indigo-600 cursor-pointer font-bold"
              >
                <option value={2}>2 Clusters</option>
                <option value={3}>3 Clusters</option>
                <option value={4}>4 Clusters</option>
                <option value={5}>5 Clusters</option>
              </select>

              <button
                type="submit"
                disabled={clustering}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-all disabled:opacity-50 shadow-md shadow-indigo-600/20"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${clustering ? 'animate-spin' : ''}`} />
                <span>{clustering ? 'Clustering...' : 'Run K-Means'}</span>
              </button>
            </form>
          </div>

          {/* AI-Assisted Grouping Mandatory Notice Banner */}
          <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-xl text-xs text-indigo-900 flex items-start space-x-2.5 shadow-sm">
            <Info className="w-4 h-4 text-indigo-600 flex-shrink-0 mt-0.5" />
            <div className="leading-relaxed">
              <span className="font-bold text-indigo-950">AI-Assisted Semantic Grouping Notice: </span>
              Clustering represents an AI-assisted semantic grouping mechanism based on mathematical embedding proximity. 
              It does not determine legal similarity or binding judicial precedent with certainty.
            </div>
          </div>

          {/* Cluster Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {clusterSummaries.map((cl) => (
              <div
                key={cl.cluster_id}
                onClick={() => handleSelectCluster(cl.cluster_id)}
                className={`p-5 rounded-2xl border transition-all cursor-pointer shadow-sm ${
                  selectedClusterId === cl.cluster_id
                    ? 'bg-indigo-50/80 border-indigo-300 ring-2 ring-indigo-500/20'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 mb-3">
                  <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">
                    Cluster #{cl.cluster_id}
                  </span>
                  <span className="text-xs text-slate-500 font-mono font-bold">
                    {cl.case_count} cases
                  </span>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block mb-1">Common Legal Topics:</span>
                    <div className="flex flex-wrap gap-1">
                      {cl.topics.map((t, idx) => (
                        <span key={idx} className="px-2.5 py-0.5 bg-slate-100 text-indigo-800 rounded-md text-[10px] font-bold border border-slate-200">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block mb-1">Representative Cases:</span>
                    <ul className="text-slate-700 text-[11px] space-y-1 list-disc pl-3 font-medium">
                      {cl.representative_cases.map((title, idx) => (
                        <li key={idx} className="truncate" title={title}>{title}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Selected Cluster Case Explorer */}
          {selectedClusterDetail && (
            <div className="mt-6 bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <div className="flex items-center space-x-2">
                  <Layers className="w-5 h-5 text-indigo-600" />
                  <h4 className="text-sm font-bold text-slate-900">
                    Cluster #{selectedClusterDetail.cluster_id} Member Cases ({selectedClusterDetail.case_count})
                  </h4>
                </div>
                <span className="text-xs text-slate-500 font-medium">Click any case to inspect full judgment</span>
              </div>

              {loadingClusterDetail ? (
                <div className="py-6 text-center text-slate-500 text-xs animate-pulse">
                  Loading cluster members...
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {selectedClusterDetail.cases.map((c) => (
                    <div key={c.case_id} className="bg-white p-4 rounded-xl border border-slate-200 text-xs space-y-2.5 shadow-sm">
                      <div className="flex items-start justify-between">
                        <span className="px-2.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200">
                          {c.case_id}
                        </span>
                        <button
                          onClick={() => setSelectedCaseId(c.case_id)}
                          className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-[11px] font-bold flex items-center space-x-1 transition-colors"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span>Inspect</span>
                        </button>
                      </div>

                      <h5 className="font-extrabold text-slate-900">{c.title}</h5>
                      <div className="text-[11px] text-slate-500 font-medium">{c.court} • {c.date}</div>

                      <p className="text-slate-700 text-[11px] line-clamp-2 italic bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                        "{c.relevant_facts}"
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Legal Arguments & Verdict Extraction */}
      {activeTab === 'arguments' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center space-x-3 border-b border-slate-200 pb-4">
            <div className="p-2.5 bg-amber-50 border border-amber-100 rounded-xl text-amber-600 shadow-sm">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Legal Arguments & Verdict Extraction Engine</h3>
              <p className="text-xs text-slate-500">Extracts cited statutes, primary arguments, and verdict summary from authorized documents</p>
            </div>
          </div>

          <form onSubmit={handleExtractArguments} className="flex space-x-3 items-center">
            <select
              value={extractDocId}
              onChange={(e) => setExtractDocId(e.target.value)}
              className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs text-slate-900 focus:outline-none focus:border-amber-600 font-medium"
            >
              <option value="">Select an Authorized Document to Analyze...</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  Doc #{doc.id}: {doc.filename} ({doc.document_type})
                </option>
              ))}
            </select>

            <button
              type="submit"
              disabled={extracting || !extractDocId}
              className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-all disabled:opacity-50 shadow-md shadow-amber-600/20"
            >
              <Scale className="w-4 h-4" />
              <span>{extracting ? 'Extracting...' : 'Extract Legal Details'}</span>
            </button>
          </form>

          {extractedData && (
            <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-4 text-xs">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <span className="font-extrabold text-amber-900 text-sm">{extractedData.filename}</span>
                <span className="text-slate-500 font-mono">Document ID: #{extractedData.document_id}</span>
              </div>

              <div>
                <h4 className="font-bold text-slate-900 mb-2 flex items-center space-x-1.5">
                  <BookOpen className="w-4 h-4 text-indigo-600" />
                  <span>Cited Statutes & Provisions:</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {extractedData.cited_statutes.map((st, idx) => (
                    <span key={idx} className="px-3 py-1 bg-white text-indigo-800 border border-indigo-200 rounded-lg font-mono text-[11px] font-bold shadow-sm">
                      {st}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-bold text-slate-900 mb-2 flex items-center space-x-1.5">
                  <FileText className="w-4 h-4 text-emerald-600" />
                  <span>Key Legal Arguments:</span>
                </h4>
                <ul className="space-y-2 text-slate-700 pl-4 list-disc font-medium">
                  {extractedData.key_arguments.map((arg, idx) => (
                    <li key={idx}>{arg}</li>
                  ))}
                </ul>
              </div>

              <div className="pt-3 border-t border-slate-200">
                <h4 className="font-bold text-slate-900 mb-2 flex items-center space-x-1.5">
                  <CheckCircle2 className="w-4 h-4 text-purple-600" />
                  <span>Verdict & Holding Summary:</span>
                </h4>
                <p className="text-slate-800 leading-relaxed italic bg-white p-4 rounded-xl border border-slate-200 font-medium shadow-sm">
                  {extractedData.verdict_summary}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 6: Audit History Log */}
      {activeTab === 'audit' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center space-x-2">
              <History className="w-5 h-5 text-slate-700" />
              <div>
                <h3 className="text-base font-bold text-slate-900">Professional Query Audit History</h3>
                <p className="text-xs text-slate-500">Security compliance log of executed RAG queries and vector retrieval operations</p>
              </div>
            </div>
            <button
              onClick={() => {
                fetchAuditLogs();
                showToast('info', 'Audit logs updated.');
              }}
              disabled={loadingAudit}
              className="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl flex items-center space-x-1 transition-all border border-slate-200"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingAudit ? 'animate-spin' : ''}`} />
              <span>Refresh Logs</span>
            </button>
          </div>

          {loadingAudit ? (
            <div className="py-8 text-center text-slate-500 text-sm animate-pulse">
              Loading security audit history...
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-xs">
              No audit logs recorded yet. Run a RAG query to generate audit trail records.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3.5 px-4 font-bold">Timestamp</th>
                    <th className="py-3.5 px-4 font-bold">Executed Query</th>
                    <th className="py-3.5 px-4 font-bold">AI Engine Provider</th>
                    <th className="py-3.5 px-4 font-bold">Chunks Retrieved</th>
                    <th className="py-3.5 px-4 font-bold">Safety Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 text-[11px] text-slate-500 whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4 text-slate-900 font-medium max-w-xs truncate" title={log.query_text}>
                        {log.query_text}
                      </td>
                      <td className="py-3.5 px-4 font-bold text-purple-700">
                        {log.provider_used}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold text-slate-800">
                        {log.chunks_retrieved} chunks
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          log.is_safe
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : 'bg-red-50 text-red-800 border border-red-200'
                        }`}>
                          {log.is_safe ? 'VERIFIED SAFE' : 'SECURITY ALERT'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 7: Settings (Page 17) */}
      {activeTab === 'settings' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
          <div className="flex items-center space-x-3 border-b border-slate-200 pb-4">
            <div className="p-2.5 bg-indigo-50 border border-indigo-100 rounded-xl text-indigo-600 shadow-sm">
              <SettingsIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Workspace & AI Security Settings</h3>
              <p className="text-xs text-slate-500">Configure default language model parameters, context chunk depth, and privacy controls</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            {/* AI Model Preferences */}
            <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-4">
              <h4 className="font-bold text-slate-900 flex items-center space-x-2 text-xs uppercase tracking-wider">
                <Sliders className="w-4 h-4 text-indigo-600" />
                <span>AI Model Generation Preferences</span>
              </h4>

              <div className="space-y-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Primary SLM Provider</label>
                  <select
                    value={defaultProvider}
                    onChange={(e) => {
                      setDefaultProvider(e.target.value);
                      showToast('info', `Default model provider updated to ${e.target.value}.`);
                    }}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-600"
                  >
                    <option value="local">Local Small Language Model (TinyLlama-1.1B)</option>
                    <option value="external">External Cloud LLM Provider (API)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">RAG Context Chunk Depth (Top-K)</label>
                  <select
                    value={defaultTopK}
                    onChange={(e) => {
                      setDefaultTopK(parseInt(e.target.value));
                      showToast('info', `Top-K vector context depth updated to ${e.target.value} chunks.`);
                    }}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 font-medium focus:outline-none focus:border-indigo-600"
                  >
                    <option value={3}>Top 3 Chunks (Fastest)</option>
                    <option value={5}>Top 5 Chunks (Balanced - Recommended)</option>
                    <option value={8}>Top 8 Chunks (Comprehensive)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Security & Data Protection Controls */}
            <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-4">
              <h4 className="font-bold text-slate-900 flex items-center space-x-2 text-xs uppercase tracking-wider">
                <Shield className="w-4 h-4 text-emerald-600" />
                <span>Pre-Generation Security Controls</span>
              </h4>

              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div>
                    <div className="font-bold text-slate-900">Owner-Scoped FAISS Pre-Filter</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Purges unauthorized context before prompt construction</div>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    ENFORCED
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div>
                    <div className="font-bold text-slate-900">5-Layer Firewall & PII Redaction</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Scans queries & outputs for leaks and jailbreak attacks</div>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    ACTIVE
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* ── Active Sessions Panel (Phase 4) ── */}
          <ActiveSessionsPanel token={token} showToast={showToast} />
        </div>
      )}

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => {
          fetchDocuments();
          showToast('success', 'New legal document uploaded and indexed.');
        }}
      />

      {/* Details & Chunk Inspection Modal */}
      <DocumentDetailsModal
        documentId={selectedDocId}
        isOpen={!!selectedDocId}
        onClose={() => setSelectedDocId(null)}
      />

      {/* Case Details Inspection Modal */}
      <CaseDetailsModal
        caseId={selectedCaseId}
        isOpen={!!selectedCaseId}
        onClose={() => setSelectedCaseId(null)}
      />
    </div>
  );
}
