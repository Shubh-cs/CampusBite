import { apiFetch } from './client.js';

export function fetchOrderReview(orderId) {
  return apiFetch(`/orders/${orderId}/review`);
}

export function submitOrderReview(orderId, payload) {
  return apiFetch(`/orders/${orderId}/review`, { method: 'POST', body: payload });
}
