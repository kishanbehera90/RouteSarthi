import { useAuthStore } from '../store/useAuthStore'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`)
    this.status = status
    this.detail = detail
  }
}

// Thin fetch wrapper for authenticated calls: attaches the bearer token,
// JSON-encodes the body, and clears the session on a 401 (expired/invalid
// token) so a stale token doesn't keep silently failing every request.
export async function apiFetch(path, { method = 'GET', body } = {}) {
  const token = useAuthStore.getState().token
  const res = await fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    useAuthStore.getState().logout()
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new ApiError(res.status, data.detail)
  }
  if (res.status === 204) return null
  return res.json()
}
