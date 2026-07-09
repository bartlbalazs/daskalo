/** Default request timeout for backend HTTP-callable calls. */
export const DEFAULT_FETCH_TIMEOUT_MS = 30_000;

/**
 * Thin wrapper around the global `fetch` that adds the two reliability
 * guarantees plain `fetch()` is missing:
 *
 *   1. A timeout — `fetch()` never times out on its own, so a hung backend
 *      or dropped connection would otherwise leave callers awaiting forever
 *      (and the UI stuck in a loading/"evaluating" state). Implemented via
 *      `AbortController`, the standard mechanism for cancelling a `fetch`.
 *   2. An HTTP-status check — `fetch()` only rejects on network-level
 *      failures; a 4xx/5xx response resolves successfully with `response.ok
 *      === false`. Callers that skip checking `.ok` silently treat error
 *      pages/bodies as success. This throws a clear, status-coded Error for
 *      any non-2xx response so every caller gets consistent failure
 *      handling for free.
 *
 * Callers should still wrap the call in try/catch — this only standardizes
 * *what* gets thrown, not whether something can throw.
 */
export async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_FETCH_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error(`Request to ${url} timed out after ${timeoutMs}ms.`, { cause: err });
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    throw new Error(
      `Request to ${url} failed with status ${response.status}${response.statusText ? ` (${response.statusText})` : ''}.`
    );
  }

  return response;
}
