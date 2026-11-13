export const ACCESS_TOKEN_KEY = 'campusbite_access_token';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function getAccessToken() {
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveAccessToken(token) {
  try {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  } catch {
    throw new ApiError('Your browser could not save the sign-in session. Check local storage settings.');
  }
}

export function clearAccessToken() {
  try {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  } catch {
    // Clearing React auth state still signs the user out in the current tab.
  }
}

function getErrorMessage(payload, status) {
  const detail = payload?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((issue) => {
        const field = issue.loc?.filter((part) => part !== 'body').join('.');
        return field ? `${field}: ${issue.msg}` : issue.msg;
      })
      .join(' ');
  }
  return `The request failed (${status}). Please try again.`;
}

export async function apiFetch(path, options = {}) {
  const { auth = true, body, headers: suppliedHeaders, ...fetchOptions } = options;
  const headers = new Headers(suppliedHeaders || {});
  let requestBody = body;

  if (body !== undefined && typeof body !== 'string' && !(body instanceof FormData)) {
    requestBody = JSON.stringify(body);
    headers.set('Content-Type', 'application/json');
  }

  const token = auth ? getAccessToken() : null;
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      body: requestBody,
      headers,
    });
  } catch {
    throw new ApiError('Cannot reach the CampusBite API. Check that the backend is running.');
  }

  if (response.status === 204) return null;

  const responseText = await response.text();
  let payload = null;
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(getErrorMessage(payload, response.status), response.status);
  }

  return payload;
}
