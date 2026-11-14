export function RestaurantSwitchDialog({ currentRestaurant, nextRestaurant, onKeepCart, onReplaceCart }) {
  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="switch-dialog" role="dialog" aria-modal="true" aria-labelledby="switch-dialog-title">
        <p className="card-kicker">One restaurant per cart</p>
        <h2 id="switch-dialog-title">Start a new cart?</h2>
        <p className="card-description">
          Your cart has items from <strong>{currentRestaurant}</strong>. Replace it with an item from <strong>{nextRestaurant}</strong>?
        </p>
        <div className="dialog-actions">
          <button className="secondary-button" type="button" onClick={onKeepCart}>Keep current cart</button>
          <button className="form-submit" type="button" onClick={onReplaceCart}>Replace cart</button>
        </div>
      </section>
    </div>
  );
}
