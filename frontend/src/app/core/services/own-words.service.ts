import { Injectable, inject, signal, computed } from '@angular/core';
import {
  Firestore,
  collection,
  getDocs,
} from '@angular/fire/firestore';
import { Auth } from '@angular/fire/auth';
import { OwnWord } from '../models/firestore.models';
import { environment } from '../../../environments/environment';

/** Response payload returned by the add-own-word Cloud Function. */
interface AddOwnWordResult {
  greek: string;
  english: string;
  audioUrl?: string;
  chapterId: string;
  bookId: string;
  docId: string;
  alreadyExisted: boolean;
}

@Injectable({ providedIn: 'root' })
export class OwnWordsService {
  private firestore = inject(Firestore);
  private auth = inject(Auth);

  /** Map of docId → OwnWord, populated by loadOwnWords(). */
  private _ownWords = signal<Map<string, OwnWord>>(new Map());

  /** True when the service has performed its initial load. */
  private _loaded = false;

  // ---------------------------------------------------------------------------
  // Queries
  // ---------------------------------------------------------------------------

  /** Flat array of all own words, sorted alphabetically by Greek. */
  allOwnWords = computed<OwnWord[]>(() =>
    Array.from(this._ownWords().values()).sort((a, b) =>
      a.greek.localeCompare(b.greek, 'el')
    )
  );

  /** Own words for a specific chapter, sorted alphabetically. */
  ownWordsForChapter(chapterId: string): OwnWord[] {
    return Array.from(this._ownWords().values())
      .filter(w => w.chapterId === chapterId)
      .sort((a, b) => a.greek.localeCompare(b.greek, 'el'));
  }

  // ---------------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------------

  /**
   * Load all own words for the current user from Firestore into the local signal.
   * Safe to call multiple times — subsequent calls refresh the data.
   */
  async loadOwnWords(): Promise<void> {
    const uid = this.auth.currentUser?.uid;
    if (!uid) {
      console.warn('[OwnWordsService] loadOwnWords called with no authenticated user.');
      return;
    }

    try {
      const ref = collection(this.firestore, 'users', uid, 'ownWords');
      const snap = await getDocs(ref);
      const map = new Map<string, OwnWord>();
      for (const d of snap.docs) {
        map.set(d.id, d.data() as OwnWord);
      }
      this._ownWords.set(map);
      this._loaded = true;
    } catch (err) {
      this._loaded = true; // prevent retry loops; signal stays with existing data
    }
  }

  /** Load own words once (no-op on subsequent calls unless force=true). */
  async ensureLoaded(force = false): Promise<void> {
    if (!this._loaded || force) {
      await this.loadOwnWords();
    }
  }

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  /**
   * Submit a new own word to the Cloud Function.
   * The function normalizes it via Gemini, generates TTS audio, writes to
   * Firestore, and returns the stored document.
   * Optimistically adds the result to the local signal on success.
   */
  async addOwnWord(text: string, chapterId: string, bookId: string): Promise<AddOwnWordResult> {
    const user = this.auth.currentUser;
    if (!user) throw new Error('User not authenticated.');

    const idToken = await user.getIdToken();

    const response = await fetch(environment.addOwnWordUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      body: JSON.stringify({
        data: {
          text,
          chapterId,
          bookId,
          ...(idToken ? { idToken } : {}),
        },
      }),
    });

    const body = await response.json();

    if (body.error) {
      throw new Error(body.error.message ?? 'Failed to add word.');
    }

    const result = body.result as AddOwnWordResult;

    // Add to local signal (optimistic — backend already wrote to Firestore)
    const newWord: OwnWord = {
      greek: result.greek,
      english: result.english,
      ...(result.audioUrl ? { audioUrl: result.audioUrl } : {}),
      chapterId: result.chapterId,
      bookId: result.bookId,
      createdAt: null as never, // server timestamp, not needed locally
    };
    this._ownWords.update(m => {
      const next = new Map(m);
      next.set(result.docId, newWord);
      return next;
    });

    return result;
  }
}
