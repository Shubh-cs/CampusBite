import { apiFetch } from './client.js';

export function createOrder(payload) {
  return apiFetch('/orders', { method: 'POST', body: payload });
}

export function fetchOrder(orderId) {
  return apiFetch(`/orders/${orderId}`);
}

export function fetchCustomerOrders(page = 1, pageSize = 10) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return apiFetch(`/orders?${params.toString()}`);
}

export function cancelOrder(orderId) {
  return apiFetch(`/orders/${orderId}/cancel`, { method: 'POST' });
}
