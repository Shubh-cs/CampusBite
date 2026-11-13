import { Link } from 'react-router-dom';

export function RestaurantCard({ restaurant }) {
  return (
    <article className="discovery-card restaurant-card">
      <div className="card-accent" aria-hidden="true">CB</div>
      <div className="card-copy">
        <p className="card-kicker">Campus restaurant</p>
        <h2>{restaurant.name}</h2>
        <p className="card-description">{restaurant.description || 'Good food, ready for your next campus break.'}</p>
        <p className="card-address"><span aria-hidden="true">⌖</span>{restaurant.address}</p>
      </div>
      <Link className="card-link" to={`/restaurants/${restaurant.id}`} aria-label={`View menu for ${restaurant.name}`}>
        Explore menu <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}
