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
import { Observable, from, of } from 'rxjs';
import { map } from 'rxjs/operators';
import { Chapter, Book, ExerciseAttempt, AttemptPayload, ExerciseType, EvaluationResult } from '../models/firestore.models';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class LessonService {
  private firestore = inject(Firestore);
  private authService = inject(AuthService);
  private auth = inject(Auth);

  /** Stream all active books ordered by their display order. */
  getBooks(): Observable<Book[]> {
    const ref = collection(this.firestore, 'books');
    return collectionData(query(ref, orderBy('order')), { idField: 'id' }) as Observable<Book[]>;
  }

  /** Stream all chapters belonging to a given book. */
  getChaptersByBook(bookId: string): Observable<Chapter[]> {
    const ref = collection(this.firestore, 'chapters');
    return collectionData(
      query(ref, where('bookId', '==', bookId), orderBy('order')),
      { idField: 'id' }
    ) as Observable<Chapter[]>;
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

    const response = await fetch(environment.evaluateAttemptUrl, {
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

    const response = await fetch(environment.completeChapterUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      body: JSON.stringify({ data: { chapterId } }),
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
}
