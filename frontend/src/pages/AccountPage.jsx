import { useAuth } from '../context/AuthContext.jsx';

export function AccountPage() {
  const { user } = useAuth();

  return (
    <main className="auth-card account-card">
      <p className="eyebrow">Signed in</p>
      <h1 className="auth-title">Hello, {user.full_name}.</h1>
      <p className="auth-intro">Your account is authenticated as <strong>{user.role.replaceAll('_', ' ')}</strong>.</p>
      <p className="account-note">Your role workspace will be added in a later milestone.</p>
    </main>
  );
}
