import { apiFetch } from './client.js';

export function createOrder(payload) {
  return apiFetch('/orders', { method: 'POST', body: payload });
}

export function fetchOrder(orderId) {
  return apiFetch(`/orders/${orderId}`);
}
