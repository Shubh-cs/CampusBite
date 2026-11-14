import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation, useNavigationType, useParams } from 'react-router-dom';
import {
  acceptOwnerOrder,
  assignDeliveryPartner,
  fetchActiveDeliveryPartners,
  fetchOwnerOrderById,
  fetchOwnerRestaurant,
  updateOwnerOrderStatus,
} from '../api/ownerOrders.js';
import { RoleOrderDetails } from '../components/RoleOrderDetails.jsx';

export function OwnerOrderDetailPage() {
  const { orderId } = useParams();
  const location = useLocation();
  const navigationType = useNavigationType();
  const isDashboardNavigation = navigationType === 'PUSH' && location.state?.source === 'owner-dashboard';
  const selectedOrder = isDashboardNavigation && location.state?.order?.id === Number(orderId)
    ? location.state.order
    : null;
  const [order, setOrder] = useState(selectedOrder);
  const [restaurantName, setRestaurantName] = useState('');
  const [partners, setPartners] = useState([]);
  const [selectedPartnerId, setSelectedPartnerId] = useState('');
  const [loadingPartners, setLoadingPartners] = useState(false);
  const [partnerError, setPartnerError] = useState('');
  const [isLoading, setIsLoading] = useState(!selectedOrder);
  const [action, setAction] = useState('');
  const [error, setError] = useState('');
  const [retryKey, setRetryKey] = useState(0);

  const reloadOrder = useCallback(async (showLoader = true) => {
    if (showLoader) setIsLoading(true);
    setError('');
    try {
      const currentOrder = await fetchOwnerOrderById(orderId);
      if (!currentOrder) throw new Error('Order not found for this restaurant.');
      setOrder(currentOrder);
    } catch (requestError) {
      setError(requestError.message || 'This order could not be loaded.');
    } finally {
      if (showLoader) setIsLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    if (selectedOrder) {
      setOrder(selectedOrder);
      setIsLoading(false);
    } else {
      void reloadOrder();
    }
    let active = true;
    fetchOwnerRestaurant().then((restaurant) => {
      if (active) setRestaurantName(restaurant.name);
    }).catch(() => {
      if (active && order) setRestaurantName(`Restaurant #${order.restaurant_id}`);
    });
    return () => { active = false; };
  }, [orderId, retryKey, reloadOrder]);

  useEffect(() => {
    if (order?.status !== 'READY') {
      setPartners([]);
      setPartnerError('');
      return undefined;
    }
    let active = true;
    setLoadingPartners(true);
    setPartnerError('');
    fetchActiveDeliveryPartners().then((result) => {
      if (active) setPartners(result);
    }).catch((requestError) => {
      if (active) setPartnerError(requestError.message || 'Active delivery partners could not be loaded.');
    }).finally(() => {
      if (active) setLoadingPartners(false);
    });
    return () => { active = false; };
  }, [order?.status, retryKey]);

  async function performAction(actionName, request) {
    if (!order) return;
    setAction(actionName);
    setError('');
    try {
      const updatedOrder = await request();
      setOrder(updatedOrder);
      await reloadOrder(false);
    } catch (requestError) {
      const actionError = requestError.message || 'The order could not be updated.';
      await reloadOrder(false);
      setError((currentError) => currentError || actionError);
    } finally {
      setAction('');
    }
  }

  return (
    <main className="discovery-page role-order-page">
      <Link className="back-link" to="/account/owner">← Owner dashboard</Link>
      {isLoading && <p className="state-panel" role="status">Loading owner order…</p>}
      {!isLoading && error && !order && <section className="state-panel state-panel--error" role="alert"><p>{error}</p><button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></section>}
      {!isLoading && order && <>
        <header className="order-detail-header"><div><p className="eyebrow">Owner order</p><h1 className="cart-title">Order #{order.id}</h1></div><span className={`order-status-badge order-status-badge--${order.status.toLowerCase()}`}>{order.status.replaceAll('_', ' ')}</span></header>
        {error && <p className="form-message form-message--error" role="alert">{error} <button className="inline-retry" type="button" onClick={() => setRetryKey((key) => key + 1)}>Reload order</button></p>}
        <RoleOrderDetails order={order} restaurantName={restaurantName} showDeliveryPartner />
        <section className="role-actions-card" aria-label="Order actions">
          <h2>Next action</h2>
          {order.status === 'PLACED' && <button className="form-submit" type="button" disabled={Boolean(action)} onClick={() => void performAction('accept', () => acceptOwnerOrder(order.id))}>{action ? 'Saving…' : 'Accept order'}</button>}
          {order.status === 'ACCEPTED' && <button className="form-submit" type="button" disabled={Boolean(action)} onClick={() => void performAction('preparing', () => updateOwnerOrderStatus(order.id, 'PREPARING'))}>{action ? 'Saving…' : 'Start preparation'}</button>}
          {order.status === 'PREPARING' && <button className="form-submit" type="button" disabled={Boolean(action)} onClick={() => void performAction('ready', () => updateOwnerOrderStatus(order.id, 'READY'))}>{action ? 'Saving…' : 'Mark ready'}</button>}
          {order.status === 'READY' && <div className="partner-assignment">
            {loadingPartners && <p role="status">Loading active delivery partners…</p>}
            {partnerError && <p className="form-message form-message--error" role="alert">{partnerError} <button className="inline-retry" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></p>}
            {!loadingPartners && !partnerError && partners.length === 0 && <p className="state-panel">No active delivery partners are available.</p>}
            {partners.length > 0 && <>
              <label className="role-select-field"><span>Active delivery partner</span><select value={selectedPartnerId} onChange={(event) => setSelectedPartnerId(event.target.value)}><option value="">Choose a partner</option>{partners.map((partner) => <option value={partner.id} key={partner.id}>{partner.full_name}</option>)}</select></label>
              <button className="form-submit" type="button" disabled={!selectedPartnerId || Boolean(action)} onClick={() => void performAction('assign', () => assignDeliveryPartner(order.id, Number(selectedPartnerId)))}>{action ? 'Assigning…' : 'Assign delivery partner'}</button>
            </>}
          </div>}
          {!['PLACED', 'ACCEPTED', 'PREPARING', 'READY'].includes(order.status) && <p className="role-action-note">No owner action is available for this order status.</p>}
        </section>
      </>}
    </main>
  );
}
