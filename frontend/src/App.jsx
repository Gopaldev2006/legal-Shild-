import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import PublicDashboard from './pages/PublicDashboard';
import ProfessionalDashboard from './pages/ProfessionalDashboard';
import AdminDashboard from './pages/AdminDashboard';
import { ShieldCheck, LogOut, User, Lock, Sparkles, Scale, BookOpen, Shield, Home, MessageSquare } from 'lucide-react';

function AppContent() {
  const { user, loading, logout } = useAuth();
  const [currentView, setCurrentView] = useState('landing'); // 'landing', 'login', 'register', 'dashboard'

  // Auto-redirect to dashboard when user logs in
  React.useEffect(() => {
    if (user && (currentView === 'login' || currentView === 'register')) {
      setCurrentView('dashboard');
    }
  }, [user]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center font-sans">
        <div className="text-center space-y-3 p-8 bg-white border border-slate-200 rounded-2xl shadow-xl">
          <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <div className="text-sm font-semibold text-slate-700">Verifying Security Session & Credentials...</div>
          <div className="text-xs text-slate-400">Antigravity RAG Legal AI Platform</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Top Header - Legal Navy Theme */}
      <header className="bg-slate-900 border-b border-slate-800 text-white py-3.5 px-6 shadow-lg sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-3 sm:space-y-0">
          {/* Logo & Title */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setCurrentView('landing')}>
            <div className="p-2 bg-indigo-600/30 border border-indigo-400/40 rounded-xl text-indigo-400 shadow-inner">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-base sm:text-lg font-bold text-white tracking-tight leading-none">
                  LexGuard AI
                </h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                  RAG v2.0
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Permission-Aware AI Assistant for Legal Data Analysis & Precedent Retrieval
              </p>
            </div>
          </div>

          {/* Navigation & Account Controls */}
          <div className="flex items-center space-x-3 w-full sm:w-auto justify-between sm:justify-end">
            <nav className="flex items-center space-x-1 bg-slate-800/80 p-1 rounded-xl border border-slate-700">
              <button
                onClick={() => setCurrentView('landing')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                  currentView === 'landing'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                }`}
              >
                <Home className="w-3.5 h-3.5" />
                <span>Overview</span>
              </button>

              {user ? (
                <button
                  onClick={() => setCurrentView('dashboard')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                    currentView === 'dashboard'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Workspace</span>
                </button>
              ) : (
                <button
                  onClick={() => setCurrentView('dashboard')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                    currentView === 'dashboard'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Public AI</span>
                </button>
              )}
            </nav>

            {user ? (
              <div className="flex items-center space-x-2">
                <div className="bg-slate-800 border border-slate-700 px-3 py-1.5 rounded-xl flex items-center space-x-2 text-xs">
                  <User className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="font-semibold text-slate-200 max-w-[120px] truncate">{user.name}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold tracking-wide ${
                    user.role === 'ADMIN'
                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                      : user.role === 'LEGAL_PROFESSIONAL'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      : 'bg-blue-950 text-blue-300 border border-blue-800'
                  }`}>
                    {user.role}
                  </span>
                </div>

                <button
                  onClick={logout}
                  className="px-3 py-1.5 bg-red-950/60 hover:bg-red-900 text-red-200 border border-red-800/80 rounded-xl text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-sm"
                  title="Sign Out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Sign Out</span>
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2 text-xs">
                <button
                  onClick={() => setCurrentView('login')}
                  className={`px-3.5 py-1.5 rounded-xl font-semibold transition-all ${
                    currentView === 'login'
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'bg-slate-800 text-slate-200 hover:bg-slate-700 border border-slate-700'
                  }`}
                >
                  Sign In
                </button>
                <button
                  onClick={() => setCurrentView('register')}
                  className={`px-3.5 py-1.5 rounded-xl font-semibold transition-all ${
                    currentView === 'register'
                      ? 'bg-emerald-600 text-white shadow-md'
                      : 'bg-emerald-950/80 text-emerald-300 hover:bg-emerald-900 border border-emerald-800'
                  }`}
                >
                  Register
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-grow max-w-7xl w-full mx-auto p-4 sm:p-6">
        {currentView === 'landing' && (
          <LandingPage
            onSelectLogin={() => setCurrentView('login')}
            onSelectRegister={() => setCurrentView('register')}
            onExplorePublic={() => setCurrentView('dashboard')}
          />
        )}

        {currentView === 'login' && !user && (
          <LoginPage onSwitchToRegister={() => setCurrentView('register')} />
        )}

        {currentView === 'register' && !user && (
          <RegisterPage onSwitchToLogin={() => setCurrentView('login')} />
        )}

        {currentView === 'dashboard' && (
          <div>
            {!user && <PublicDashboard />}
            {user?.role === 'PUBLIC_USER' && <PublicDashboard />}
            {user?.role === 'LEGAL_PROFESSIONAL' && <ProfessionalDashboard />}
            {user?.role === 'ADMIN' && <AdminDashboard />}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 px-6 text-center text-xs text-slate-500 mt-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center space-y-2 sm:space-y-0">
          <div>
            <strong>LexGuard AI</strong> • Permission-Aware AI Legal Data Analysis Platform (B.Tech Major Project)
          </div>
          <div className="flex items-center space-x-4 text-slate-600">
            <span>5-Layer Security Firewall</span>
            <span>•</span>
            <span>TinyLlama SLM</span>
            <span>•</span>
            <span>FAISS Grounded RAG</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
