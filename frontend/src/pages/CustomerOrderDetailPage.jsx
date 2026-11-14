import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchRestaurantById } from '../api/catalog.js';
import { cancelOrder, fetchOrder } from '../api/orders.js';
import { formatINR, itemSubtotalPaise } from '../context/CartContext.jsx';

const DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata',
});
const DELIVERY_STEPS = [
  ['PLACED', 'Order placed'],
  ['ACCEPTED', 'Accepted by restaurant'],
  ['PREPARING', 'Being prepared'],
  ['READY', 'Ready for delivery'],
  ['ASSIGNED', 'Delivery partner assigned'],
  ['OUT_FOR_DELIVERY', 'Out for delivery'],
  ['DELIVERED', 'Delivered'],
];

function formatDate(value) {
  return value ? DATE_FORMAT.format(new Date(value)) : null;
}

function OrderTimeline({ order }) {
  const statusIndex = DELIVERY_STEPS.findIndex(([status]) => status === order.status);
  const terminalSteps = order.status === 'CANCELLED'
    ? [['PLACED', 'Order placed'], ['CANCELLED', 'Cancelled']]
    : order.status === 'REFUNDED'
      ? [['REFUNDED', 'Refunded']]
      : DELIVERY_STEPS;
  const currentIndex = terminalSteps.findIndex(([status]) => status === order.status);
  const activeIndex = currentIndex >= 0 ? currentIndex : statusIndex;

  return (
    <section className="order-timeline-section" aria-labelledby="order-timeline-title">
      <h2 id="order-timeline-title">Order status</h2>
      <p className="order-current-status">{order.status.replaceAll('_', ' ')}</p>
      <ol className="order-timeline">
        {terminalSteps.map(([status, label], index) => {
          const isCurrent = status === order.status;
          const isComplete = activeIndex >= 0 && index < activeIndex;
          let timestamp = null;
          if (status === 'PLACED') timestamp = formatDate(order.placed_at);
          if (status === 'DELIVERED') timestamp = formatDate(order.delivered_at);
          return (
            <li className={`timeline-step${isCurrent ? ' is-current' : ''}${isComplete ? ' is-complete' : ''}`} key={status}>
              <span className="timeline-marker" aria-hidden="true" />
              <div><strong>{label}</strong>{timestamp && <time dateTime={status === 'PLACED' ? order.placed_at : order.delivered_at}>{timestamp}</time>}</div>
            </li>
          );
        })}
      </ol>
      {order.updated_at && <p className="order-last-updated">Last updated {formatDate(order.updated_at)}</p>}
    </section>
  );
}

