import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchRestaurantById } from '../api/catalog.js';
import { fetchDeliveryOrders } from '../api/deliveryOrders.js';
import { Pagination } from '../components/Pagination.jsx';
import { formatINR } from '../context/CartContext.jsx';

const PAGE_SIZE = 10;
const REFUNDED_DELIVERY_GROUP = 'REFUNDED_DELIVERED';
const FILTERS = [
  ['', 'All deliveries'],
  ['ASSIGNED', 'Assigned'],
  ['OUT_FOR_DELIVERY', 'Out for delivery'],
  ['DELIVERED', 'Delivered history'],
];

function formatDate(value) {
  return value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone: 'Asia/Kolkata' }).format(new Date(value)) : '';
}

export function DeliveryOrdersPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [retryKey, setRetryKey] = useState(0);
  const [result, setResult] = useState(null);
  const [restaurantNames, setRestaurantNames] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDeliveries = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetchDeliveryOrders({ page, pageSize: PAGE_SIZE, status });
      const ids = [...new Set(response.items.map((order) => order.restaurant_id))];
      const names = await Promise.all(ids.map(async (id) => {
        try {
          const restaurant = await fetchRestaurantById(id);
          return [id, restaurant?.name || `Restaurant #${id}`];
        } catch {
          return [id, `Restaurant #${id}`];
        }
      }));
      setResult(response);
      setRestaurantNames(Object.fromEntries(names));
    } catch (requestError) {
      setError(requestError.message || 'Assigned deliveries could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }, [page, status]);

  useEffect(() => { void loadDeliveries(); }, [loadDeliveries, retryKey]);

  const groupedOrders = (result?.items || []).reduce((groups, order) => {
    const group = order.status === 'REFUNDED' && order.delivered_at
      ? REFUNDED_DELIVERY_GROUP
      : order.status;
    (groups[group] ||= []).push(order);
    return groups;
  }, {});
  const groupOrder = ['ASSIGNED', 'OUT_FOR_DELIVERY', 'DELIVERED', REFUNDED_DELIVERY_GROUP];

  return (
    <main className="discovery-page role-dashboard">
      <p className="eyebrow">Delivery workspace</p>
      <h1 className="cart-title">My deliveries</h1>
      <div className="section-heading"><div><p className="card-kicker">Assigned to your account</p><h2>Delivery queue and history</h2></div>{result && <span className="result-count">{result.total} orders</span>}</div>
      <label className="role-filter-single"><span>Filter by status</span><select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }}>{FILTERS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      {isLoading && <p className="state-panel" role="status">Loading assigned deliveries…</p>}
      {!isLoading && error && <section className="state-panel state-panel--error" role="alert"><p>{error}</p><button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></section>}
      {!isLoading && !error && result?.items.length === 0 && <p className="state-panel">No deliveries match this status.</p>}
      {!isLoading && !error && result?.items.length > 0 && <>
        {groupOrder.filter((group) => groupedOrders[group]?.length).map((group) => (
          <section className="delivery-status-group" aria-label={`${group.replaceAll('_', ' ')} deliveries`} key={group}>
            <h2>{group === REFUNDED_DELIVERY_GROUP ? 'Delivered · Refunded' : group.replaceAll('_', ' ')}</h2>
            <div className="role-order-list">
              {groupedOrders[group].map((order) => (
                <article className="order-list-card" key={order.id}>
                  <div className="order-list-heading"><div><p className="card-kicker">Order #{order.id}</p><h3>{restaurantNames[order.restaurant_id] || `Restaurant #${order.restaurant_id}`}</h3></div><span className={`order-status-badge order-status-badge--${order.status.toLowerCase()}`}>{order.status.replaceAll('_', ' ')}</span></div>
                  <p className="order-list-meta">Placed {formatDate(order.placed_at)} · {order.items.length} {order.items.length === 1 ? 'line item' : 'line items'}</p>
                  <div className="order-list-footer"><strong>{formatINR(Math.round(Number(order.total_amount) * 100))}</strong><Link className="card-link" to={`/delivery/orders/${order.id}`}>Delivery details <span aria-hidden="true">→</span></Link></div>
                </article>
              ))}
            </div>
          </section>
        ))}
        <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPageChange={setPage} />
      </>}
    </main>
  );
}
