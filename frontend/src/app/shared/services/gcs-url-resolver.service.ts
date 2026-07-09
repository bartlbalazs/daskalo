import { Injectable, inject } from '@angular/core';
import { Storage, ref, getDownloadURL } from '@angular/fire/storage';

/**
 * Resolves `gs://` URIs to fetchable HTTPS download URLs via Firebase
 * Storage, caching the in-flight/resolved `Promise<string>` per URI so
 * repeated requests for the same asset — e.g. re-rendering a grammar
 * example, replaying a vocabulary word, or revisiting an already-seen
 * chapter/exercise — reuse one Storage call instead of re-issuing a fresh
 * `getDownloadURL()` request every time.
 *
 * Plain http(s) URLs are passed through unchanged (some assets are already
 * fully resolved, e.g. in local dev without a real Storage bucket).
 *
 * Entries are never evicted: the set of distinct asset URIs referenced by
 * a chapter/practice-set is bounded (content-cli-authored curriculum
 * assets, not unbounded user input), so an ever-growing cache is a
 * non-issue in practice.
 */
@Injectable({ providedIn: 'root' })
export class GcsUrlResolverService {
  private storage = inject(Storage);

  private readonly cache = new Map<string, Promise<string>>();

  /**
   * Resolve a `gs://` URI to a download URL, or pass through a non-`gs://`
   * value (already a usable URL) unchanged. Concurrent/repeated calls for
   * the same URI share the same underlying promise.
   */
  resolve(uri: string): Promise<string> {
    if (!uri.startsWith('gs://')) return Promise.resolve(uri);

    const cached = this.cache.get(uri);
    if (cached) return cached;

    const promise = getDownloadURL(ref(this.storage, uri)).catch((err: unknown) => {
      // Don't poison the cache with a permanently-rejected promise — a
      // transient failure (e.g. offline) shouldn't block every future
      // retry for this URI for the lifetime of the app.
      this.cache.delete(uri);
      throw err;
    });
    this.cache.set(uri, promise);
    return promise;
  }
}
