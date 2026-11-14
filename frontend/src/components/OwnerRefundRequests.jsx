import { useCallback, useEffect, useState } from 'react';
import { decideOwnerRefundRequest, fetchOwnerRefundRequests } from '../api/refunds.js';
import { Pagination } from './Pagination.jsx';
import { formatINR } from '../context/CartContext.jsx';

const PAGE_SIZE = 10;
const FILTERS = [
  ['', 'All requests'],
  ['PENDING', 'Pending'],
  ['APPROVED', 'Approved'],
  ['REJECTED', 'Rejected'],
];

function formatDate(value) {
  return value
    ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(new Date(value))
    : 'Date unavailable';
}

export function OwnerRefundRequests({ onUpdated }) {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [retryKey, setRetryKey] = useState(0);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [error, setError] = useState('');

  const loadRequests = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      setResult(await fetchOwnerRefundRequests({ page, pageSize: PAGE_SIZE, status }));
    } catch (requestError) {
      setError(requestError.message || 'Refund requests could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }, [page, status]);

  useEffect(() => { void loadRequests(); }, [loadRequests, retryKey]);

  async function handleDecision(requestId, decision) {
    setActionId(requestId);
    setError('');
    try {
      await decideOwnerRefundRequest(requestId, decision);
      await Promise.all([loadRequests(), onUpdated()]);
    } catch (requestError) {
      await Promise.all([loadRequests(), onUpdated()]);
      setError(requestError.message || 'The refund request could not be updated.');
    } finally {
      setActionId(null);
    }
  }

  return (
    <section className="owner-orders-section refund-requests-section" aria-labelledby="refund-requests-title">
      <div className="section-heading">
        <div><p className="card-kicker">Customer requests</p><h2 id="refund-requests-title">Refund requests</h2></div>
        {result && <span className="result-count">{result.total} total</span>}
      </div>
      <label className="role-filter-single"><span>Filter refund requests</span>
        <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }}>
          {FILTERS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      {error && <section className="state-panel state-panel--error" role="alert"><p>{error}</p><button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></section>}
      {isLoading && <p className="state-panel" role="status">Loading refund requests…</p>}
      {!isLoading && !error && result?.items.length === 0 && <p className="state-panel">No refund requests match this status.</p>}
      {!isLoading && !error && result?.items.length > 0 && <>
        <div className="role-order-list">
          {result.items.map((request) => (
            <article className="order-list-card refund-request-card" key={request.id}>
              <div className="order-list-heading">
                <div><p className="card-kicker">Request #{request.id} · Order #{request.order.id}</p><h3>{request.customer.full_name}</h3></div>
                <span className={`order-status-badge order-status-badge--${request.status.toLowerCase()}`}>{request.status}</span>
              </div>
              <p className="refund-customer-contact">{request.customer.email}</p>
              <p className="order-list-meta">Placed {formatDate(request.order.placed_at)} · {request.order.items.length} {request.order.items.length === 1 ? 'line item' : 'line items'} · Order total {formatINR(Math.round(Number(request.order.total_amount) * 100))}</p>
              <p className="refund-created-at">Items: {request.order.items.map((item) => `${item.item_name} × ${item.quantity}`).join(', ')}</p>
              <p className="refund-created-at">Delivery address: {request.order.delivery_address}</p>
              <p className="refund-reason"><strong>Reason:</strong> {request.reason}</p>
              <p className="refund-created-at">Requested {formatDate(request.created_at)}</p>
              {request.reviewed_at && <p className="refund-created-at">Decision recorded {formatDate(request.reviewed_at)}</p>}
              {request.status === 'PENDING' && <div className="refund-decision-actions">
                <button className="form-submit" type="button" disabled={actionId !== null} onClick={() => void handleDecision(request.id, 'APPROVED')}>
                  {actionId === request.id ? 'Saving…' : 'Approve full refund'}
                </button>
                <button className="secondary-button" type="button" disabled={actionId !== null} onClick={() => void handleDecision(request.id, 'REJECTED')}>
                  Reject request
                </button>
              </div>}
            </article>
          ))}
        </div>
        <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPageChange={setPage} />
      </>}
    </section>
  );
}
