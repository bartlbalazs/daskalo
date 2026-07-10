import { Injectable, inject } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  doc,
  docData,
  documentId,
  query,
  orderBy,
  where,
  addDoc,
  serverTimestamp,
  getDocs,
} from '@angular/fire/firestore';
import { Auth } from '@angular/fire/auth';
import { Observable, combineLatest, from, of } from 'rxjs';
import { map, shareReplay } from 'rxjs/operators';
import { toObservable } from '@angular/core/rxjs-interop';
import { Chapter, Book, ExerciseAttempt, AttemptPayload, ExerciseType, EvaluationResult, PracticeSet } from '../models/firestore.models';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';
import { fetchWithTimeout } from '../utils/fetch-with-timeout';

@Injectable({ providedIn: 'root' })
export class LessonService {
  private firestore = inject(Firestore);
  private authService = inject(AuthService);
  private auth = inject(Auth);

  /** Cached books$ stream (IMP-FE-03) — LayoutComponent's sidebar and
   *  ChaptersPage both need the full books list; without caching, each
   *  independently opens its own realtime Firestore listener for identical
   *  data. `shareReplay({ bufferSize: 1, refCount: false })` means every
   *  caller shares one underlying listener and immediately gets the last
   *  emitted value on subscribe, and the listener is never torn down (the
   *  books list is small and cheap to keep hot for the app's lifetime). */
  private _books$: Observable<Book[]> | null = null;

  /** Cached chapters$ streams keyed by bookId, same rationale as _books$ above. */
  private readonly _chaptersByBook$ = new Map<string, Observable<Chapter[]>>();
  private _allChapters$: Observable<Chapter[]> | null = null;
  private readonly user$ = toObservable(this.authService.currentUser);

  /** Stream all active books ordered by their display order. */
  getBooks(): Observable<Book[]> {
    if (!this._books$) {
      const ref = collection(this.firestore, 'books');
      this._books$ = (collectionData(query(ref, orderBy('order')), { idField: 'id' }) as Observable<Book[]>).pipe(
        shareReplay({ bufferSize: 1, refCount: false })
      );
    }
    return this._books$;
  }

  /** Stream all chapters belonging to a given book. */
  getChaptersByBook(bookId: string): Observable<Chapter[]> {
    let chapters$ = this._chaptersByBook$.get(bookId);
    if (!chapters$) {
      const ref = collection(this.firestore, 'chapters');
      chapters$ = (collectionData(
        query(ref, where('bookId', '==', bookId), orderBy('order')),
        { idField: 'id' }
      ) as Observable<Chapter[]>).pipe(
        shareReplay({ bufferSize: 1, refCount: false })
      );
      this._chaptersByBook$.set(bookId, chapters$);
    }
    return chapters$;
  }

  /** Stream all chapters ordered locally. Used for curriculum alternative grouping. */
  getAllChapters(): Observable<Chapter[]> {
    if (!this._allChapters$) {
      const ref = collection(this.firestore, 'chapters');
      this._allChapters$ = (collectionData(ref, { idField: 'id' }) as Observable<Chapter[]>).pipe(
        map((chapters) => this.sortChapters(chapters)),
        shareReplay({ bufferSize: 1, refCount: false })
      );
    }
    return this._allChapters$;
  }

  /** Stream selected chapter variants for one book, with newest-selectable fallback. */
  getSelectedChaptersByBook(bookId: string): Observable<Chapter[]> {
    return combineLatest([this.getChaptersByBook(bookId), this.user$]).pipe(
      map(([chapters, user]) => this.selectedChapters(chapters, user?.curriculum?.selectedChapterIdsByCurriculumChapterId ?? {}))
    );
  }

  /** Stream alternatives for one curriculum slot. Hidden variants are excluded unless already selected. */
  getAlternativesForCurriculumChapter(curriculumChapterId: string): Observable<Chapter[]> {
    return combineLatest([this.getAllChapters(), this.user$]).pipe(
      map(([chapters, user]) => {
        const selectedId = user?.curriculum?.selectedChapterIdsByCurriculumChapterId?.[curriculumChapterId];
        return chapters
          .filter((chapter) =>
            chapter.curriculumChapterId === curriculumChapterId &&
            (chapter.isSelectableAlternative !== false || chapter.id === selectedId)
          )
          .sort((a, b) => this.alternativeSort(a, b, selectedId));
      })
    );
  }

