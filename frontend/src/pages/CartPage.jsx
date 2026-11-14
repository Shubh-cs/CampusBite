import { Link } from 'react-router-dom';
import { formatINR, itemSubtotalPaise, useCart } from '../context/CartContext.jsx';

export function CartPage() {
  const {
    cart,
    itemCount,
    subtotalPaise,
    isRevalidating,
    revalidationError,
    storageError,
    increaseQuantity,
    decreaseQuantity,
    removeItem,
    acceptPriceChange,
  } = useCart();

  return (
    <main className="discovery-page cart-page">
      <p className="eyebrow">Your selections</p>
      <h1 className="cart-title">Shopping cart</h1>
      {storageError && <p className="form-message form-message--error" role="alert">{storageError}</p>}
      {isRevalidating && <p className="state-panel cart-status" role="status">Checking saved items against the current menu…</p>}
      {revalidationError && <p className="state-panel state-panel--error cart-status" role="alert">{revalidationError} Item availability and prices could not be confirmed.</p>}

      {!cart.items.length ? (
        <section className="state-panel cart-empty">
          <h2>Your cart is empty</h2>
          <p>Browse restaurants and add a dish to get started.</p>
          <Link className="form-submit cart-browse-link" to="/restaurants">Browse restaurants</Link>
        </section>
      ) : (
        <div className="cart-layout">
          <section className="cart-items" aria-label="Cart items">
            <div className="cart-restaurant-heading">
              <div>
                <p className="card-kicker">One restaurant per cart</p>
                <h2>{cart.restaurantName}</h2>
              </div>
              <span className="result-count">{itemCount} {itemCount === 1 ? 'item' : 'items'}</span>
            </div>

            {cart.items.map((item) => (
              <article className="cart-item" key={item.menuItemId}>
                <div className="cart-item-copy">
                  <h3>{item.name}</h3>
                  <p className="cart-unit-price">{formatINR(item.unitPrice)} <span>each</span></p>
                  {item.availability === 'unavailable' && (
                    <p className="cart-item-alert" role="status">This dish is unavailable or no longer on the menu. Remove it before continuing.</p>
                  )}
                  {item.availability === 'unverified' && (
                    <p className="cart-item-alert" role="status">Availability could not be confirmed. Check your connection and refresh the cart.</p>
                  )}
                  {item.currentUnitPrice && (
                    <div className="price-change" role="status">
                      <p>Menu price changed: {formatINR(item.unitPrice)} → <strong>{formatINR(item.currentUnitPrice)}</strong>.</p>
                      <p>Your saved price remains until you accept this change.</p>
                      <button className="secondary-button" type="button" onClick={() => acceptPriceChange(item.menuItemId)}>
                        Accept new price
                      </button>
                    </div>
                  )}
                </div>
                <div className="cart-item-actions">
                  <div className="quantity-control" aria-label={`Quantity for ${item.name}`}>
                    <button type="button" aria-label={`Decrease ${item.name} quantity`} disabled={item.quantity <= 1} onClick={() => decreaseQuantity(item.menuItemId)}>−</button>
                    <output aria-live="polite">{item.quantity}</output>
                    <button type="button" aria-label={`Increase ${item.name} quantity`} onClick={() => increaseQuantity(item.menuItemId)}>+</button>
                  </div>
                  <strong className="cart-line-total">{formatINR(itemSubtotalPaise(item))}</strong>
                  <button className="remove-item-button" type="button" onClick={() => removeItem(item.menuItemId)}>Remove</button>
                </div>
              </article>
            ))}
          </section>

          <aside className="cart-summary" aria-label="Cart summary">
            <p className="card-kicker">Summary</p>
            <h2>Subtotal</h2>
            <p className="cart-subtotal">{formatINR(subtotalPaise)}</p>
            <p className="cart-summary-note">Shown using the saved item prices. Final prices are confirmed by the server during checkout.</p>
            <Link className="secondary-link" to="/restaurants">Continue browsing</Link>
          </aside>
        </div>
      )}
    </main>
  );
}
