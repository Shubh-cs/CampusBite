import { useState } from 'react';
import { ApiError } from '../api/client.js';
import { askOrderInsights } from '../api/orderInsights.js';
import { formatINR } from '../context/CartContext.jsx';

const EXAMPLE_QUESTIONS = [
  'Summarize my order history.',
  'Which dishes have I ordered most often?',
  'How much did I spend this week?',
  'Which of my orders are still not delivered?',
  'How much have I spent after cancellations and refunds?',
  'What was in my most recent order?',
];

const DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata',
});

function formatDate(value) {
  return value ? DATE_FORMAT.format(new Date(value)) : 'Date unavailable';
}

function money(value) {
  return formatINR(String(value ?? '0.00'));
}

export function CustomerOrderInsightsPage() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function submitQuestion(value) {
    const submittedQuestion = value.trim();
    if (!submittedQuestion || isLoading) return;
    setIsLoading(true);
    setError('');
    setResult(null);
    try {
      setResult(await askOrderInsights(submittedQuestion));
    } catch (requestError) {
      setError(requestError instanceof ApiError
        ? requestError.message
        : 'Order insights could not be loaded. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    void submitQuestion(question);
  }

  return (
    <main className="discovery-page order-insights-page">
      <p className="eyebrow">Your CampusBite history</p>
      <h1 className="cart-title">Order insights</h1>
      <p className="insights-intro">Ask a question about your orders. Verified totals are calculated from your order and payment records.</p>

      <section className="order-insights-card" aria-labelledby="insights-question-title">
        <h2 id="insights-question-title">What would you like to know?</h2>
        <form className="insights-question-form" onSubmit={handleSubmit}>
          <label className="form-field" htmlFor="order-insights-question">
            <span>Your question</span>
            <textarea
              id="order-insights-question"
              rows="3"
              maxLength={500}
              required
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="For example, summarize my recent orders"
            />
          </label>
          <div className="insights-submit-row">
            <small>{question.length}/500 characters</small>
            <button className="form-submit" type="submit" disabled={isLoading || !question.trim()}>
              {isLoading ? 'Reviewing your orders…' : 'Ask about my orders'}
            </button>
          </div>
        </form>
        <div className="insights-suggestions" aria-label="Example questions">
          <p className="card-kicker">Try an example</p>
          {EXAMPLE_QUESTIONS.map((example) => (
            <button key={example} type="button" className="insight-prompt" disabled={isLoading} onClick={() => setQuestion(example)}>
              {example}
            </button>
          ))}
        </div>
      </section>

      {isLoading && <p className="state-panel" role="status">Preparing your verified order facts and answer…</p>}
      {error && (
        <section className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button className="secondary-button" type="button" disabled={isLoading || !question.trim()} onClick={() => void submitQuestion(question)}>
            Retry
          </button>
        </section>
      )}

      {result && (
        <div className="insights-results">
          {result.notice && <p className="state-panel" role="status">{result.notice}</p>}
          {result.answer && (
            <section className="order-insights-card" aria-labelledby="insights-answer-title">
              <p className="card-kicker">AI explanation</p>
              <h2 id="insights-answer-title">Your answer</h2>
              <p className="insights-answer">{result.answer}</p>
            </section>
          )}
          <section className="order-insights-card" aria-labelledby="verified-facts-title">
            <p className="card-kicker">Calculated by CampusBite</p>
            <h2 id="verified-facts-title">Verified order facts</h2>
            <p className="insights-facts-note">These figures come directly from your records. Currency: {result.verified_facts.currency}; timezone: {result.verified_facts.timezone}.</p>
            <div className="insights-metrics">
              <article><span>Orders</span><strong>{result.verified_facts.order_count}</strong></article>
              <article><span>Gross successful payments</span><strong>{money(result.verified_facts.gross_successful_payments)}</strong></article>
              <article><span>Voided amounts</span><strong>{money(result.verified_facts.voided_amounts)}</strong></article>
              <article><span>Refunded amounts</span><strong>{money(result.verified_facts.refunded_amounts)}</strong></article>
              <article className="insights-net-metric"><span>Net spending</span><strong>{money(result.verified_facts.net_spending)}</strong></article>
            </div>
            <section className="insights-weekly-activity" aria-labelledby="weekly-activity-title">
              <h3 id="weekly-activity-title">This week’s payment activity</h3>
              <p className="order-list-meta">
                {formatDate(result.verified_facts.weekly_payment_activity.period_start)} – {formatDate(result.verified_facts.weekly_payment_activity.period_end)}
              </p>
              <div className="insights-metrics">
                <article><span>Gross successful payments</span><strong>{money(result.verified_facts.weekly_payment_activity.gross_successful_payments)}</strong></article>
                <article><span>Voided</span><strong>{money(result.verified_facts.weekly_payment_activity.voided_amounts)}</strong></article>
                <article><span>Refunded</span><strong>{money(result.verified_facts.weekly_payment_activity.refunded_amounts)}</strong></article>
                <article className="insights-net-metric"><span>Net payment activity</span><strong>{money(result.verified_facts.weekly_payment_activity.net_payment_activity)}</strong></article>
              </div>
              <p className="insights-facts-note">{result.verified_facts.weekly_payment_activity.accounting_note}</p>
            </section>
            <div className="insights-fact-columns">
              <section>
                <h3>Orders by status</h3>
                {Object.keys(result.verified_facts.order_counts_by_status).length === 0
                  ? <p className="order-list-meta">No order statuses to report.</p>
                  : <ul>{Object.entries(result.verified_facts.order_counts_by_status).map(([status, count]) => <li key={status}><span>{status.replaceAll('_', ' ')}</span><strong>{count}</strong></li>)}</ul>}
              </section>
              <section>
                <h3>Most ordered dishes</h3>
                {result.verified_facts.most_ordered_items.length === 0
                  ? <p className="order-list-meta">No ordered dishes to report.</p>
                  : <ul>{result.verified_facts.most_ordered_items.map((item) => <li key={item.item_name}><span>{item.item_name} · {item.quantity_ordered} ordered</span><strong>{money(item.snapshot_spend)}</strong></li>)}</ul>}
              </section>
            </div>
            <section className="insights-outstanding-orders" aria-labelledby="outstanding-orders-title">
              <h3 id="outstanding-orders-title">Outstanding orders</h3>
              {result.verified_facts.outstanding_orders.length === 0
                ? <p className="order-list-meta">You have no active undelivered orders.</p>
                : <div className="insights-recent-list">
                    {result.verified_facts.outstanding_orders.map((order) => (
                      <article key={order.order_id}>
                        <strong>Order #{order.order_id} · {order.status.replaceAll('_', ' ')}</strong>
                        <span>{order.restaurant_name} · Placed {formatDate(order.placed_at)}</span>
                      </article>
                    ))}
                  </div>}
            </section>
            {result.verified_facts.recent_orders.length > 0 && (
              <details className="insights-recent-orders">
                <summary>Recent order details (up to {result.verified_facts.recent_order_limit})</summary>
                <div className="insights-recent-list">
                  {result.verified_facts.recent_orders.map((order) => (
                    <article key={order.order_id}>
                      <strong>Order #{order.order_id} · {order.status.replaceAll('_', ' ')}</strong>
                      <span>{order.restaurant_name} · {formatDate(order.placed_at)}</span>
                      <span>{order.items.map((item) => `${item.item_name} × ${item.quantity} (${money(item.unit_price)} each)`).join(', ')}</span>
                    </article>
                  ))}
                </div>
              </details>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
