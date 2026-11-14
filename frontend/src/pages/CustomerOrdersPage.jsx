import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchRestaurantById } from '../api/catalog.js';
import { fetchCustomerOrders } from '../api/orders.js';
import { Pagination } from '../components/Pagination.jsx';
import { formatINR } from '../context/CartContext.jsx';

const PAGE_SIZE = 10;
const DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata',
});

function formatDate(value) {
  return value ? DATE_FORMAT.format(new Date(value)) : 'Date unavailable';
}

export function CustomerOrdersPage() {
  const [page, setPage] = useState(1);
  const [retryKey, setRetryKey] = useState(0);
  const [result, setResult] = useState(null);
  const [restaurantNames, setRestaurantNames] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadOrders = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetchCustomerOrders(page, PAGE_SIZE);
      setResult(response);
      const restaurantIds = [...new Set(response.items.map((order) => order.restaurant_id))];
      const names = await Promise.all(restaurantIds.map(async (restaurantId) => {
        try {
          const restaurant = await fetchRestaurantById(restaurantId);
          return [restaurantId, restaurant?.name || `Restaurant #${restaurantId}`];
        } catch {
          return [restaurantId, `Restaurant #${restaurantId}`];
        }
      }));
      setRestaurantNames(Object.fromEntries(names));
    } catch (requestError) {
      setError(requestError.message || 'Your orders could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }, [page]);

  useEffect(() => { void loadOrders(); }, [loadOrders, retryKey]);

  return (
    <main className="discovery-page orders-page">
      <p className="eyebrow">Your CampusBite activity</p>
      <h1 className="cart-title">Your orders</h1>
      {isLoading && <p className="state-panel" role="status">Loading your orders…</p>}
      {!isLoading && error && (
        <section className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button>
        </section>
      )}
      {!isLoading && !error && result?.items.length === 0 && (
        <section className="state-panel cart-empty">
          <h2>No orders yet</h2>
          <p>Your completed checkouts will appear here.</p>
          <Link className="form-submit cart-browse-link" to="/restaurants">Browse restaurants</Link>
        </section>
      )}
      {!isLoading && !error && result?.items.length > 0 && (
        <>
          <section className="order-list" aria-label="Order history">
            {result.items.map((order) => (
              <article className="order-list-card" key={order.id}>
                <div className="order-list-heading">
                  <div>
                    <p className="card-kicker">Order #{order.id}</p>
                    <h2>{restaurantNames[order.restaurant_id] || `Restaurant #${order.restaurant_id}`}</h2>
                  </div>
                  <span className={`order-status-badge order-status-badge--${order.status.toLowerCase()}`}>{order.status.replaceAll('_', ' ')}</span>
                </div>
                <p className="order-list-meta">Placed {formatDate(order.placed_at)} · {order.items.length} {order.items.length === 1 ? 'line item' : 'line items'}</p>
                <div className="order-list-footer">
                  <strong>{formatINR(Math.round(Number(order.total_amount) * 100))}</strong>
                  <Link className="card-link" to={`/orders/${order.id}`}>View order details <span aria-hidden="true">→</span></Link>
                </div>
              </article>
            ))}
          </section>
          <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPageChange={setPage} />
        </>
      )}
    </main>
  );
}
