import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('sec_legal_token') || null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Auto-verify token on initial load
  useEffect(() => {
    const verifyToken = async () => {
      const storedToken = localStorage.getItem('sec_legal_token');
      if (!storedToken) {
        setLoading(false);
        return;
      }
      try {
        const response = await fetch('/api/v1/auth/me', {
          headers: { 'Authorization': `Bearer ${storedToken}` }
        });
        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
          setToken(storedToken);
        } else {
          logout();
        }
      } catch (err) {
        console.error('Token verification error:', err);
        // Network error - keep token, don't log out
        setLoading(false);
      } finally {
        setLoading(false);
      }
    };

    verifyToken();
  }, []);

  const login = async (email, password) => {
    setAuthError(null);
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Login failed');
      }
      
      localStorage.setItem('sec_legal_token', data.access_token);
      setToken(data.access_token);
      setUser(data.user);
      return { success: true, user: data.user };
    } catch (err) {
      setAuthError(err.message);
      return { success: false, error: err.message };
    }
  };

  const register = async (name, email, password) => {
    setAuthError(null);
    try {
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed');
      }
      
      // Auto login upon successful registration
      return await login(email, password);
    } catch (err) {
      setAuthError(err.message);
      return { success: false, error: err.message };
    }
  };

  const logout = async () => {
    // Tell the server to revoke this session's jti before clearing local state
    const storedToken = localStorage.getItem('sec_legal_token');
    if (storedToken) {
      try {
        await fetch('/api/v1/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${storedToken}` },
        });
      } catch {
        // Network failure — still clear local state; token will expire naturally
      }
    }
    localStorage.removeItem('sec_legal_token');
    setToken(null);
    setUser(null);
    setAuthError(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, authError, login, register, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
