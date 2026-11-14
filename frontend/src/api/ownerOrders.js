import { apiFetch } from './client.js';

function orderParams({ page = 1, pageSize = 10, status, placedFrom, placedTo } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) params.set('status', status);
  if (placedFrom) params.set('placed_from', placedFrom);
  if (placedTo) params.set('placed_to', placedTo);
  return params;
}

export function fetchOwnerOrders(filters = {}) {
  return apiFetch(`/owner/orders?${orderParams(filters).toString()}`);
}

export async function fetchAllOwnerOrders(filters = {}) {
  const pageSize = 100;
  const firstPage = await fetchOwnerOrders({ ...filters, page: 1, pageSize });
  const orders = [...firstPage.items];
  const pageCount = Math.ceil(firstPage.total / firstPage.page_size);
  for (let page = 2; page <= pageCount; page += 1) {
    const result = await fetchOwnerOrders({ ...filters, page, pageSize });
    orders.push(...result.items);
  }
  return orders;
}

export async function fetchOwnerOrderById(orderId) {
  const pageSize = 100;
  const firstPage = await fetchOwnerOrders({ page: 1, pageSize });
  const found = firstPage.items.find((order) => order.id === Number(orderId));
  if (found) return found;
  const pageCount = Math.ceil(firstPage.total / firstPage.page_size);
  for (let page = 2; page <= pageCount; page += 1) {
    const result = await fetchOwnerOrders({ page, pageSize });
    const order = result.items.find((item) => item.id === Number(orderId));
    if (order) return order;
  }
  return null;
}

export function fetchOwnerRestaurant() {
  return apiFetch('/owner/restaurant');
}

export function fetchActiveDeliveryPartners() {
  return apiFetch('/owner/orders/delivery-partners');
}

export function acceptOwnerOrder(orderId) {
  return apiFetch(`/owner/orders/${orderId}/accept`, { method: 'POST' });
}

export function updateOwnerOrderStatus(orderId, status) {
  return apiFetch(`/owner/orders/${orderId}/status`, { method: 'PATCH', body: { status } });
}

export function assignDeliveryPartner(orderId, deliveryPartnerId) {
  return apiFetch(`/owner/orders/${orderId}/assign-delivery`, {
    method: 'POST', body: { delivery_partner_id: deliveryPartnerId },
  });
}
