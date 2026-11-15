import { apiFetch } from './client.js';

export function fetchOwnerMenuItems(page = 1, pageSize = 10) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return apiFetch(`/owner/menu-items?${params.toString()}`);
}

export function createOwnerMenuItem(payload) {
  return apiFetch('/owner/menu-items', { method: 'POST', body: payload });
}

export function updateOwnerMenuItem(menuItemId, payload) {
  return apiFetch(`/owner/menu-items/${menuItemId}`, { method: 'PATCH', body: payload });
}
