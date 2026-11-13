import { useEffect, useState } from 'react';
import { ApiError } from '../api/client.js';
import { fetchRestaurants } from '../api/catalog.js';
import { Pagination } from '../components/Pagination.jsx';
import { RestaurantCard } from '../components/RestaurantCard.jsx';

export function RestaurantListPage() {
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError('');
    fetchRestaurants(page)
      .then((data) => { if (current) setResult(data); })
      .catch((requestError) => {
        if (current) setError(requestError instanceof ApiError ? requestError.message : 'Restaurants could not be loaded. Please try again.');
      })
      .finally(() => { if (current) setIsLoading(false); });
    return () => { current = false; };
  }, [page, retryKey]);

  return (
    <main className="discovery-page">
      <section className="discovery-hero">
        <p className="eyebrow">A little closer to good food</p>
        <h1>Find your campus favorite.</h1>
        <p className="intro">Browse local restaurants and see what’s cooking today.</p>
      </section>

      <section aria-labelledby="restaurants-heading">
        <div className="section-heading">
          <div>
            <p className="card-kicker">Made for campus days</p>
            <h2 id="restaurants-heading">Restaurants</h2>
          </div>
          {result && <span className="result-count">{result.total} {result.total === 1 ? 'place' : 'places'}</span>}
        </div>

        {isLoading && <p className="state-panel" role="status">Finding restaurants…</p>}
        {!isLoading && error && (
          <div className="state-panel state-panel--error" role="alert">
            <p>{error}</p>
            <button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Try again</button>
          </div>
        )}
        {!isLoading && !error && result?.items.length === 0 && (
          <p className="state-panel">No restaurants are listed yet. Please check back soon.</p>
        )}
        {!isLoading && !error && result?.items.length > 0 && (
          <>
            <div className="restaurant-grid">
              {result.items.map((restaurant) => <RestaurantCard key={restaurant.id} restaurant={restaurant} />)}
            </div>
            <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPageChange={setPage} />
          </>
        )}
      </section>
    </main>
  );
}
