/**
 * chatApi.js — Chat API Service
 * Thin wrapper around /api/v1/chat/* endpoints.
 * All calls require a valid JWT Bearer token.
 *
 * Error handling maps HTTP status codes to human-readable messages
 * so UI components never show raw backend exceptions.
 */

const BASE = '/api/v1/chat';

function authHeaders(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

// ── Human-readable error messages by HTTP status ──────────────────────────────

const STATUS_MESSAGES = {
  400: 'Invalid request. Please check your input and try again.',
  401: 'Your session has expired. Please log in again.',
  403: 'You do not have permission to perform this action.',
  404: 'The requested conversation or document was not found.',
  409: 'A conflict occurred. Please refresh and try again.',
  422: 'The request could not be processed. Please check your input.',
  429: 'Too many requests. Please wait a moment and try again.',
  500: 'The server encountered an error. Please try again shortly.',
  502: 'The server is temporarily unavailable. Please try again.',
  503: 'The service is currently unavailable. Please try again later.',
};

async function handleResponse(res) {
  // 204 No Content — success with no body
  if (res.status === 204) return null;

  let data = {};
  try {
    data = await res.json();
  } catch {
    // Body is not JSON (e.g. gateway HTML error page)
  }

  if (!res.ok) {
    // Prefer the server's detail message; fall back to our status map; last resort generic
    const serverDetail = data?.detail;
    const statusMsg    = STATUS_MESSAGES[res.status];
    const fallback     = `Request failed (${res.status})`;
    throw new Error(serverDetail || statusMsg || fallback);
  }

  return data;
}

async function safeFetch(url, options) {
  try {
    return await fetch(url, options);
  } catch (err) {
    // Network-level failure (offline, DNS, CORS, etc.)
    throw new Error('Network error — please check your connection and try again.');
  }
}

// ── Conversations ────────────────────────────────────────────────────────────

/**
 * Create a new conversation.
 * @param {string} token
 * @param {{ title?: string, mode: 'general'|'document'|'rag', document_id?: number|null }} payload
 */
export async function createConversation(token, payload) {
  const res = await safeFetch(`${BASE}/conversations`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

/**
 * List the user's conversations, sorted by recent activity.
 * @param {string} token
 * @param {{ page?: number, page_size?: number, mode?: string }} opts
 */
export async function listConversations(token, opts = {}) {
  const params = new URLSearchParams();
  if (opts.page)      params.set('page',      opts.page);
  if (opts.page_size) params.set('page_size', opts.page_size);
  if (opts.mode)      params.set('mode',      opts.mode);

  const res = await safeFetch(`${BASE}/conversations?${params}`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

/**
 * Get a conversation with full message history.
 * @param {string} token
 * @param {number} conversationId
 */
export async function getConversation(token, conversationId) {
  const res = await safeFetch(`${BASE}/conversations/${conversationId}`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

/**
 * Rename a conversation.
 * @param {string} token
 * @param {number} conversationId
 * @param {string} title
 */
export async function renameConversation(token, conversationId, title) {
  const res = await safeFetch(`${BASE}/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify({ title }),
  });
  return handleResponse(res);
}

/**
 * Delete a conversation and all its messages.
 * @param {string} token
 * @param {number} conversationId
 */
export async function deleteConversation(token, conversationId) {
  const res = await safeFetch(`${BASE}/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

// ── Messages ─────────────────────────────────────────────────────────────────

/**
 * Send a user message and receive an AI response.
 * @param {string} token
 * @param {number} conversationId
 * @param {string} message
 */
export async function sendMessage(token, conversationId, message) {
  const res = await safeFetch(`${BASE}/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ message }),
  });
  return handleResponse(res);
}
