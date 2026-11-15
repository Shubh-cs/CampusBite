import { apiFetch } from './client.js';

export function createOrder(payload) {
  return apiFetch('/orders', { method: 'POST', body: payload });
}

export function fetchOrder(orderId) {
  return apiFetch(`/orders/${orderId}`);
}

export function fetchCustomerOrders({ page = 1, pageSize = 10, status, placedFrom, placedTo } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) params.set('status', status);
  if (placedFrom) params.set('placed_from', placedFrom);
  if (placedTo) params.set('placed_to', placedTo);
  return apiFetch(`/orders?${params.toString()}`);
}

export function cancelOrder(orderId) {
  return apiFetch(`/orders/${orderId}/cancel`, { method: 'POST' });
}
