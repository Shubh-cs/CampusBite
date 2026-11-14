import { apiFetch } from './client.js';

export function askOrderInsights(question) {
  return apiFetch('/insights/orders', { method: 'POST', body: { question } });
}
