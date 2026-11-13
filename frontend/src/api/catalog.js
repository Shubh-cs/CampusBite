import { apiFetch } from './client.js';

const RESTAURANT_PAGE_SIZE = 100;

export function fetchRestaurants(page = 1) {
  return apiFetch(`/restaurants?page=${page}&page_size=10`, { auth: false });
}

export async function fetchRestaurantById(restaurantId) {
  let page = 1;
  let total = Number.POSITIVE_INFINITY;

  while ((page - 1) * RESTAURANT_PAGE_SIZE < total) {
    const result = await apiFetch(
      `/restaurants?page=${page}&page_size=${RESTAURANT_PAGE_SIZE}`,
      { auth: false },
    );
    const restaurant = result.items.find((item) => item.id === restaurantId);
    if (restaurant) return restaurant;
    total = result.total;
    page += 1;
  }

  return null;
}

export function fetchRestaurantMenu(restaurantId, filters, page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: '10' });
  if (filters.search.trim()) params.set('search', filters.search.trim());
  if (filters.minPrice !== '') params.set('min_price', filters.minPrice);
  if (filters.maxPrice !== '') params.set('max_price', filters.maxPrice);
  return apiFetch(`/restaurants/${restaurantId}/menu-items?${params.toString()}`, { auth: false });
}
