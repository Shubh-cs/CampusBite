import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchRestaurantById } from '../api/catalog.js';
import { fetchCustomerOrders } from '../api/orders.js';
import { Pagination } from '../components/Pagination.jsx';
import { formatINR } from '../context/CartContext.jsx';

const PAGE_SIZE = 10;
const ORDER_STATUSES = [
  'PLACED', 'ACCEPTED', 'PREPARING', 'READY', 'ASSIGNED',
  'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'REFUNDED',
];
const EMPTY_FILTERS = { status: '', placedFrom: '', placedTo: '' };
const DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata',
});

function formatDate(value) {
  return value ? DATE_FORMAT.format(new Date(value)) : 'Date unavailable';
}

export function CustomerOrdersPage() {
  const [page, setPage] = useState(1);
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterError, setFilterError] = useState('');
  const [retryKey, setRetryKey] = useState(0);
  const [result, setResult] = useState(null);
  const [restaurantNames, setRestaurantNames] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadOrders = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetchCustomerOrders({ page, pageSize: PAGE_SIZE, ...filters });
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
  }, [page, filters]);

  useEffect(() => { void loadOrders(); }, [loadOrders, retryKey]);

  function updateDraftFilter(field, value) {
    setDraftFilters((current) => ({ ...current, [field]: value }));
    setFilterError('');
  }

  function applyFilters(event) {
    event.preventDefault();
    if (draftFilters.placedFrom && draftFilters.placedTo && draftFilters.placedFrom > draftFilters.placedTo) {
      setFilterError('Start date must be on or before the end date.');
      return;
    }
    setFilterError('');
    setPage(1);
    setFilters({ ...draftFilters });
  }

  function clearFilters() {
    setDraftFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setFilterError('');
    setPage(1);
  }

  const hasAppliedFilters = Boolean(filters.status || filters.placedFrom || filters.placedTo);

  return (
    <main className="discovery-page orders-page">
      <p className="eyebrow">Your CampusBite activity</p>
      <h1 className="cart-title">Customer dashboard</h1>
      <form className="role-filter-bar" onSubmit={applyFilters}>
        <label>
          <span>Status</span>
          <select value={draftFilters.status} onChange={(event) => updateDraftFilter('status', event.target.value)}>
            <option value="">All statuses</option>
            {ORDER_STATUSES.map((status) => <option value={status} key={status}>{status.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
        <label>
          <span>Placed from</span>
          <input type="date" value={draftFilters.placedFrom} onChange={(event) => updateDraftFilter('placedFrom', event.target.value)} />
        </label>
        <label>
          <span>Placed to</span>
          <input type="date" value={draftFilters.placedTo} onChange={(event) => updateDraftFilter('placedTo', event.target.value)} />
        </label>
        <button className="form-submit" type="submit">Apply filters</button>
      </form>
      {(hasAppliedFilters || Object.values(draftFilters).some(Boolean)) && (
        <button className="secondary-button" type="button" onClick={clearFilters}>Clear filters</button>
      )}
      {filterError && <p className="form-message form-message--error" role="alert">{filterError}</p>}
      {isLoading && <p className="state-panel" role="status">Loading your orders…</p>}
      {!isLoading && error && (
        <section className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button>
        </section>
      )}
      {!isLoading && !error && result?.items.length === 0 && (
        <section className="state-panel cart-empty">
          {hasAppliedFilters ? <>
            <h2>No orders match these filters</h2>
            <p>Try changing your status or date range.</p>
            <button className="secondary-button" type="button" onClick={clearFilters}>Clear filters</button>
          </> : <>
            <h2>No orders yet</h2>
            <p>Your completed checkouts will appear here.</p>
            <Link className="form-submit cart-browse-link" to="/restaurants">Browse restaurants</Link>
          </>}
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
