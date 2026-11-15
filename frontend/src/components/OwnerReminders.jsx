import { useCallback, useEffect, useState } from 'react';
import { fetchOwnerReminders } from '../api/reminders.js';
import { Pagination } from './Pagination.jsx';
import { formatINR } from '../context/CartContext.jsx';

const PAGE_SIZE = 10;
const DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata',
});

function formatDate(value) {
  return value ? DATE_FORMAT.format(new Date(value)) : 'Date unavailable';
}

export function OwnerReminders() {
  const [page, setPage] = useState(1);
  const [retryKey, setRetryKey] = useState(0);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadReminders = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      setResult(await fetchOwnerReminders(page, PAGE_SIZE));
    } catch (requestError) {
      setError(requestError.message || 'Order reminders could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }, [page]);

  useEffect(() => { void loadReminders(); }, [loadReminders, retryKey]);

  return (
    <section className="owner-orders-section owner-reminders-section" aria-labelledby="owner-reminders-title">
      <div className="section-heading">
        <div><p className="card-kicker">Needs attention</p><h2 id="owner-reminders-title">Order reminders</h2></div>
        {result && <span className="result-count">{result.total} total</span>}
      </div>
      {error && <section className="state-panel state-panel--error" role="alert"><p>{error}</p><button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></section>}
      {isLoading && <p className="state-panel" role="status">Loading order reminders…</p>}
      {!isLoading && !error && result?.items.length === 0 && <p className="state-panel">No overdue orders need a reminder.</p>}
      {!isLoading && !error && result?.items.length > 0 && <>
        <div className="role-order-list">
          {result.items.map((reminder) => (
            <article className="order-list-card owner-reminder-card" key={reminder.id}>
              <div className="order-list-heading">
                <div><p className="card-kicker">Order #{reminder.order.id}</p><h3>{reminder.order.status.replaceAll('_', ' ')}</h3></div>
                <span className="order-status-badge">Reminder</span>
              </div>
              <p className="order-list-meta">Customer: {reminder.order.customer.full_name}</p>
              <p className="order-list-meta">Placed {formatDate(reminder.order.placed_at)} · Order total {formatINR(String(reminder.order.total_amount))}</p>
              <p className="reminder-created-at">Reminder created {formatDate(reminder.created_at)}</p>
            </article>
          ))}
        </div>
        <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPageChange={setPage} />
      </>}
    </section>
  );
}
