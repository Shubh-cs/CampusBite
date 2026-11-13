import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError } from '../api/client.js';
import { fetchRestaurantById, fetchRestaurantMenu } from '../api/catalog.js';
import { MenuItemCard } from '../components/MenuItemCard.jsx';
import { Pagination } from '../components/Pagination.jsx';

const EMPTY_FILTERS = { search: '', minPrice: '', maxPrice: '' };

function asNonNegativeAmount(value) {
  if (value === '') return true;
  const amount = Number(value);
  return Number.isFinite(amount) && amount >= 0;
}

export function RestaurantMenuPage() {
  const { restaurantId: restaurantIdParam } = useParams();
  const restaurantId = Number(restaurantIdParam);
  const validRestaurantId = Number.isSafeInteger(restaurantId) && restaurantId > 0;
  const [restaurant, setRestaurant] = useState(null);
  const [result, setResult] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterError, setFilterError] = useState('');
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError('');

    if (!validRestaurantId) {
      setError('That restaurant could not be found.');
      setIsLoading(false);
      return () => { current = false; };
    }

    Promise.all([
      fetchRestaurantById(restaurantId),
      fetchRestaurantMenu(restaurantId, filters, page),
    ])
      .then(([restaurantData, menuData]) => {
        if (!current) return;
        if (!restaurantData) {
          setError('That restaurant could not be found.');
          return;
        }
        setRestaurant(restaurantData);
        setResult(menuData);
      })
      .catch((requestError) => {
        if (current) setError(requestError instanceof ApiError ? requestError.message : 'This menu could not be loaded. Please try again.');
      })
      .finally(() => { if (current) setIsLoading(false); });

    return () => { current = false; };
  }, [restaurantId, validRestaurantId, filters, page, retryKey]);

  function updateDraft(field, value) {
    setDraftFilters((current) => ({ ...current, [field]: value }));
    setFilterError('');
  }

  function applyFilters(event) {
    event.preventDefault();
    if (!asNonNegativeAmount(draftFilters.minPrice) || !asNonNegativeAmount(draftFilters.maxPrice)) {
      setFilterError('Enter valid prices that are zero or greater.');
      return;
    }
    if (draftFilters.minPrice !== '' && draftFilters.maxPrice !== '' && Number(draftFilters.minPrice) > Number(draftFilters.maxPrice)) {
      setFilterError('Minimum price must not exceed maximum price.');
      return;
    }
    setFilterError('');
    setPage(1);
    setFilters({
      search: draftFilters.search.trim(),
      minPrice: draftFilters.minPrice,
      maxPrice: draftFilters.maxPrice,
    });
  }

  function clearFilters() {
    setDraftFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setFilterError('');
    setPage(1);
  }

  return (
    <main className="discovery-page">
      <Link className="back-link" to="/restaurants">← All restaurants</Link>

      {!isLoading && error ? (
        <div className="state-panel state-panel--error" role="alert">
          <p>{error}</p>
          <button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Try again</button>
        </div>
      ) : (
        <>
          {restaurant && (
            <section className="restaurant-hero">
              <p className="eyebrow">Restaurant menu</p>
              <h1>{restaurant.name}</h1>
              {restaurant.description && <p className="intro">{restaurant.description}</p>}
              <p className="restaurant-address"><span aria-hidden="true">⌖</span>{restaurant.address}</p>
            </section>
          )}

          <section aria-labelledby="menu-heading">
        <div className="section-heading section-heading--menu">
          <div>
            <p className="card-kicker">Fresh from the kitchen</p>
            <h2 id="menu-heading">Available dishes</h2>
          </div>
          {result && <span className="result-count">{result.total} {result.total === 1 ? 'dish' : 'dishes'}</span>}
        </div>

        <form className="menu-filters" onSubmit={applyFilters}>
          <label className="filter-field filter-field--search">
            <span>Search dishes</span>
            <input
              type="search"
              maxLength={160}
              placeholder="Try noodles, curry, sandwich…"
              value={draftFilters.search}
              onChange={(event) => updateDraft('search', event.target.value)}
            />
          </label>
          <label className="filter-field">
            <span>Minimum price</span>
            <input type="number" min="0" step="0.01" inputMode="decimal" placeholder="₹0" value={draftFilters.minPrice} onChange={(event) => updateDraft('minPrice', event.target.value)} />
          </label>
          <label className="filter-field">
            <span>Maximum price</span>
            <input type="number" min="0" step="0.01" inputMode="decimal" placeholder="No limit" value={draftFilters.maxPrice} onChange={(event) => updateDraft('maxPrice', event.target.value)} />
          </label>
          <div className="filter-actions">
            <button className="form-submit" type="submit">Apply filters</button>
            <button className="text-button" type="button" onClick={clearFilters}>Clear</button>
          </div>
        </form>
        {filterError && <p className="form-message form-message--error filter-error" role="alert">{filterError}</p>}

        {isLoading && <p className="state-panel" role="status">Loading the menu…</p>}
        {!isLoading && !error && result?.items.length === 0 && (
          <div className="state-panel">
            <p>No available dishes match these filters.</p>
            {(filters.search || filters.minPrice || filters.maxPrice) && <button className="secondary-button" type="button" onClick={clearFilters}>Clear filters</button>}
          </div>
        )}
        {!isLoading && !error && result?.items.length > 0 && (
          <>
            <div className="dish-grid">
              {result.items.map((item) => <MenuItemCard key={item.id} item={item} />)}
            </div>
            <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPageChange={setPage} />
          </>
        )}
          </section>
        </>
      )}
    </main>
  );
}
