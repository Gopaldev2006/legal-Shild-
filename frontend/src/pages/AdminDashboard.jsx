import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import PaginationControls from '../components/PaginationControls';
import Toast from '../components/Toast';
import {
  Shield, Users, CheckCircle, XCircle, RefreshCw, FileText, Eye, Check, X,
  AlertCircle, Cpu, Database, Lock, Search, Filter, ShieldAlert, Activity, Server, Key, Settings as SettingsIcon, Sliders, ClipboardList
} from 'lucide-react';

export default function AdminDashboard() {
  const { token } = useAuth();

  const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'users', 'verifications', 'documents', 'security', 'audit', 'model', 'settings'

  // Toast State
  const [toast, setToast] = useState(null);
  const showToast = (type, message) => setToast({ type, message });

  // Summary Cards State
  const [summaryData, setSummaryData] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(true);

  // User Management State
  const [userItems, setUserItems] = useState([]);
  const [userTotal, setUserTotal] = useState(0);
  const [userPage, setUserPage] = useState(1);
  const [userTotalPages, setUserTotalPages] = useState(1);
  const [userSearch, setUserSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState('');
  const [userStatusFilter, setUserStatusFilter] = useState('');
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Verification Requests State
  const [verifications, setVerifications] = useState([]);
  const [loadingVerifications, setLoadingVerifications] = useState(false);
  const [reviewNotes, setReviewNotes] = useState({});
  const [processingId, setProcessingId] = useState(null);
  const [selectedOcrText, setSelectedOcrText] = useState(null);

  // Document Repository Audit State
  const [docItems, setDocItems] = useState([]);
  const [docTotal, setDocTotal] = useState(0);
  const [docPage, setDocPage] = useState(1);
  const [docTotalPages, setDocTotalPages] = useState(1);
  const [docSearch, setDocSearch] = useState('');
  const [docStatusFilter, setDocStatusFilter] = useState('');
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Security Events State
  const [secEvents, setSecEvents] = useState([]);
  const [secTotal, setSecTotal] = useState(0);
  const [secPage, setSecPage] = useState(1);
  const [secTotalPages, setSecTotalPages] = useState(1);
  const [secTypeFilter, setSecTypeFilter] = useState('');
  const [secSeverityFilter, setSecSeverityFilter] = useState('');
  const [loadingSec, setLoadingSec] = useState(false);

  // Model Status State
  const [modelStatus, setModelStatus] = useState(null);
  const [loadingModel, setLoadingModel] = useState(false);

  // Audit Log State (Phase 7)
  const [auditItems, setAuditItems]         = useState([]);
  const [auditTotal, setAuditTotal]         = useState(0);
  const [auditPage, setAuditPage]           = useState(1);
  const [auditTotalPages, setAuditTotalPages] = useState(1);
  const [auditEventFilter, setAuditEventFilter] = useState('');
  const [auditSuccessFilter, setAuditSuccessFilter] = useState('');
  const [loadingAuditLogs, setLoadingAuditLogs] = useState(false);

  // API Call Helpers
  const fetchSummary = async () => {
    setLoadingSummary(true);
    try {
      const res = await fetch('/api/v1/admin/dashboard-summary', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSummaryData(data);
      }
    } catch (err) {
      console.error('Failed to load dashboard summary:', err);
    } finally {
      setLoadingSummary(false);
    }
  };

  const fetchUsers = async (p = userPage) => {
    setLoadingUsers(true);
    try {
      const params = new URLSearchParams({ page: p, limit: 10 });
      if (userSearch.trim()) params.append('search', userSearch.trim());
      if (userRoleFilter) params.append('role', userRoleFilter);
      if (userStatusFilter) params.append('verification_status', userStatusFilter);

      const res = await fetch(`/api/v1/admin/users?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUserItems(data.items);
        setUserTotal(data.total);
        setUserTotalPages(data.total_pages);
      }
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const fetchVerifications = async () => {
    setLoadingVerifications(true);
    try {
      const res = await fetch('/api/v1/admin/verifications', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setVerifications(data);
      }
    } catch (err) {
      console.error('Failed to load verifications:', err);
    } finally {
      setLoadingVerifications(false);
    }
  };

  const fetchDocuments = async (p = docPage) => {
    setLoadingDocs(true);
    try {
      const params = new URLSearchParams({ page: p, limit: 10 });
      if (docSearch.trim()) params.append('search', docSearch.trim());
      if (docStatusFilter) params.append('processing_status', docStatusFilter);

      const res = await fetch(`/api/v1/admin/documents?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setDocItems(data.items);
        setDocTotal(data.total);
        setDocTotalPages(data.total_pages);
      }
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoadingDocs(false);
    }
  };

  const fetchSecurityEvents = async (p = secPage) => {
    setLoadingSec(true);
    try {
      const params = new URLSearchParams({ page: p, limit: 10 });
      if (secTypeFilter) params.append('event_type', secTypeFilter);
      if (secSeverityFilter) params.append('severity', secSeverityFilter);

      const res = await fetch(`/api/v1/admin/security-events?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSecEvents(data.items);
        setSecTotal(data.total);
        setSecTotalPages(data.total_pages);
      }
    } catch (err) {
      console.error('Failed to load security events:', err);
    } finally {
      setLoadingSec(false);
    }
  };

  const fetchAuditLogs = async (p = auditPage) => {
    setLoadingAuditLogs(true);
    try {
      const params = new URLSearchParams({ page: p, limit: 20 });
      if (auditEventFilter) params.append('event_type', auditEventFilter);
      if (auditSuccessFilter !== '') params.append('success', auditSuccessFilter);

      const res = await fetch(`/api/v1/admin/audit-logs?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAuditItems(data.items);
        setAuditTotal(data.total);
        setAuditTotalPages(data.total_pages);
      }
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoadingAuditLogs(false);
    }
  };

  const fetchModelStatus = async () => {
    setLoadingModel(true);
    try {
      const res = await fetch('/api/v1/admin/model-status', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setModelStatus(data);
      }
    } catch (err) {
      console.error('Failed to load model status:', err);
    } finally {
      setLoadingModel(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [token]);

  useEffect(() => {
    if (activeTab === 'users') fetchUsers(userPage);
    else if (activeTab === 'verifications') fetchVerifications();
    else if (activeTab === 'documents') fetchDocuments(docPage);
    else if (activeTab === 'security') fetchSecurityEvents(secPage);
    else if (activeTab === 'audit') fetchAuditLogs(1);
    else if (activeTab === 'model') fetchModelStatus();
  }, [activeTab, token]);

  const handleApprove = async (id) => {
    setProcessingId(id);
    try {
      const res = await fetch(`/api/v1/admin/verifications/${id}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ review_notes: reviewNotes[id] || 'Approved by Admin' })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Approval failed');
      }
      showToast('success', `Verification request #${id} approved successfully! User role elevated to LEGAL_PROFESSIONAL.`);
      await fetchVerifications();
      await fetchSummary();
    } catch (err) {
      showToast('error', `Approval error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (id) => {
    setProcessingId(id);
    try {
      const res = await fetch(`/api/v1/admin/verifications/${id}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ review_notes: reviewNotes[id] || 'Rejected by Admin' })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Rejection failed');
      }
      showToast('info', `Verification request #${id} rejected.`);
      await fetchVerifications();
      await fetchSummary();
    } catch (err) {
      showToast('error', `Rejection error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const cards = summaryData?.cards || {};

  return (
    <div className="space-y-6">
      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}

      {/* Admin Header Banner */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between space-y-4 sm:space-y-0">
        <div className="flex items-center space-x-4">
          <div className="p-3.5 bg-amber-50 border border-amber-100 rounded-2xl text-amber-600 shadow-sm">
            <Shield className="w-8 h-8" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-xl font-extrabold text-slate-900">Administrator Control Center</h2>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200 flex items-center space-x-1">
                <Lock className="w-3 h-3 text-amber-600" />
                <span>SYSTEM ADMIN MODE</span>
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              User Management • Professional Verification Queue • System Security Audit • Model Status Monitoring
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            fetchSummary();
            if (activeTab === 'users') fetchUsers(1);
            if (activeTab === 'verifications') fetchVerifications();
            if (activeTab === 'documents') fetchDocuments(1);
            if (activeTab === 'security') fetchSecurityEvents(1);
            if (activeTab === 'model') fetchModelStatus();
            showToast('info', 'System metrics refreshed.');
          }}
          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl flex items-center space-x-1.5 transition-all border border-slate-200 shadow-sm"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh All Metrics</span>
        </button>
      </div>

      {/* 6 Dashboard Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Card 1: Total Users */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase">Total Users</span>
            <Users className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-extrabold text-slate-900">{cards.total_users ?? '-'}</div>
          <div className="text-[10px] text-slate-500 font-medium">Registered Accounts</div>
        </div>

        {/* Card 2: Verified Professionals */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase">Verified Pro</span>
            <CheckCircle className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-extrabold text-emerald-600">{cards.verified_professionals ?? '-'}</div>
          <div className="text-[10px] text-slate-500 font-medium">Legal Advocates</div>
        </div>

        {/* Card 3: Pending Verifications */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase">Pending Queue</span>
            <AlertCircle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-extrabold text-amber-600">{cards.pending_verifications ?? '-'}</div>
          <div className="text-[10px] text-slate-500 font-medium">Review Requests</div>
        </div>

        {/* Card 4: Total Documents */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase">Documents</span>
            <FileText className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-2xl font-extrabold text-slate-900">{cards.total_documents ?? '-'}</div>
          <div className="text-[10px] text-slate-500 font-medium">Indexed Files</div>
        </div>

        {/* Card 5: Total RAG Queries */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase">RAG Queries</span>
            <Database className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-extrabold text-slate-900">{cards.total_rag_queries ?? '-'}</div>
          <div className="text-[10px] text-slate-500 font-medium">Executed Sessions</div>
        </div>

        {/* Card 6: Total Security Events */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase">Security Log</span>
            <ShieldAlert className="w-4 h-4 text-red-600" />
          </div>
          <div className="text-2xl font-extrabold text-red-600">{cards.total_security_events ?? '-'}</div>
          <div className="text-[10px] text-slate-500 font-medium">Threat Alerts</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 space-x-1 overflow-x-auto">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'overview'
              ? 'bg-white text-amber-600 border-amber-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Dashboard</span>
        </button>

        <button
          onClick={() => setActiveTab('users')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'users'
              ? 'bg-white text-indigo-600 border-indigo-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Users</span>
        </button>

        <button
          onClick={() => setActiveTab('verifications')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'verifications'
              ? 'bg-white text-emerald-600 border-emerald-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <CheckCircle className="w-4 h-4" />
          <span>Verifications ({cards.pending_verifications ?? 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('documents')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'documents'
              ? 'bg-white text-purple-600 border-purple-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Documents</span>
        </button>

        <button
          onClick={() => setActiveTab('security')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'security'
              ? 'bg-white text-red-600 border-red-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Security</span>
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'audit'
              ? 'bg-white text-violet-600 border-violet-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <ClipboardList className="w-4 h-4" />
          <span>Audit Logs</span>
        </button>

        <button
          onClick={() => setActiveTab('model')}
          className={`px-4 py-3 text-xs font-bold rounded-t-xl flex items-center space-x-2 transition-all whitespace-nowrap border-b-2 ${
            activeTab === 'model'
              ? 'bg-white text-indigo-600 border-indigo-600 shadow-sm'
              : 'text-slate-500 hover:text-slate-900 border-transparent hover:bg-slate-100/50'
          }`}
        >
          <Cpu className="w-4 h-4" />
          <span>Model Status</span>
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

      {/* Tab 1: System Overview */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2 border-b border-slate-200 pb-3">
              <Server className="w-5 h-5 text-indigo-600" />
              <span>System Health & Resource Metrics</span>
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between items-center bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-slate-600 font-medium">Process Memory Usage (RAM):</span>
                <span className="font-mono font-extrabold text-emerald-700">
                  {summaryData?.system_health?.memory_usage_mb ?? '-'} MB
                </span>
              </div>
              <div className="flex justify-between items-center bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-slate-600 font-medium">System Operational Status:</span>
                <span className="px-3 py-1 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                  {summaryData?.system_health?.status || 'HEALTHY'}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2 border-b border-slate-200 pb-3">
              <Cpu className="w-5 h-5 text-indigo-600" />
              <span>AI Engine Configuration Summary</span>
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between items-center bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-slate-600 font-medium">Active Model Name:</span>
                <span className="font-mono font-bold text-purple-700">
                  {summaryData?.model_status?.model_name || 'TinyLlama/TinyLlama-1.1B-Chat-v1.0'}
                </span>
              </div>
              <div className="flex justify-between items-center bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                <span className="text-slate-600 font-medium">LoRA PEFT Fine-Tuning:</span>
                <span className={`px-3 py-1 rounded-full text-[10px] font-bold ${
                  summaryData?.model_status?.use_finetuned_model
                    ? 'bg-purple-50 text-purple-800 border border-purple-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}>
                  {summaryData?.model_status?.use_finetuned_model ? 'ENABLED (PEFT / LoRA)' : 'BASE MODEL'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: User Management */}
      {activeTab === 'users' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <Users className="w-5 h-5 text-indigo-600" />
              <span>User Administration ({userTotal})</span>
            </h3>
          </div>

          {/* Search & Filter Bar */}
          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            <div className="relative flex-grow">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                placeholder="Search users by name or email..."
                className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-600 font-medium"
              />
            </div>

            <select
              value={userRoleFilter}
              onChange={(e) => setUserRoleFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none cursor-pointer font-medium"
            >
              <option value="">All Roles</option>
              <option value="PUBLIC_USER">PUBLIC_USER</option>
              <option value="LEGAL_PROFESSIONAL">LEGAL_PROFESSIONAL</option>
              <option value="ADMIN">ADMIN</option>
            </select>

            <select
              value={userStatusFilter}
              onChange={(e) => setUserStatusFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none cursor-pointer font-medium"
            >
              <option value="">All Verification Statuses</option>
              <option value="UNVERIFIED">UNVERIFIED</option>
              <option value="PENDING">PENDING</option>
              <option value="VERIFIED">VERIFIED</option>
              <option value="REJECTED">REJECTED</option>
            </select>

            <button
              onClick={() => fetchUsers(1)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl flex items-center justify-center space-x-1.5 transition-all shadow-md shadow-indigo-600/20"
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Filter</span>
            </button>
          </div>

          {loadingUsers ? (
            <div className="py-8 text-center text-slate-500 text-sm animate-pulse">
              Loading users...
            </div>
          ) : userItems.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-xs">
              No users found matching search criteria.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3.5 px-4 font-bold">User ID</th>
                    <th className="py-3.5 px-4 font-bold">Name & Email</th>
                    <th className="py-3.5 px-4 font-bold">Role</th>
                    <th className="py-3.5 px-4 font-bold">Verification Status</th>
                    <th className="py-3.5 px-4 font-bold">Bar Card Number</th>
                    <th className="py-3.5 px-4 font-bold">Joined Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {userItems.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-slate-500">#{u.id}</td>
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-slate-900">{u.name}</div>
                        <div className="text-[11px] text-slate-500">{u.email}</div>
                      </td>
                      <td className="py-3.5 px-4 font-bold">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] ${
                          u.role === 'ADMIN'
                            ? 'bg-amber-50 text-amber-800 border border-amber-200'
                            : u.role === 'LEGAL_PROFESSIONAL'
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : 'bg-indigo-50 text-indigo-800 border border-indigo-200'
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          u.verification_status === 'VERIFIED'
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : u.verification_status === 'REJECTED'
                            ? 'bg-red-50 text-red-800 border border-red-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}>
                          {u.verification_status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-700">
                        {u.bar_card_number || '-'}
                      </td>
                      <td className="py-3.5 px-4 text-[11px] text-slate-500">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <PaginationControls
                page={userPage}
                totalPages={userTotalPages}
                totalItems={userTotal}
                limit={10}
                onPageChange={(p) => {
                  setUserPage(p);
                  fetchUsers(p);
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Verification Queue */}
      {activeTab === 'verifications' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <CheckCircle className="w-5 h-5 text-emerald-600" />
              <span>Professional Credential Verification Queue ({verifications.length})</span>
            </h3>
          </div>

          {loadingVerifications ? (
            <div className="py-8 text-center text-slate-500 text-sm animate-pulse">
              Loading verification queue...
            </div>
          ) : verifications.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-xs">
              No verification requests submitted yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3.5 px-4 font-bold">Req ID</th>
                    <th className="py-3.5 px-4 font-bold">Applicant</th>
                    <th className="py-3.5 px-4 font-bold">Bar Card #</th>
                    <th className="py-3.5 px-4 font-bold">OCR Text</th>
                    <th className="py-3.5 px-4 font-bold">Status</th>
                    <th className="py-3.5 px-4 font-bold">Review Notes</th>
                    <th className="py-3.5 px-4 font-bold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {verifications.map((req) => (
                    <tr key={req.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-slate-500">#{req.id}</td>
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-slate-900">{req.applicant_name}</div>
                        <div className="text-[11px] text-slate-500">{req.applicant_email}</div>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-700">
                        {req.bar_card_number || '-'}
                      </td>
                      <td className="py-3.5 px-4">
                        {req.extracted_text ? (
                          <button
                            onClick={() => setSelectedOcrText(req.extracted_text)}
                            className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-[11px] font-bold flex items-center space-x-1 transition-colors"
                          >
                            <Eye className="w-3 h-3" />
                            <span>Inspect OCR</span>
                          </button>
                        ) : (
                          <span className="text-slate-400 italic">None</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full font-bold text-[11px] ${
                          req.status === 'VERIFIED'
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : req.status === 'REJECTED'
                            ? 'bg-red-50 text-red-800 border border-red-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}>
                          {req.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        {req.status === 'PENDING' ? (
                          <input
                            type="text"
                            placeholder="Review note..."
                            value={reviewNotes[req.id] || ''}
                            onChange={(e) => setReviewNotes({ ...reviewNotes, [req.id]: e.target.value })}
                            className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-[11px] text-slate-900 focus:outline-none focus:border-amber-600"
                          />
                        ) : (
                          <span className="text-slate-500 text-[11px]">{req.review_notes || '-'}</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        {req.status === 'PENDING' ? (
                          <div className="flex items-center justify-end space-x-2">
                            <button
                              onClick={() => handleApprove(req.id)}
                              disabled={processingId === req.id}
                              className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[11px] font-bold transition-all flex items-center space-x-1 disabled:opacity-50 shadow-sm"
                            >
                              <Check className="w-3 h-3" />
                              <span>Approve</span>
                            </button>
                            <button
                              onClick={() => handleReject(req.id)}
                              disabled={processingId === req.id}
                              className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded-lg text-[11px] font-bold transition-all flex items-center space-x-1 disabled:opacity-50 shadow-sm"
                            >
                              <X className="w-3 h-3" />
                              <span>Reject</span>
                            </button>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-[11px]">Completed</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Document Repository Audit */}
      {activeTab === 'documents' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <FileText className="w-5 h-5 text-purple-600" />
              <span>System-Wide Document Audit ({docTotal})</span>
            </h3>
          </div>

          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            <div className="relative flex-grow">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
                placeholder="Search documents by filename..."
                className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:border-purple-600 font-medium"
              />
            </div>

            <select
              value={docStatusFilter}
              onChange={(e) => setDocStatusFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none cursor-pointer font-medium"
            >
              <option value="">All Processing Statuses</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="PENDING">PENDING</option>
              <option value="FAILED">FAILED</option>
            </select>

            <button
              onClick={() => fetchDocuments(1)}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-xl flex items-center justify-center space-x-1.5 transition-all shadow-md shadow-purple-600/20"
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Filter</span>
            </button>
          </div>

          {loadingDocs ? (
            <div className="py-8 text-center text-slate-500 text-sm animate-pulse">
              Loading document audit list...
            </div>
          ) : docItems.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-xs">
              No documents found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3.5 px-4 font-bold">Doc ID</th>
                    <th className="py-3.5 px-4 font-bold">Filename</th>
                    <th className="py-3.5 px-4 font-bold">Document Type</th>
                    <th className="py-3.5 px-4 font-bold">Owner Email</th>
                    <th className="py-3.5 px-4 font-bold">Status</th>
                    <th className="py-3.5 px-4 font-bold">Chunks</th>
                    <th className="py-3.5 px-4 font-bold">Uploaded Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {docItems.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-slate-500">#{d.id}</td>
                      <td className="py-3.5 px-4 font-bold text-slate-900">{d.filename}</td>
                      <td className="py-3.5 px-4 capitalize text-slate-600 font-medium">{d.document_type.replace('_', ' ')}</td>
                      <td className="py-3.5 px-4 text-slate-700">{d.owner_email}</td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          d.processing_status === 'COMPLETED'
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}>
                          {d.processing_status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold">{d.chunk_count} chunks</td>
                      <td className="py-3.5 px-4 text-[11px] text-slate-500">
                        {d.created_at ? new Date(d.created_at).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <PaginationControls
                page={docPage}
                totalPages={docTotalPages}
                totalItems={docTotal}
                limit={10}
                onPageChange={(p) => {
                  setDocPage(p);
                  fetchDocuments(p);
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Security & Threat Events */}
      {activeTab === 'security' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <ShieldAlert className="w-5 h-5 text-red-600" />
              <span>System Threat & Security Events Audit ({secTotal})</span>
            </h3>
          </div>

          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            <select
              value={secTypeFilter}
              onChange={(e) => setSecTypeFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none cursor-pointer font-medium"
            >
              <option value="">All Security Event Types</option>
              <option value="direct_injection">direct_injection</option>
              <option value="indirect_document_injection">indirect_document_injection</option>
              <option value="system_prompt_leak">system_prompt_leak</option>
              <option value="matter_access_refusal">matter_access_refusal</option>
              <option value="pii_redaction">pii_redaction</option>
            </select>

            <select
              value={secSeverityFilter}
              onChange={(e) => setSecSeverityFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none cursor-pointer font-medium"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="INFO">INFO</option>
            </select>

            <button
              onClick={() => fetchSecurityEvents(1)}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-xl flex items-center justify-center space-x-1.5 transition-all shadow-md shadow-red-600/20"
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Filter Security Logs</span>
            </button>
          </div>

          {loadingSec ? (
            <div className="py-8 text-center text-slate-500 text-sm animate-pulse">
              Loading security logs...
            </div>
          ) : secEvents.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-xs">
              No security threat events recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3.5 px-4 font-bold">Timestamp</th>
                    <th className="py-3.5 px-4 font-bold">Event Type</th>
                    <th className="py-3.5 px-4 font-bold">Severity</th>
                    <th className="py-3.5 px-4 font-bold">User ID</th>
                    <th className="py-3.5 px-4 font-bold">Snippet Preview / Rules</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {secEvents.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                        {new Date(ev.timestamp).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4 font-bold text-slate-900">
                        {ev.event_type}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          ev.severity === 'CRITICAL'
                            ? 'bg-red-50 text-red-800 border border-red-200'
                            : ev.severity === 'HIGH'
                            ? 'bg-amber-50 text-amber-800 border border-amber-200'
                            : 'bg-indigo-50 text-indigo-800 border border-indigo-200'
                        }`}>
                          {ev.severity}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-mono">User #{ev.user_id}</td>
                      <td className="py-3.5 px-4 text-[11px] text-slate-700 max-w-xs truncate font-mono" title={ev.snippet_preview || JSON.stringify(ev.details)}>
                        {ev.snippet_preview || JSON.stringify(ev.details)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <PaginationControls
                page={secPage}
                totalPages={secTotalPages}
                totalItems={secTotal}
                limit={10}
                onPageChange={(p) => {
                  setSecPage(p);
                  fetchSecurityEvents(p);
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Tab 6: Security Audit Logs (Phase 7) */}
      {activeTab === 'audit' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <ClipboardList className="w-5 h-5 text-violet-600" />
              <span>Security Audit Logs ({auditTotal})</span>
            </h3>
            <p className="text-[11px] text-slate-500">Append-only accountability records — no secrets stored</p>
          </div>

          {/* Filters */}
          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-2">
            <select
              value={auditEventFilter}
              onChange={(e) => setAuditEventFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none cursor-pointer font-medium"
            >
              <option value="">All Event Types</option>
              <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
              <option value="LOGIN_FAILURE">LOGIN_FAILURE</option>
              <option value="LOGOUT">LOGOUT</option>
              <option value="SESSION_REVOKED">SESSION_REVOKED</option>
              <option value="SESSION_REVOKE_ALL">SESSION_REVOKE_ALL</option>
              <option value="DOCUMENT_UPLOADED">DOCUMENT_UPLOADED</option>
              <option value="DOCUMENT_ACCESSED">DOCUMENT_ACCESSED</option>
              <option value="DOCUMENT_ANALYZED">DOCUMENT_ANALYZED</option>
              <option value="DOCUMENT_DELETED">DOCUMENT_DELETED</option>
              <option value="RAG_QUERY">RAG_QUERY</option>
              <option value="CHAT_CREATED">CHAT_CREATED</option>
              <option value="CHAT_DELETED">CHAT_DELETED</option>
              <option value="API_KEY_ADDED">API_KEY_ADDED</option>
              <option value="API_KEY_REMOVED">API_KEY_REMOVED</option>
              <option value="ACCESS_DENIED">ACCESS_DENIED</option>
              <option value="VERIFICATION_APPROVED">VERIFICATION_APPROVED</option>
              <option value="VERIFICATION_REJECTED">VERIFICATION_REJECTED</option>
            </select>

            <select
              value={auditSuccessFilter}
              onChange={(e) => setAuditSuccessFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none cursor-pointer font-medium"
            >
              <option value="">All Outcomes</option>
              <option value="true">Success</option>
              <option value="false">Failure / Denied</option>
            </select>

            <button
              onClick={() => { setAuditPage(1); fetchAuditLogs(1); }}
              disabled={loadingAuditLogs}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-xs font-bold rounded-xl flex items-center justify-center space-x-1.5 transition-all shadow-md shadow-violet-600/20"
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Filter</span>
            </button>
          </div>

          {loadingAuditLogs ? (
            <div className="py-8 text-center text-slate-500 text-sm animate-pulse">Loading audit logs...</div>
          ) : auditItems.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-xs">No audit log entries found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3.5 px-4 font-bold">Timestamp</th>
                    <th className="py-3.5 px-4 font-bold">Event</th>
                    <th className="py-3.5 px-4 font-bold">User</th>
                    <th className="py-3.5 px-4 font-bold">Resource</th>
                    <th className="py-3.5 px-4 font-bold">Status</th>
                    <th className="py-3.5 px-4 font-bold">Metadata</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {auditItems.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-4 text-[11px] text-slate-500 whitespace-nowrap font-mono">
                        {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          log.event_type.includes('FAIL') || log.event_type.includes('DENIED')
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : log.event_type.includes('DELETE') || log.event_type.includes('REVOKE')
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}>
                          {log.event_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[11px] text-slate-600">
                        {log.user_email || (log.user_id ? `#${log.user_id}` : '—')}
                      </td>
                      <td className="py-3 px-4 text-[11px] text-slate-600">
                        {log.resource_type ? (
                          <span>{log.resource_type}{log.resource_id ? ` #${log.resource_id}` : ''}</span>
                        ) : '—'}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          log.success
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-red-50 text-red-700 border border-red-200'
                        }`}>
                          {log.success ? 'OK' : 'FAIL'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[11px] text-slate-500 font-mono truncate max-w-[180px]" title={log.metadata}>
                        {log.metadata || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <PaginationControls
                page={auditPage}
                totalPages={auditTotalPages}
                totalItems={auditTotal}
                limit={20}
                onPageChange={(p) => { setAuditPage(p); fetchAuditLogs(p); }}
              />
            </div>
          )}
        </div>
      )}

      {/* Tab 6: Model Status */}
      {activeTab === 'model' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
              <Cpu className="w-5 h-5 text-indigo-600" />
              <span>Small Language Model (SLM) Operational Status</span>
            </h3>
          </div>

          {loadingModel ? (
            <div className="py-8 text-center text-slate-500 text-sm animate-pulse">
              Loading model configuration status...
            </div>
          ) : modelStatus && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                <span className="text-[10px] text-slate-500 uppercase font-bold block">HuggingFace Base Model:</span>
                <div className="font-mono font-bold text-purple-700 text-sm">{modelStatus.base_model}</div>
              </div>

              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                <span className="text-[10px] text-slate-500 uppercase font-bold block">LoRA PEFT Fine-Tuning Status:</span>
                <span className={`px-3 py-1 rounded-full text-xs font-bold inline-block ${
                  modelStatus.use_finetuned_model
                    ? 'bg-purple-50 text-purple-800 border border-purple-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}>
                  {modelStatus.use_finetuned_model ? 'ACTIVE (Base Model + LoRA Adapter)' : 'BASE MODEL ACTIVE'}
                </span>
              </div>

              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                <span className="text-[10px] text-slate-500 uppercase font-bold block">Target Hardware Device:</span>
                <div className="font-mono font-bold text-emerald-700">{modelStatus.device}</div>
              </div>

              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                <span className="text-[10px] text-slate-500 uppercase font-bold block">Generation Parameters:</span>
                <div className="font-mono text-slate-700 font-medium">
                  Max Tokens: {modelStatus.max_new_tokens} • Temp: {modelStatus.temperature}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 7: Settings (Page 17) */}
      {activeTab === 'settings' && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
          <div className="flex items-center space-x-3 border-b border-slate-200 pb-4">
            <div className="p-2.5 bg-amber-50 border border-amber-100 rounded-xl text-amber-600 shadow-sm">
              <SettingsIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">System Admin Policy & Security Settings</h3>
              <p className="text-xs text-slate-500">Configure global RBAC constraints, logging levels, and system health policies</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-4">
              <h4 className="font-bold text-slate-900 flex items-center space-x-2 text-xs uppercase tracking-wider">
                <Sliders className="w-4 h-4 text-amber-600" />
                <span>Global System Policies</span>
              </h4>

              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div>
                    <div className="font-bold text-slate-900">JWT Token Expiry Window</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Session security token timeout duration</div>
                  </div>
                  <span className="font-mono font-bold text-slate-800">8 Hours</span>
                </div>

                <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div>
                    <div className="font-bold text-slate-900">Default Rate Limiter</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Maximum requests allowed per client IP</div>
                  </div>
                  <span className="font-mono font-bold text-slate-800">100 req/min</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-4">
              <h4 className="font-bold text-slate-900 flex items-center space-x-2 text-xs uppercase tracking-wider">
                <Shield className="w-4 h-4 text-red-600" />
                <span>Threat Alerting & Audit Log Persistence</span>
              </h4>

              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div>
                    <div className="font-bold text-slate-900">Security Audit Log Database</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Persistent SQLite event trail</div>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    ACTIVE
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                  <div>
                    <div className="font-bold text-slate-900">OCR Document Extractor Engine</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Open-source Tesseract OCR fallback</div>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    READY
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* OCR Inspection Modal */}
      {selectedOcrText && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setSelectedOcrText(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2 mb-4">
              <FileText className="w-5 h-5 text-indigo-600" />
              <h4 className="font-bold text-slate-900 text-base">OCR Text Extraction Result</h4>
            </div>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 max-h-80 overflow-y-auto font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed">
              {selectedOcrText}
            </div>

            <div className="mt-4 text-right">
              <button
                onClick={() => setSelectedOcrText(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl border border-slate-200"
              >
                Close Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
