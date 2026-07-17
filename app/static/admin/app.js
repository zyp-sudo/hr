/**
 * Admin Panel — Client-side utilities.
 * No framework dependencies — vanilla JS + Fetch API + SSE.
 *
 * Exposes window.Admin with:
 *   API.get/API.post  — typed fetch wrappers
 *   parseRequest(msg) — extract HTTP method/status/path/latency from log lines
 *   toast(msg, type)  — ephemeral notification
 *   escapeHtml / formatTime — render helpers
 */
(function () {
  'use strict';

  // ---- API helpers -------------------------------------------------------

  const API = {
    async get(url, params = {}) {
      const qs = new URLSearchParams(params).toString();
      const res = await fetch(`/api/admin${url}${qs ? '?' + qs : ''}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    },

    async post(url, body = {}) {
      const res = await fetch(`/api/admin${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    },
  };

  // ---- Toast notifications -----------------------------------------------

  function toast(msg, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => { el.remove(); }, 3500);
  }

  // ---- HTTP request parser -----------------------------------------------

  /**
   * Parse a middleware log line like:
   *   "GET     200  153ms    /api/admin/health-full"
   *   "POST    201  45ms     /api/talent-vectors/search"
   * Returns { isRequest, method, code, cls, path, latency }
   *
   * cls is one of: 'ok' (2xx), 'info' (3xx), 'warn' (4xx), 'error' (5xx)
   */
  function parseRequest(msg) {
    if (!msg) return { isRequest: false };

    // Middleware log format: METHOD  STATUS  LATENCY  PATH
    const re = /^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\d{3})\s+(\d+ms)\s+(.+)$/;
    const m = msg.match(re);
    if (!m) return { isRequest: false };

    const code = parseInt(m[2], 10);
    let cls = 'ok';
    if (code >= 500) cls = 'error';
    else if (code >= 400) cls = 'warn';
    else if (code >= 300) cls = 'info';

    return {
      isRequest: true,
      method: m[1],
      code: m[2],
      cls: cls,
      latency: m[3],
      path: m[4].split('?')[0],  // strip query string for display
    };
  }

  // ---- Render helpers ----------------------------------------------------

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return (ctx || document).querySelectorAll(sel); }

  function escapeHtml(str) {
    if (!str && str !== 0) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  function formatTime(ts) {
    if (!ts) return '—';
    return ts.replace('T', ' ').substring(0, 19);
  }

  // ---- Expose ------------------------------------------------------------
  window.Admin = { API, parseRequest, toast, $, $$, escapeHtml, formatTime };
})();
