import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchOwnerOrders, fetchAllOwnerOrders, fetchOwnerRestaurant } from '../api/ownerOrders.js';
import { Pagination } from '../components/Pagination.jsx';
import { formatINR } from '../context/CartContext.jsx';

const PAGE_SIZE = 10;
const ORDER_STATUSES = ['PLACED', 'ACCEPTED', 'PREPARING', 'READY', 'ASSIGNED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'REFUNDED'];
const PENDING_STATUSES = new Set(['PLACED', 'ACCEPTED', 'PREPARING', 'READY', 'ASSIGNED', 'OUT_FOR_DELIVERY']);

export function calculateOwnerMetrics(orders) {
  return {
    total: orders.length,
    pending: orders.filter((order) => PENDING_STATUSES.has(order.status)).length,
    completed: orders.filter((order) => order.status === 'DELIVERED' || order.status === 'REFUNDED').length,
    cancelled: orders.filter((order) => order.status === 'CANCELLED').length,
    refunded: orders.filter((order) => order.status === 'REFUNDED').length,
    salesPaise: orders
      .filter((order) => order.status === 'DELIVERED')
      .reduce((sum, order) => sum + Math.round(Number(order.total_amount) * 100), 0),
  };
}

export function OwnerDashboardPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [fromInput, setFromInput] = useState('');
  const [toInput, setToInput] = useState('');
  const [filters, setFilters] = useState({ placedFrom: '', placedTo: '' });
  const [retryKey, setRetryKey] = useState(0);
  const [ordersPage, setOrdersPage] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [restaurant, setRestaurant] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterError, setFilterError] = useState('');

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [pageResult, allOrders, ownerRestaurant] = await Promise.all([
        fetchOwnerOrders({ page, pageSize: PAGE_SIZE, status: statusFilter, ...filters }),
        fetchAllOwnerOrders(filters),
        fetchOwnerRestaurant(),
      ]);
      setOrdersPage(pageResult);
      setMetrics(calculateOwnerMetrics(allOrders));
      setRestaurant(ownerRestaurant);
    } catch (requestError) {
      setError(requestError.message || 'The owner dashboard could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, filters]);

  useEffect(() => { void loadDashboard(); }, [loadDashboard, retryKey]);

  function applyFilters(event) {
    event.preventDefault();
    setFilterError('');
    if (fromInput && toInput && fromInput > toInput) {
      setFilterError('Start date must be on or before the end date.');
      return;
    }
    setPage(1);
    setFilters({ placedFrom: fromInput, placedTo: toInput });
  }

  const metricCards = useMemo(() => metrics ? [
    ['Total orders', metrics.total],
    ['Pending', metrics.pending],
    ['Completed', metrics.completed],
    ['Cancelled', metrics.cancelled],
    ['Refunded', metrics.refunded],
  ] : [], [metrics]);

  return (
    <main className="discovery-page role-dashboard">
      <p className="eyebrow">Restaurant workspace</p>
      <h1 className="cart-title">{restaurant?.name || 'Owner dashboard'}</h1>
      {error && <section className="state-panel state-panel--error" role="alert"><p>{error}</p><button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></section>}
      {!error && (
        <>
          <section className="dashboard-metrics" aria-label="Operational order counts">
            {metricCards.map(([label, value]) => <article className="metric-card" key={label}><span>{label}</span><strong>{isLoading ? '…' : value}</strong></article>)}
          </section>
          <section className="sales-metric" aria-label="Sales figure">
            <div><p className="card-kicker">Financial metric</p><h2>Sales</h2><p>Delivered orders, excluding refunded orders.</p></div>
            <strong>{isLoading || !metrics ? '…' : formatINR(metrics.salesPaise)}</strong>
          </section>
          <section className="owner-orders-section">
            <div className="section-heading"><div><p className="card-kicker">Restaurant queue</p><h2>Orders</h2></div>{ordersPage && <span className="result-count">{ordersPage.total} total</span>}</div>
            <form className="role-filter-bar" onSubmit={applyFilters}>
              <label><span>Status</span><select value={statusFilter} onChange={(event) => { setPage(1); setStatusFilter(event.target.value); }}><option value="">All statuses</option>{ORDER_STATUSES.map((status) => <option value={status} key={status}>{status.replaceAll('_', ' ')}</option>)}</select></label>
              <label><span>Placed from</span><input type="date" value={fromInput} onChange={(event) => setFromInput(event.target.value)} /></label>
              <label><span>Placed to</span><input type="date" value={toInput} onChange={(event) => setToInput(event.target.value)} /></label>
              <button className="form-submit" type="submit">Apply dates</button>
            </form>
            {filterError && <p className="form-message form-message--error" role="alert">{filterError}</p>}
            {isLoading && <p className="state-panel" role="status">Loading restaurant orders…</p>}
            {!isLoading && ordersPage?.items.length === 0 && <p className="state-panel">No orders match these filters.</p>}
            {!isLoading && ordersPage?.items.length > 0 && <>
              <div className="role-order-list">
                {ordersPage.items.map((order) => (
                  <article className="order-list-card" key={order.id}>
                    <div className="order-list-heading"><div><p className="card-kicker">Order #{order.id}</p><h2>{order.status.replaceAll('_', ' ')}</h2></div><span>{formatINR(Math.round(Number(order.total_amount) * 100))}</span></div>
                    <p className="order-list-meta">{order.items.length} {order.items.length === 1 ? 'line item' : 'line items'} · Delivery: {order.delivery_address}</p>
                    <Link className="card-link" to={`/owner/orders/${order.id}`} state={{ source: 'owner-dashboard', order }}>Review order <span aria-hidden="true">→</span></Link>
                  </article>
                ))}
              </div>
              <Pagination page={ordersPage.page} pageSize={ordersPage.page_size} total={ordersPage.total} onPageChange={setPage} />
            </>}
          </section>
        </>
      )}
    </main>
  );
}
