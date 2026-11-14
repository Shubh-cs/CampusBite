import { apiFetch } from './client.js';

export function fetchOrderRefundRequest(orderId) {
  return apiFetch(`/orders/${orderId}/refund-request`);
}

export function createOrderRefundRequest(orderId, reason) {
  return apiFetch(`/orders/${orderId}/refund-request`, { method: 'POST', body: { reason } });
}

export function fetchOwnerRefundRequests({ page = 1, pageSize = 10, status } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) params.set('status', status);
  return apiFetch(`/owner/refund-requests?${params.toString()}`);
}

export function decideOwnerRefundRequest(requestId, status) {
  return apiFetch(`/owner/refund-requests/${requestId}`, { method: 'PATCH', body: { status } });
}
