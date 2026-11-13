import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { roleHomePath } from './auth/roles.js';
import { useAuth } from './context/AuthContext.jsx';
import { AccountPage } from './pages/AccountPage.jsx';
import { LoginPage } from './pages/LoginPage.jsx';
import { RegisterPage } from './pages/RegisterPage.jsx';
import { RestaurantListPage } from './pages/RestaurantListPage.jsx';
import { RestaurantMenuPage } from './pages/RestaurantMenuPage.jsx';
import { ProtectedRoute } from './routes/ProtectedRoute.jsx';
import './styles.css';

function SiteHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="site-header">
      <Link className="wordmark" to="/">Campus<span>Bite</span><b aria-hidden="true">.</b></Link>
      <div className="header-actions">
        <Link className="text-button" to="/restaurants">Browse restaurants</Link>
        {user ? (
          <>
            <span className="status-pill"><i aria-hidden="true" />{user.role.replaceAll('_', ' ')}</span>
            <button className="text-button" type="button" onClick={logout}>Sign out</button>
          </>
        ) : (
          <>
            <Link className="text-button" to="/login">Sign in</Link>
            <Link className="small-button" to="/register">Create account</Link>
          </>
        )}
      </div>
    </header>
  );
}

function Home() {
  return (
    <main className="welcome-card">
      <div className="brand-mark" aria-hidden="true">CB</div>
      <p className="eyebrow">CampusBite · Capstone project</p>
      <h1>Good food, closer to campus.</h1>
      <p className="intro">Explore campus restaurants and browse their menus. Sign in when you’re ready to order.</p>
      <div className="home-actions">
        <Link className="api-link" to="/restaurants">Browse restaurants <span aria-hidden="true">→</span></Link>
        <Link className="text-button" to="/login">Sign in</Link>
        <Link className="secondary-link" to="/register">Create a customer account</Link>
      </div>
    </main>
  );
}

function ApiStatus() {
  return (
    <main className="welcome-card">
      <p className="eyebrow">Project foundation</p>
      <h1>API foundation</h1>
      <p className="intro">The backend health endpoint is available at <code>/health</code>.</p>
      <Link className="api-link" to="/">Back to home <span aria-hidden="true">→</span></Link>
    </main>
  );
}

function LoadingPage() {
  return <main className="auth-card" role="status">Checking your session…</main>;
}

export default function App() {
  const { isAuthenticated, isLoading, user } = useAuth();

  return (
    <div className="page-shell">
      <SiteHeader />
      <Routes>
        <Route
          path="/"
          element={isLoading ? <LoadingPage /> : isAuthenticated ? <Navigate to={roleHomePath(user.role)} replace /> : <Home />}
        />
        <Route path="/api-status" element={<ApiStatus />} />
        <Route path="/restaurants" element={<RestaurantListPage />} />
        <Route path="/restaurants/:restaurantId" element={<RestaurantMenuPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/account/customer" element={<ProtectedRoute allowedRoles={["CUSTOMER"]}><AccountPage /></ProtectedRoute>} />
        <Route path="/account/owner" element={<ProtectedRoute allowedRoles={["OWNER"]}><AccountPage /></ProtectedRoute>} />
        <Route path="/account/delivery-partner" element={<ProtectedRoute allowedRoles={["DELIVERY_PARTNER"]}><AccountPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <footer>Built for the campus community <span aria-hidden="true">✳</span></footer>
    </div>
  );
}
