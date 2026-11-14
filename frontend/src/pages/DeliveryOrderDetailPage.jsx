import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchRestaurantById } from '../api/catalog.js';
import { fetchAssignedOrder, updateDeliveryOrderStatus } from '../api/deliveryOrders.js';
import { RoleOrderDetails } from '../components/RoleOrderDetails.jsx';

export function DeliveryOrderDetailPage() {
  const { orderId } = useParams();
  const [order, setOrder] = useState(null);
  const [restaurantName, setRestaurantName] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [action, setAction] = useState(false);
  const [error, setError] = useState('');
  const [retryKey, setRetryKey] = useState(0);

  const loadOrder = useCallback(async (showLoader = true) => {
    if (showLoader) setIsLoading(true);
    setError('');
    try {
      const currentOrder = await fetchAssignedOrder(orderId);
      setOrder(currentOrder);
      setRestaurantName(`Restaurant #${currentOrder.restaurant_id}`);
      try {
        const restaurant = await fetchRestaurantById(currentOrder.restaurant_id);
        if (restaurant?.name) setRestaurantName(restaurant.name);
      } catch {
        // Order details remain available if the public restaurant catalog is down.
      }
    } catch (requestError) {
      setError(requestError.message || 'This assigned delivery could not be loaded.');
    } finally {
      if (showLoader) setIsLoading(false);
    }
  }, [orderId]);

  useEffect(() => { void loadOrder(); }, [loadOrder, retryKey]);

  async function updateStatus(nextStatus) {
    if (!order) return;
    setAction(true);
    setError('');
    try {
      const updatedOrder = await updateDeliveryOrderStatus(order.id, nextStatus);
      setOrder(updatedOrder);
      await loadOrder(false);
    } catch (requestError) {
      const actionError = requestError.message || 'The delivery status could not be updated.';
      await loadOrder(false);
      setError((currentError) => currentError || actionError);
    } finally {
      setAction(false);
    }
  }

  return (
    <main className="discovery-page role-order-page">
      <Link className="back-link" to="/account/delivery-partner">← My deliveries</Link>
      {isLoading && <p className="state-panel" role="status">Loading assigned delivery…</p>}
      {!isLoading && error && !order && <section className="state-panel state-panel--error" role="alert"><p>{error}</p><button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></section>}
      {!isLoading && order && <>
        <header className="order-detail-header"><div><p className="eyebrow">Assigned delivery</p><h1 className="cart-title">Order #{order.id}</h1></div><span className={`order-status-badge order-status-badge--${order.status.toLowerCase()}`}>{order.status.replaceAll('_', ' ')}</span></header>
        {error && <p className="form-message form-message--error" role="alert">{error} <button className="inline-retry" type="button" onClick={() => setRetryKey((key) => key + 1)}>Reload order</button></p>}
        <RoleOrderDetails order={order} restaurantName={restaurantName} />
        <section className="role-actions-card" aria-label="Delivery status actions">
          <h2>Delivery status</h2>
          {order.status === 'ASSIGNED' && <button className="form-submit" type="button" disabled={action} onClick={() => void updateStatus('OUT_FOR_DELIVERY')}>{action ? 'Saving…' : 'Start delivery'}</button>}
          {order.status === 'OUT_FOR_DELIVERY' && <button className="form-submit" type="button" disabled={action} onClick={() => void updateStatus('DELIVERED')}>{action ? 'Saving…' : 'Mark delivered'}</button>}
          {order.status === 'DELIVERED' && <p className="role-action-note">This delivery is complete and appears in your delivered history.</p>}
          {!['ASSIGNED', 'OUT_FOR_DELIVERY', 'DELIVERED'].includes(order.status) && <p className="role-action-note">No delivery action is available for this order status.</p>}
        </section>
      </>}
    </main>
  );
}