  async setCurriculumSelection(curriculumChapterId: string, chapterId: string): Promise<void> {
    const userId = this.authService.firebaseUser()?.uid;
    if (!userId) throw new Error('User not authenticated.');

    const idToken = await this.auth.currentUser?.getIdToken();
    const response = await fetchWithTimeout(environment.setCurriculumSelectionUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      body: JSON.stringify({
        data: {
          curriculumChapterId,
          chapterId,
          ...(idToken ? { idToken } : {}),
        },
      }),
    });

    const body = await response.json();
    if (body.error) {
      throw new Error(body.error.message ?? 'Failed to update curriculum selection.');
    }

    await this.authService.loadCurrentUser();
  }

  /** Stream a single chapter document in real-time. */
  getChapter(chapterId: string): Observable<Chapter> {
    const ref = doc(this.firestore, 'chapters', chapterId);
    return docData(ref, { idField: 'id' }) as Observable<Chapter>;
  }

  /**
   * Fetch chapters by an array of IDs (e.g. all completed chapters for the vocabulary page).
   * Firestore `in` queries are limited to 30 items, so large arrays are batched automatically.
   */
  getChaptersByIds(ids: string[]): Observable<Chapter[]> {
    if (ids.length === 0) return of([]);

    const BATCH_SIZE = 30;
    const batches: string[][] = [];
    for (let i = 0; i < ids.length; i += BATCH_SIZE) {
      batches.push(ids.slice(i, i + BATCH_SIZE));
    }

    const ref = collection(this.firestore, 'chapters');
    const promises = batches.map(batch =>
      getDocs(query(ref, where(documentId(), 'in', batch)))
        .then(snap => snap.docs.map(d => ({ id: d.id, ...d.data() } as Chapter)))
    );

    return from(Promise.all(promises)).pipe(
      map(results => results.flat())
    );
  }

  /**
   * Submit an AI-graded exercise attempt:
   *   1. Write the attempt document to Firestore (records the attempt — no audio stored).
   *   2. Call the evaluate-attempt Cloud Function with the attempt ID and optional audioBase64.
   *   3. The function evaluates via STT + Gemini and writes the result back to Firestore.
   *   4. Returns the evaluation result directly to the caller.
   *
   * audioBase64 is sent ONLY in the HTTP request body and is NEVER written to Firestore.
   */
  async evaluateAttempt(
    chapterId: string,
    exerciseId: string,
    type: ExerciseType,
    payload: AttemptPayload & { audioBase64?: string }
  ): Promise<EvaluationResult> {
    const userId = this.authService.firebaseUser()?.uid;
    if (!userId) throw new Error('User not authenticated.');

    // Separate the audio from the Firestore payload — audio is never persisted.
    const { audioBase64, ...firestorePayload } = payload;

    // 1. Write attempt to Firestore (status tracking only, no audio)
    const attempt: Omit<ExerciseAttempt, 'evaluation'> & { evaluation: null } = {
      userId,
      chapterId,
      exerciseId,
      type,
      submittedAt: serverTimestamp() as never,
      payload: firestorePayload,
      status: 'pending',
      evaluation: null,
    };
    const ref = await addDoc(collection(this.firestore, 'exercise_attempts'), attempt);
    const attemptId = ref.id;

    // 2. Call the evaluate-attempt Cloud Function
    //    audioBase64 is included in the request body only (not in Firestore).
    const idToken = await this.auth.currentUser?.getIdToken();
    const requestData: Record<string, unknown> = { attemptId };
    if (audioBase64) requestData['audioBase64'] = audioBase64;
    // Also include the token in the body: the API Gateway replaces the
    // Authorization header with its own service-account JWT when proxying to
    // Cloud Run, so the backend reads the Firebase ID token from the body
    // instead (falls back to the header for local dev without a gateway).
    if (idToken) requestData['idToken'] = idToken;

    const response = await fetchWithTimeout(environment.evaluateAttemptUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      body: JSON.stringify({ data: requestData }),
    });

    const body = await response.json();

    // 3. Surface Callable errors
    if (body.error) {
      throw new Error(body.error.message ?? 'Evaluation failed.');
    }

    return body.result as EvaluationResult;
  }

  /**
   * Mark a chapter as complete by calling the complete-chapter Cloud Function.
   * The function generates a progress summary via Gemini and updates the user
   * document in Firestore (completedChapterIds, lastActive, lastProgressSummary).
   *
   * The grammar book is NOT generated here — each chapter document contains a
   * pre-generated grammarSummary field written by the content-cli pipeline.
   * The grammar book page assembles summaries from completed chapters at runtime.
   *
   * Blocks until the function responds (up to ~10s is acceptable per design).
   */
  async completeChapter(chapterId: string): Promise<{ xpGained: number }> {
    const userId = this.authService.firebaseUser()?.uid;
    if (!userId) throw new Error('User not authenticated.');

    const idToken = await this.auth.currentUser?.getIdToken();

    const response = await fetchWithTimeout(environment.completeChapterUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      // Include the token in the body: the API Gateway replaces the Authorization
      // header with its own JWT, so the backend reads the Firebase ID token from
      // the body (falls back to the header in local dev without a gateway).
      body: JSON.stringify({ data: { chapterId, ...(idToken ? { idToken } : {}) } }),
    });

    const body = await response.json();

    if (body.error) {
      throw new Error(body.error.message ?? 'Failed to complete chapter.');
    }

    // Refresh the local user profile so completedChapterIds is up-to-date
    // everywhere (sidebar, chapters list, vocabulary page) without a page reload.
    await this.authService.loadCurrentUser();

    return { xpGained: body.result.xpGained };
  }

  /** Stream a single practice set document in real-time. */
  getPracticeSet(practiceSetId: string): Observable<PracticeSet> {
    const ref = doc(this.firestore, 'practice_sets', practiceSetId);
    return docData(ref, { idField: 'id' }) as Observable<PracticeSet>;
  }

  /**
   * Mark a practice set as complete by calling the complete-practice Cloud Function.
   * Awards 175 XP (idempotent — safe to call multiple times).
   */
  async completePractice(practiceSetId: string): Promise<{ xpGained: number }> {
    const userId = this.authService.firebaseUser()?.uid;
    if (!userId) throw new Error('User not authenticated.');

    const idToken = await this.auth.currentUser?.getIdToken();

    const response = await fetchWithTimeout(environment.completePracticeUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      body: JSON.stringify({ data: { practiceSetId, ...(idToken ? { idToken } : {}) } }),
    });

    const body = await response.json();

    if (body.error) {
      throw new Error(body.error.message ?? 'Failed to complete practice set.');
    }

    await this.authService.loadCurrentUser();

    return { xpGained: body.result.xpGained };
  }

  private selectedChapters(chapters: Chapter[], selectedBySlot: Record<string, string>): Chapter[] {
    const groups = new Map<string, Chapter[]>();
    for (const chapter of chapters) {
      groups.set(chapter.curriculumChapterId, [...(groups.get(chapter.curriculumChapterId) ?? []), chapter]);
    }

    const selected: Chapter[] = [];
    for (const [slot, variants] of groups) {
      const selectedId = selectedBySlot[slot];
      const selectedVariant = variants.find((chapter) => chapter.id === selectedId);
      if (selectedVariant) {
        selected.push(selectedVariant);
        continue;
      }

      const newestSelectable = variants
        .filter((chapter) => chapter.isSelectableAlternative !== false)
        .sort((a, b) => this.newestFirst(a, b))[0];
      if (newestSelectable) selected.push(newestSelectable);
    }

    return this.sortChapters(selected);
  }

  private sortChapters(chapters: Chapter[]): Chapter[] {
    return [...chapters].sort((a, b) =>
      a.order - b.order || a.curriculumChapterId.localeCompare(b.curriculumChapterId) || a.id.localeCompare(b.id)
    );
  }

  private alternativeSort(a: Chapter, b: Chapter, selectedId?: string): number {
    if (a.id === selectedId) return -1;
    if (b.id === selectedId) return 1;
    return this.newestFirst(a, b);
  }

  private newestFirst(a: Chapter, b: Chapter): number {
    return this.generatedAtMs(b) - this.generatedAtMs(a) || b.id.localeCompare(a.id);
  }

  private generatedAtMs(chapter: Chapter): number {
    const generatedAt = chapter.generatedAt;
    if (!generatedAt) return Number.NEGATIVE_INFINITY;
    if (typeof generatedAt === 'object' && 'toMillis' in generatedAt) return generatedAt.toMillis();
    return Number.NEGATIVE_INFINITY;
  }
}
