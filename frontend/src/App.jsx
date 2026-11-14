import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { roleHomePath } from './auth/roles.js';
import { useAuth } from './context/AuthContext.jsx';
import { AccountPage } from './pages/AccountPage.jsx';
import { LoginPage } from './pages/LoginPage.jsx';
import { RegisterPage } from './pages/RegisterPage.jsx';
import { CartPage } from './pages/CartPage.jsx';
import { CheckoutPage } from './pages/CheckoutPage.jsx';
import { OrderConfirmationPage } from './pages/OrderConfirmationPage.jsx';
import { CustomerOrdersPage } from './pages/CustomerOrdersPage.jsx';
import { CustomerOrderDetailPage } from './pages/CustomerOrderDetailPage.jsx';
import { OwnerDashboardPage } from './pages/OwnerDashboardPage.jsx';
import { OwnerOrderDetailPage } from './pages/OwnerOrderDetailPage.jsx';
import { DeliveryOrdersPage } from './pages/DeliveryOrdersPage.jsx';
import { DeliveryOrderDetailPage } from './pages/DeliveryOrderDetailPage.jsx';
import { RestaurantListPage } from './pages/RestaurantListPage.jsx';
import { RestaurantMenuPage } from './pages/RestaurantMenuPage.jsx';
import { ProtectedRoute } from './routes/ProtectedRoute.jsx';
import { useCart } from './context/CartContext.jsx';
import './styles.css';

function SiteHeader() {
  const { user, logout } = useAuth();
  const { itemCount } = useCart();

  return (
    <header className="site-header">
      <Link className="wordmark" to="/">Campus<span>Bite</span><b aria-hidden="true">.</b></Link>
      <div className="header-actions">
        <Link className="text-button" to="/restaurants">Browse restaurants</Link>
        <Link className="cart-nav-link" to="/cart" aria-label={`Shopping cart, ${itemCount} ${itemCount === 1 ? 'item' : 'items'}`}>
          Cart <span className="cart-count" aria-live="polite">{itemCount}</span>
        </Link>
        {user ? (
          <>
            {user.role === 'CUSTOMER' && <Link className="text-button" to="/orders">My orders</Link>}
            {user.role === 'OWNER' && <Link className="text-button" to="/account/owner">Owner dashboard</Link>}
            {user.role === 'DELIVERY_PARTNER' && <Link className="text-button" to="/account/delivery-partner">My deliveries</Link>}
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
        <Route path="/cart" element={<CartPage />} />
        <Route path="/checkout" element={<ProtectedRoute allowedRoles={["CUSTOMER"]}><CheckoutPage /></ProtectedRoute>} />
        <Route path="/order-confirmation/:orderId" element={<ProtectedRoute allowedRoles={["CUSTOMER"]}><OrderConfirmationPage /></ProtectedRoute>} />
        <Route path="/orders" element={<ProtectedRoute allowedRoles={["CUSTOMER"]}><CustomerOrdersPage /></ProtectedRoute>} />
        <Route path="/orders/:orderId" element={<ProtectedRoute allowedRoles={["CUSTOMER"]}><CustomerOrderDetailPage /></ProtectedRoute>} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/account/customer" element={<ProtectedRoute allowedRoles={["CUSTOMER"]}><AccountPage /></ProtectedRoute>} />
        <Route path="/account/owner" element={<ProtectedRoute allowedRoles={["OWNER"]}><OwnerDashboardPage /></ProtectedRoute>} />
        <Route path="/owner/orders/:orderId" element={<ProtectedRoute allowedRoles={["OWNER"]}><OwnerOrderDetailPage /></ProtectedRoute>} />
        <Route path="/account/delivery-partner" element={<ProtectedRoute allowedRoles={["DELIVERY_PARTNER"]}><DeliveryOrdersPage /></ProtectedRoute>} />
        <Route path="/delivery/orders/:orderId" element={<ProtectedRoute allowedRoles={["DELIVERY_PARTNER"]}><DeliveryOrderDetailPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <footer>Built for the campus community <span aria-hidden="true">✳</span></footer>
    </div>
  );
}
