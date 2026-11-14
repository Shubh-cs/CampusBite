import { formatINR } from '../context/CartContext.jsx';

const DATE_FORMAT = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata',
});

function formatDate(value) {
  return value ? DATE_FORMAT.format(new Date(value)) : null;
}

export function RoleOrderDetails({ order, restaurantName, showDeliveryPartner = false }) {
  return (
    <div className="role-order-layout">
      <section className="order-detail-card" aria-label="Order items">
        <h2>Order #{order.id}</h2>
        <p className="role-order-restaurant">{restaurantName || `Restaurant #${order.restaurant_id}`}</p>
        {order.items.map((item) => (
          <article className="order-detail-item" key={item.id}>
            <div><h3>{item.item_name}</h3><p>{item.quantity} × {formatINR(Math.round(Number(item.unit_price) * 100))}</p></div>
            <strong>{formatINR(Math.round(Number(item.unit_price) * item.quantity * 100))}</strong>
          </article>
        ))}
        <div className="order-total-row"><span>Total</span><strong>{formatINR(Math.round(Number(order.total_amount) * 100))}</strong></div>
      </section>
      <aside className="order-detail-card role-order-meta">
        <h2>Order information</h2>
        <p className="card-kicker">Status</p><p>{order.status.replaceAll('_', ' ')}</p>
        <p className="card-kicker">Delivery address</p><p>{order.delivery_address}</p>
        <p className="card-kicker">Placed</p><p>{formatDate(order.placed_at) || 'Date unavailable'}</p>
        {order.delivered_at && <><p className="card-kicker">Delivered</p><p>{formatDate(order.delivered_at)}</p></>}
        {order.updated_at && <p className="order-last-updated">Last updated {formatDate(order.updated_at)}</p>}
        {showDeliveryPartner && order.delivery_partner_id != null && (
          <><p className="card-kicker">Delivery partner</p><p>Partner #{order.delivery_partner_id}</p></>
        )}
      </aside>
    </div>
  );
}
