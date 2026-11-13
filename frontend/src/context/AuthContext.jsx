import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { ApiError, apiFetch, clearAccessToken, getAccessToken, saveAccessToken } from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionError, setSessionError] = useState('');

  useEffect(() => {
    let isMounted = true;
    const token = getAccessToken();

    if (!token) {
      setIsLoading(false);
      return () => { isMounted = false; };
    }

    apiFetch('/auth/me')
      .then((currentUser) => {
        if (isMounted) setUser(currentUser);
      })
      .catch((error) => {
        if (!isMounted) return;
        if (error instanceof ApiError && error.status === 401) clearAccessToken();
        setSessionError('We could not verify your saved session. Please sign in again.');
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => { isMounted = false; };
  }, []);

  const login = useCallback(async (credentials) => {
    const result = await apiFetch('/auth/login', {
      method: 'POST',
      body: credentials,
      auth: false,
    });
    saveAccessToken(result.access_token);
    setSessionError('');
    setUser(result.user);
    return result.user;
  }, []);

  const register = useCallback((details) => apiFetch('/auth/register', {
    method: 'POST',
    body: details,
    auth: false,
  }), []);

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setSessionError('');
  }, []);

  const value = useMemo(() => ({
    user,
    isAuthenticated: Boolean(user),
    isLoading,
    sessionError,
    login,
    register,
    logout,
  }), [user, isLoading, sessionError, login, register, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider.');
  return context;
}
