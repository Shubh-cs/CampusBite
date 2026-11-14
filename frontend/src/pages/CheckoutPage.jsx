import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client.js';
import { createOrder } from '../api/orders.js';
import { formatINR, itemSubtotalPaise, useCart } from '../context/CartContext.jsx';

function getDetail(error) {
  return error instanceof ApiError ? error.payload?.detail : null;
}

export function CheckoutPage() {
  const {
    cart, subtotalPaise, isRevalidating, revalidationError, storageError,
    acceptPriceChanges, markItemsUnavailable, setItemsPriceChanges, clearCart,
  } = useCart();
  const navigate = useNavigate();
  const [address, setAddress] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [requiresSignIn, setRequiresSignIn] = useState(false);
  const [priceChanges, setPriceChanges] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const blockedItems = cart.items.filter((item) => item.availability !== 'available' || item.currentUnitPrice);
  const canSubmit = cart.items.length > 0 && !isRevalidating && !revalidationError && !blockedItems.length && address.trim() && !isSubmitting;

  async function submitOrder(expectedPrices = null) {
    setIsSubmitting(true);
    setErrorMessage('');
    setRequiresSignIn(false);
    setPriceChanges([]);
    const overrides = expectedPrices || new Map();
    const payload = {
      items: cart.items.map((item) => ({
        menu_item_id: item.menuItemId,
        quantity: item.quantity,
        expected_unit_price: overrides.get(item.menuItemId) || item.unitPrice,
      })),
      delivery_address: address.trim(),
    };

    try {
      const order = await createOrder(payload);
      if (!Number.isSafeInteger(order?.id)) throw new Error('The server response did not include an order number. Your cart is preserved.');
      clearCart();
      navigate(`/order-confirmation/${order.id}`, { replace: true, state: { order } });
    } catch (error) {
      const detail = getDetail(error);
      if (error instanceof ApiError && error.status === 409 && detail?.code === 'PRICE_CHANGED' && Array.isArray(detail.items)) {
        setPriceChanges(detail.items);
        setItemsPriceChanges(detail.items);
        setErrorMessage('Some menu prices changed. Review and confirm the current prices before retrying.');
      } else if (error instanceof ApiError && error.status === 409 && detail?.code === 'ITEM_UNAVAILABLE' && Array.isArray(detail.items)) {
        markItemsUnavailable(detail.items.map((item) => item.menu_item_id));
        setErrorMessage('One or more dishes are no longer available. Remove them from your cart before retrying.');
      } else if (error instanceof ApiError && error.status === 404 && detail?.code === 'MENU_ITEM_NOT_FOUND') {
        markItemsUnavailable(detail.menu_item_ids || []);
        setErrorMessage('One or more dishes are no longer on the menu. Remove them from your cart before retrying.');
      } else if (error instanceof ApiError && error.status === 401) {
        setRequiresSignIn(true);
        setErrorMessage('Your sign-in session has expired. Your cart is saved; sign in again to place the order.');
      } else if (error instanceof ApiError && error.status === 422) {
        setErrorMessage(error.message || 'Please check the address and cart details.');
      } else if (error instanceof ApiError && error.status >= 500) {
        setErrorMessage('The server could not place your order. Your cart is unchanged; please try again.');
      } else {
        setErrorMessage(error.message || 'We could not place your order. Your cart is unchanged; please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function confirmPriceChanges() {
    const priceMap = new Map(priceChanges.map((item) => [item.menu_item_id, String(item.current_unit_price)]));
    acceptPriceChanges(priceChanges);
    void submitOrder(priceMap);
  }

  return (
    <main className="discovery-page checkout-page">
      <p className="eyebrow">Delivery details</p>
      <h1 className="cart-title">Checkout</h1>
      {storageError && <p className="form-message form-message--error" role="alert">{storageError}</p>}
      {revalidationError && <p className="state-panel state-panel--error" role="alert">{revalidationError}</p>}
      {errorMessage && <p className="form-message form-message--error" role="alert">{errorMessage} {requiresSignIn && <Link to="/login" state={{ from: { pathname: '/checkout' } }}>Sign in again</Link>}</p>}

      {!cart.items.length ? (
        <section className="state-panel cart-empty">
          <h2>Your cart is empty</h2>
          <p>Add dishes before checking out.</p>
          <Link className="form-submit cart-browse-link" to="/restaurants">Browse restaurants</Link>
        </section>
      ) : (
        <div className="cart-layout">
          <section className="cart-items" aria-label="Order review">
            <div className="cart-restaurant-heading"><div><p className="card-kicker">Restaurant</p><h2>{cart.restaurantName}</h2></div></div>
            {cart.items.map((item) => (
              <article className="cart-item" key={item.menuItemId}>
                <div className="cart-item-copy">
                  <h3>{item.name}</h3>
                  <p className="cart-unit-price">{formatINR(item.unitPrice)} <span>each · quantity {item.quantity}</span></p>
                  {item.currentUnitPrice && <p className="cart-item-alert">Current menu price: {formatINR(item.currentUnitPrice)}. Review in your cart before checkout.</p>}
                  {item.availability === 'unavailable' && <p className="cart-item-alert">This item is unavailable or has been removed from the menu.</p>}
                  {item.availability === 'unverified' && <p className="cart-item-alert">Item availability could not be confirmed.</p>}
                </div>
                <strong className="cart-line-total">{formatINR(itemSubtotalPaise(item))}</strong>
              </article>
            ))}
          </section>
          <aside className="cart-summary" aria-label="Checkout summary">
            <p className="card-kicker">Delivery</p>
            <label className="form-field checkout-address">
              <span>Delivery address</span>
              <textarea rows="4" required value={address} onChange={(event) => setAddress(event.target.value)} placeholder="Enter your campus or delivery address" />
            </label>
            <h2>Subtotal</h2>
            <p className="cart-subtotal">{formatINR(subtotalPaise)}</p>
            <p className="cart-summary-note">The server verifies availability and calculates the final total when you place the order.</p>
            {isRevalidating && <p role="status" className="cart-summary-note">Checking current menu…</p>}
            {blockedItems.length > 0 && !isRevalidating && <p className="cart-item-alert">Resolve price or availability notices before continuing.</p>}
            <button className="form-submit checkout-submit" type="button" disabled={!canSubmit} onClick={() => void submitOrder()}>
              {isSubmitting ? 'Placing order…' : 'Place order'}
            </button>
            <Link className="secondary-link" to="/cart">Back to cart</Link>
          </aside>
        </div>
      )}

      {priceChanges.length > 0 && (
          <section className="price-confirmation" role="alert" aria-labelledby="price-confirmation-title" aria-describedby="price-confirmation-description">
          <h2 id="price-confirmation-title">Review menu price changes</h2>
          <p id="price-confirmation-description">Your order was not placed. Confirm these prices to update your cart and retry checkout.</p>
          <ul>
            {priceChanges.map((item) => <li key={item.menu_item_id}>{item.name}: {formatINR(item.expected_unit_price)} → <strong>{formatINR(item.current_unit_price)}</strong></li>)}
          </ul>
          <button className="form-submit" type="button" disabled={isSubmitting} onClick={confirmPriceChanges}>Accept current prices and retry</button>
        </section>
      )}
    </main>
  );
}
