import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { User, Mail, Lock, UserPlus, ShieldAlert, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function RegisterPage({ onSwitchToLogin }) {
  const { register } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    if (!name || !email || !password) {
      setErrorMessage('Please fill out all required fields.');
      return;
    }
    if (password.length < 6) {
      setErrorMessage('Password must be at least 6 characters long.');
      return;
    }

    setLoading(true);
    const result = await register(name, email, password);
    setLoading(false);
    if (!result.success) {
      setErrorMessage(result.error);
    }
  };

  return (
    <div className="max-w-md mx-auto my-8 bg-white border border-slate-200 rounded-2xl p-8 shadow-xl">
      <div className="text-center mb-6">
        <div className="inline-flex p-3 bg-emerald-50 border border-emerald-100 rounded-2xl text-emerald-600 mb-3 shadow-sm">
          <UserPlus className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Create User Account</h2>
        <p className="text-xs text-slate-500 mt-1">
          Register for General Public Educational Legal Intelligence
        </p>
      </div>

      {/* Security Role Notice */}
      <div className="mb-6 bg-indigo-50/70 border border-indigo-100 rounded-xl p-3.5 text-xs text-slate-700 flex items-start space-x-2.5 shadow-sm">
        <ShieldAlert className="w-4 h-4 text-indigo-600 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-indigo-900">Default Access Scope: PUBLIC_USER</span>
          <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
            All new user accounts are assigned Public User permissions. Practicing lawyers can submit Bar credentials for Tier 2 Verification after registration.
          </p>
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
            Full Name
          </label>
          <div className="relative">
            <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Adv. Sharma or John Doe"
              className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100 transition-all font-medium"
            />
          </div>
        </div>

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
              className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100 transition-all font-medium"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 mb-1.5">
            Password (min 6 characters)
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:bg-white focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100 transition-all font-medium"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full mt-2 py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-xs flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/20 transition-all disabled:opacity-50"
        >
          <span>{loading ? 'Creating User Profile...' : 'Complete Registration'}</span>
        </button>
      </form>

      <div className="mt-6 text-center pt-4 border-t border-slate-200">
        <p className="text-xs text-slate-500">
          Already registered?{' '}
          <button
            onClick={onSwitchToLogin}
            className="text-emerald-600 hover:underline font-bold"
          >
            Sign In Here
          </button>
        </p>
      </div>
    </div>
  );
}
