import { apiFetch } from './client.js';

export function fetchOwnerReminders(page = 1, pageSize = 10) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return apiFetch(`/owner/reminders?${params.toString()}`);
}
