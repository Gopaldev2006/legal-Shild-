import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Lock, Mail, ArrowRight, ShieldCheck, AlertCircle, Key, UserCheck, Shield } from 'lucide-react';

export default function LoginPage({ onSwitchToRegister }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setErrorMessage('');
    if (!email || !password) {
      setErrorMessage('Please enter both email and password.');
      return;
    }

    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (!result.success) {
      setErrorMessage(result.error);
    }
  };

  const autofillAccount = (demoEmail, demoPass) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setErrorMessage('');
  };

  return (
    <div className="max-w-md mx-auto my-8 bg-white border border-slate-200 rounded-2xl p-8 shadow-xl">
      <div className="text-center mb-6">
        <div className="inline-flex p-3 bg-indigo-50 border border-indigo-100 rounded-2xl text-indigo-600 mb-3 shadow-sm">
          <ShieldCheck className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Account Sign In</h2>
        <p className="text-xs text-slate-500 mt-1">
          Secure Authorization & Grounded Legal RAG Analytics
        </p>
      </div>

      {/* Demo Quick Login Helper Buttons */}
      <div className="mb-6 bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-2">
        <div className="text-[11px] font-bold text-slate-600 uppercase tracking-wider flex items-center space-x-1">
          <Key className="w-3.5 h-3.5 text-indigo-600" />
          <span>Quick Demo Auto-Fill (University Presentation)</span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => autofillAccount('public@example.com', 'public123')}
            className="px-2 py-1.5 bg-white hover:bg-slate-100 border border-slate-200 rounded-lg text-[11px] font-medium text-slate-700 text-center transition-colors shadow-sm"
          >
            Public User
          </button>
          <button
            type="button"
            onClick={() => autofillAccount('advocate@example.com', 'advocate123')}
            className="px-2 py-1.5 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg text-[11px] font-bold text-emerald-800 text-center transition-colors shadow-sm"
          >
            Advocate (Pro)
          </button>
          <button
            type="button"
            onClick={() => autofillAccount('admin@example.com', 'admin123')}
            className="px-2 py-1.5 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg text-[11px] font-bold text-amber-800 text-center transition-colors shadow-sm"
          >
            System Admin
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="mb-6 bg-red-50 border border-red-200 p-3.5 rounded-xl text-red-800 text-xs flex items-start space-x-2.5 shadow-sm">
          <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1.5">
            Email Address
          </label>
          <div className="relative">
            <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 transition-all font-medium"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1.5">
            Password
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 transition-all font-medium"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full mt-2 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl text-xs flex items-center justify-center space-x-2 shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
        >
          <span>{loading ? 'Authenticating Security Token...' : 'Sign In to Workspace'}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      <div className="mt-6 text-center pt-4 border-t border-slate-200">
        <p className="text-xs text-slate-500">
          Don't have an account yet?{' '}
          <button
            onClick={onSwitchToRegister}
            className="text-indigo-600 hover:underline font-bold"
          >
            Register Public Account
          </button>
        </p>
      </div>
    </div>
  );
}
