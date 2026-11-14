import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { fetchOrder } from '../api/orders.js';
import { formatINR } from '../context/CartContext.jsx';

export function OrderConfirmationPage() {
  const { orderId } = useParams();
  const location = useLocation();
  const [order, setOrder] = useState(location.state?.order || null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (order?.id === Number(orderId)) return;
    let active = true;
    fetchOrder(orderId).then((result) => {
      if (active) setOrder(result);
    }).catch((requestError) => {
      if (active) setError(requestError.message || 'Order details could not be loaded.');
    });
    return () => { active = false; };
  }, [orderId, order?.id]);

  return (
    <main className="auth-card order-confirmation">
      <p className="eyebrow">Order placed</p>
      <h1 className="auth-title">Thank you</h1>
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      {!order && !error && <p role="status">Loading order details…</p>}
      {order && <>
        <p className="auth-intro">Your order <strong>#{order.id}</strong> has been placed with status {order.status.replaceAll('_', ' ').toLowerCase()}.</p>
        <p className="cart-subtotal">{formatINR(Math.round(Number(order.total_amount) * 100))}</p>
        <p className="cart-summary-note">Payment status: {order.payment_status}</p>
      </>}
      <Link className="form-submit cart-browse-link" to="/restaurants">Browse restaurants</Link>
    </main>
  );
}
