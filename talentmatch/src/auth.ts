/**
 * Auth helpers — token storage + authenticated fetch wrapper.
 *
 * Token is stored in localStorage so it survives page reloads.
 * On every API call the token is attached as ``Authorization: Bearer <token>``.
 *
 * Session is automatically invalidated when:
 * - The user explicitly logs out
 * - Another device logs in with the same account (server returns 401)
 * - The token expires (server returns 401)
 */

const TOKEN_KEY = "talentmatch_token";
const USER_KEY = "talentmatch_user";

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: string;
}

// ---------------------------------------------------------------------------
// Token persistence
// ---------------------------------------------------------------------------

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// ---------------------------------------------------------------------------
// User persistence
// ---------------------------------------------------------------------------

export function getSavedUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveUser(user: AuthUser): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

// ---------------------------------------------------------------------------
// Auth state
// ---------------------------------------------------------------------------

export function isLoggedIn(): boolean {
  return getToken() !== null;
}

// ---------------------------------------------------------------------------
// Auth actions
// ---------------------------------------------------------------------------

export async function login(
  email: string,
  password: string,
): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch("/api/platform/storage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: "/api/auth/login",
      method: "POST",
      body: { email, password },
    }),
  });

  // If the proxy returns a non-JSON error, handle it gracefully
  let data: any;
  try {
    data = await res.json();
  } catch {
    throw new Error("服务暂不可用，请稍后重试");
  }

  if (!res.ok) {
    throw new Error(data.detail || data.error || "登录失败");
  }

  setToken(data.token);
  saveUser(data.user);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await authFetch("/api/auth/logout", { method: "POST" });
  } catch {
    // Even if the server call fails, clear local state
  }
  clearToken();
}

/**
 * Fetch with automatic Authorization header injection.
 * If the server returns 401, the token is cleared (session expired / kicked out).
 */
export async function authFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    // Dispatch a custom event so the UI can react
    window.dispatchEvent(new CustomEvent("auth:session-expired"));
  }

  return res;
}

/**
 * Fetch that goes through the Express platform proxy to FastAPI.
 * Uses the proxy path pattern: POST /api/platform/storage with {url, method, body}.
 */
export async function proxyAuthFetch(
  fastApiPath: string,
  options: { method?: string; body?: any } = {},
): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch("/api/platform/storage", {
    method: "POST",
    headers,
    body: JSON.stringify({
      url: fastApiPath,
      method: options.method || "GET",
      body: options.body,
    }),
  });

  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent("auth:session-expired"));
  }

  return res;
}
