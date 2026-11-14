import { apiFetch } from './client.js';

export function fetchDeliveryOrders({ page = 1, pageSize = 10, status } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) params.set('status', status);
  return apiFetch(`/delivery/orders?${params.toString()}`);
}

export function fetchAssignedOrder(orderId) {
  return apiFetch(`/delivery/orders/${orderId}`);
}

export function updateDeliveryOrderStatus(orderId, status) {
  return apiFetch(`/delivery/orders/${orderId}/status`, { method: 'PATCH', body: { status } });
}
