import { Injectable, inject, signal, computed } from '@angular/core';
import {
  Firestore,
  collection,
  doc,
  getDocs,
  setDoc,
  deleteDoc,
  serverTimestamp,
} from '@angular/fire/firestore';
import { Auth } from '@angular/fire/auth';
import { FavoriteWord, VocabularyItem } from '../models/firestore.models';

/** Build the document ID for a favorite word: `{chapterId}__{greek}`. */
function favoriteDocId(chapterId: string, greek: string): string {
  return `${chapterId}__${greek}`;
}

@Injectable({ providedIn: 'root' })
export class FavoriteWordsService {
  private firestore = inject(Firestore);
  private auth = inject(Auth);

  /** Map of docId → FavoriteWord, populated by loadFavorites(). */
  private _favorites = signal<Map<string, FavoriteWord>>(new Map());

  /** Public read-only signal: Map<docId, FavoriteWord>. */
  readonly favorites = computed(() => this._favorites());

  /** True when the service has performed its initial load. */
  private _loaded = false;

  // ---------------------------------------------------------------------------
  // Queries
  // ---------------------------------------------------------------------------

  /** Returns true if the given word from the given chapter is currently favorited. */
  isFavorited(chapterId: string, greek: string): boolean {
    return this._favorites().has(favoriteDocId(chapterId, greek));
  }

  /** Flat array of all favorited words, sorted alphabetically by Greek. */
  readonly allFavorites = computed<FavoriteWord[]>(() =>
    Array.from(this._favorites().values()).sort((a, b) =>
      a.greek.localeCompare(b.greek, 'el')
    )
  );

  // ---------------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------------

  /**
   * Load all favorite words for the current user from Firestore into the local signal.
   * Safe to call multiple times — subsequent calls refresh the data.
   */
  async loadFavorites(): Promise<void> {
    const uid = this.auth.currentUser?.uid;
    if (!uid) return;

    const ref = collection(this.firestore, 'users', uid, 'favoriteWords');
    const snap = await getDocs(ref);
    const map = new Map<string, FavoriteWord>();
    for (const d of snap.docs) {
      map.set(d.id, d.data() as FavoriteWord);
    }
    this._favorites.set(map);
    this._loaded = true;
  }

  /** Load favorites once (no-op on subsequent calls unless force=true). */
  async ensureLoaded(force = false): Promise<void> {
    if (!this._loaded || force) {
      await this.loadFavorites();
    }
  }

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  /**
   * Toggle the favorite state for a vocabulary word.
   * If currently favorited — removes it. If not — adds it.
   * Optimistically updates the local signal before the Firestore write.
   */
  async toggleFavorite(
    word: VocabularyItem,
    chapterId: string,
    bookId: string
  ): Promise<void> {
    const uid = this.auth.currentUser?.uid;
    if (!uid) return;

    const docId = favoriteDocId(chapterId, word.greek);
    const favRef = doc(this.firestore, 'users', uid, 'favoriteWords', docId);

    if (this.isFavorited(chapterId, word.greek)) {
      // Optimistic remove
      this._favorites.update(m => {
        const next = new Map(m);
        next.delete(docId);
        return next;
      });
      await deleteDoc(favRef);
    } else {
      // Optimistic add
      const newFav: FavoriteWord = {
        greek: word.greek,
        english: word.english,
        ...(word.audioUrl ? { audioUrl: word.audioUrl } : {}),
        chapterId,
        bookId,
        favoritedAt: serverTimestamp() as never,
      };
      this._favorites.update(m => {
        const next = new Map(m);
        next.set(docId, newFav);
        return next;
      });
      await setDoc(favRef, newFav);
    }
  }
}