export function CustomerOrderDetailPage() {
  const { orderId } = useParams();
  const [order, setOrder] = useState(null);
  const [restaurantName, setRestaurantName] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isCancelling, setIsCancelling] = useState(false);
  const [showCancelConfirmation, setShowCancelConfirmation] = useState(false);
  const [error, setError] = useState('');
  const [cancelMessage, setCancelMessage] = useState('');
  const [retryKey, setRetryKey] = useState(0);

  const loadOrder = useCallback(async (showLoader = true) => {
    if (showLoader) setIsLoading(true);
    setError('');
    try {
      const currentOrder = await fetchOrder(orderId);
      setOrder(currentOrder);
      setRestaurantName(`Restaurant #${currentOrder.restaurant_id}`);
      try {
        const restaurant = await fetchRestaurantById(currentOrder.restaurant_id);
        if (restaurant?.name) setRestaurantName(restaurant.name);
      } catch {
        // Keep the order usable if the public catalog is temporarily unavailable.
      }
    } catch (requestError) {
      setError(requestError.message || 'Order details could not be loaded.');
    } finally {
      if (showLoader) setIsLoading(false);
    }
  }, [orderId]);

  useEffect(() => { void loadOrder(); }, [loadOrder, retryKey]);

  async function handleCancel() {
    if (!order || order.status !== 'PLACED') return;
    setIsCancelling(true);
    setError('');
    setCancelMessage('');
    try {
      const cancelledOrder = await cancelOrder(order.id);
      setOrder(cancelledOrder);
      setShowCancelConfirmation(false);
      setCancelMessage('Your order was cancelled.');
      await loadOrder(false);
    } catch (requestError) {
      const cancellationError = requestError.message || 'The order could not be cancelled.';
      setShowCancelConfirmation(false);
      // A concurrent status update may have made cancellation invalid; reload the authoritative state.
      await loadOrder(false);
      setError((currentError) => currentError || cancellationError);
    } finally {
      setIsCancelling(false);
    }
  }

  return (
    <main className="discovery-page order-detail-page">
      <Link className="back-link" to="/orders">← Order history</Link>
      {isLoading && <p className="state-panel" role="status">Loading order details…</p>}
      {!isLoading && error && !order && (
        <section className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button>
        </section>
      )}
      {!isLoading && order && (
        <>
          <header className="order-detail-header">
            <div><p className="eyebrow">Order details</p><h1 className="cart-title">Order #{order.id}</h1><p className="order-detail-restaurant">{restaurantName}</p></div>
            <span className={`order-status-badge order-status-badge--${order.status.toLowerCase()}`}>{order.status.replaceAll('_', ' ')}</span>
          </header>
          {error && <p className="form-message form-message--error" role="alert">{error} <button className="inline-retry" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry loading order</button></p>}
          {cancelMessage && <p className="form-message order-success-message" role="status">{cancelMessage}</p>}
          <div className="order-detail-layout">
            <div className="order-detail-main">
              <section className="order-detail-card" aria-label="Ordered items">
                <h2>Items</h2>
                {order.items.map((item) => (
                  <article className="order-detail-item" key={item.id}>
                    <div><h3>{item.item_name}</h3><p>{item.quantity} × {formatINR(Math.round(Number(item.unit_price) * 100))}</p></div>
                    <strong>{formatINR(itemSubtotalPaise({ unitPrice: String(item.unit_price), quantity: item.quantity }))}</strong>
                  </article>
                ))}
                <div className="order-total-row"><span>Total</span><strong>{formatINR(Math.round(Number(order.total_amount) * 100))}</strong></div>
              </section>
              <OrderTimeline order={order} />
            </div>
            <aside className="order-detail-card order-delivery-card">
              <h2>Delivery</h2>
              <p className="card-kicker">Address</p><p>{order.delivery_address}</p>
              <p className="card-kicker">Placed</p><p>{formatDate(order.placed_at) || 'Date unavailable'}</p>
              {order.delivered_at && <><p className="card-kicker">Delivered</p><p>{formatDate(order.delivered_at)}</p></>}
              {order.updated_at && <p className="order-last-updated">Last updated {formatDate(order.updated_at)}</p>}
              <p className="card-kicker">Payment</p><p>{order.payment_status}</p>
              {order.status === 'PLACED' && (
                <button className="cancel-order-button" type="button" onClick={() => setShowCancelConfirmation(true)}>Cancel order</button>
              )}
            </aside>
          </div>
        </>
      )}
      {showCancelConfirmation && (
        <div className="dialog-backdrop" role="presentation">
          <section className="switch-dialog" role="dialog" aria-modal="true" aria-labelledby="cancel-dialog-title">
            <p className="card-kicker">Order #{order?.id}</p>
            <h2 id="cancel-dialog-title">Cancel this order?</h2>
            <p className="card-description">This will cancel the order and void its mock payment. You can’t undo this action.</p>
            <div className="dialog-actions">
              <button className="secondary-button" type="button" disabled={isCancelling} onClick={() => setShowCancelConfirmation(false)}>Keep order</button>
              <button className="cancel-order-button" type="button" disabled={isCancelling} onClick={() => void handleCancel()}>{isCancelling ? 'Cancelling…' : 'Confirm cancellation'}</button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
