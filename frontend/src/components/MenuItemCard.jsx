export function MenuItemCard({ item }) {
  return (
    <article className="discovery-card dish-card">
      {item.image_url ? (
        <img className="dish-image" src={item.image_url} alt="" loading="lazy" />
      ) : (
        <div className="dish-image dish-image--placeholder" aria-hidden="true">✳</div>
      )}
      <div className="dish-copy">
        <div className="dish-heading">
          <div>
            <p className="card-kicker">{item.category}</p>
            <h2>{item.name}</h2>
          </div>
          <span className="dish-price">₹{Number(item.price).toFixed(2)}</span>
        </div>
        {item.description && <p className="card-description">{item.description}</p>}
      </div>
    </article>
  );
}
