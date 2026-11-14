import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client.js';
import { roleHomePath } from '../auth/roles.js';
import { useAuth } from '../context/AuthContext.jsx';

export function LoginPage() {
  const { login, sessionError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const user = await login({ email: email.trim(), password });
      const requestedPath = location.state?.from?.pathname;
      const returnToCheckout = user.role === 'CUSTOMER' && requestedPath === '/checkout';
      navigate(returnToCheckout ? requestedPath : requestedPath === roleHomePath(user.role) ? requestedPath : roleHomePath(user.role), { replace: true });
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Sign-in failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-card">
      <p className="eyebrow">Welcome back</p>
      <h1 className="auth-title">Sign in</h1>
      <p className="auth-intro">Use your CampusBite account to continue.</p>
      {sessionError && <p className="form-message form-message--error" role="status">{sessionError}</p>}
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <label className="form-field">
          <span>Email</span>
          <input type="email" name="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="form-field">
          <span>Password</span>
          <input type="password" name="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button className="form-submit" type="submit" disabled={isSubmitting || !email.trim() || !password}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="auth-switch">New to CampusBite? <Link to="/register">Create a customer account</Link></p>
    </main>
  );
}
