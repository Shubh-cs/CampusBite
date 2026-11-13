import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../api/client.js';
import { useAuth } from '../context/AuthContext.jsx';

export function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [created, setCreated] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    if (fullName.trim().length < 2) {
      setError('Enter your name (at least 2 characters).');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Enter a valid email address.');
      return;
    }
    if (password.length < 8) {
      setError('Choose a password with at least 8 characters.');
      return;
    }
    if (new TextEncoder().encode(password).length > 72) {
      setError('Password must be no more than 72 UTF-8 bytes.');
      return;
    }

    setIsSubmitting(true);
    try {
      await register({ full_name: fullName.trim(), email: email.trim(), password });
      setCreated(true);
      setPassword('');
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Account creation failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (created) {
    return (
      <main className="auth-card">
        <p className="eyebrow">Account created</p>
        <h1 className="auth-title">You’re all set.</h1>
        <p className="auth-intro">Your customer account is ready. Sign in to continue.</p>
        <Link className="form-submit form-submit--link" to="/login">Continue to sign in</Link>
      </main>
    );
  }

  return (
    <main className="auth-card">
      <p className="eyebrow">Join CampusBite</p>
      <h1 className="auth-title">Create account</h1>
      <p className="auth-intro">Customer accounts are open for registration.</p>
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <label className="form-field">
          <span>Full name</span>
          <input type="text" name="full_name" autoComplete="name" required minLength={2} maxLength={120} value={fullName} onChange={(event) => setFullName(event.target.value)} />
        </label>
        <label className="form-field">
          <span>Email</span>
          <input type="email" name="email" autoComplete="email" required maxLength={255} value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="form-field">
          <span>Password</span>
          <input type="password" name="password" autoComplete="new-password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} />
          <small>At least 8 characters.</small>
        </label>
        <button className="form-submit" type="submit" disabled={isSubmitting || !fullName.trim() || !email.trim() || !password}>
          {isSubmitting ? 'Creating account…' : 'Create customer account'}
        </button>
      </form>
      <p className="auth-switch">Already registered? <Link to="/login">Sign in</Link></p>
    </main>
  );
}
