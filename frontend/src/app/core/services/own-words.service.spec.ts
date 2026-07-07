import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { OwnWordsService } from './own-words.service';
import { Firestore } from '@angular/fire/firestore';
import { Auth } from '@angular/fire/auth';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

/** Minimal stub so Firestore injection token resolves without a real app. */
const mockFirestore = {} as Firestore;

/** Minimal stub for Firebase Auth. currentUser provides getIdToken(). */
const mockAuth = {
  currentUser: { uid: 'user-123', getIdToken: vi.fn().mockResolvedValue('fake-id-token') },
} as unknown as Auth;

const { mockGetDocs } = vi.hoisted(() => ({
  mockGetDocs: vi.fn().mockResolvedValue({ docs: [] }),
}));

vi.mock('@angular/fire/firestore', () => ({
  Firestore: class MockFirestoreToken {},
  collection: vi.fn().mockReturnValue({}),
  getDocs: (...args: unknown[]) => mockGetDocs(...args),
}));

/** Builds a resolved-`fetch` response that passes the `response.ok` check
 *  added for IMP-FE-05. */
function okResponse(body: unknown, status = 200) {
  return { ok: true, status, statusText: 'OK', json: vi.fn().mockResolvedValue(body) };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OwnWordsService', () => {
  let service: OwnWordsService;

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetDocs.mockResolvedValue({ docs: [] });

    TestBed.configureTestingModule({
      providers: [
        OwnWordsService,
        { provide: Firestore, useValue: mockFirestore },
        { provide: Auth, useValue: mockAuth },
      ],
    });
    service = TestBed.inject(OwnWordsService);
  });

  // -------------------------------------------------------------------------
  // addOwnWord — happy path
  // -------------------------------------------------------------------------

  it('calls the add-own-word endpoint and returns the result', async () => {
    const fakeResult = {
      greek: 'σκύλος',
      english: 'dog',
      audioUrl: 'gs://bucket/audio.mp3',
      chapterId: 'ch-1',
      bookId: 'book-1',
      docId: 'word-abc',
      alreadyExisted: false,
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse({ result: fakeResult })));

    const result = await service.addOwnWord('σκύλος', 'ch-1', 'book-1');

    expect(result).toEqual(fakeResult);
    expect(fetch).toHaveBeenCalledOnce();
    expect(service.allOwnWords()).toContainEqual(
      expect.objectContaining({ greek: 'σκύλος', english: 'dog' })
    );
  });

  // -------------------------------------------------------------------------
  // addOwnWord — unauthenticated throws
  // -------------------------------------------------------------------------

  it('throws when user is not authenticated', async () => {
    const unauthAuth = { currentUser: null } as unknown as Auth;
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        OwnWordsService,
        { provide: Firestore, useValue: mockFirestore },
        { provide: Auth, useValue: unauthAuth },
      ],
    });
    const unauthService = TestBed.inject(OwnWordsService);

    await expect(unauthService.addOwnWord('γεια', 'ch-1', 'book-1')).rejects.toThrow(
      'not authenticated'
    );
  });

  // -------------------------------------------------------------------------
  // addOwnWord — surfaces callable error from backend
  // -------------------------------------------------------------------------

  it('throws when the backend returns a callable error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(okResponse({ error: { status: 'INVALID_ARGUMENT', message: 'Bad word.' } }))
    );

    await expect(service.addOwnWord('???', 'ch-1', 'book-1')).rejects.toThrow('Bad word.');
  });

  // -------------------------------------------------------------------------
  // addOwnWord — fetch reliability (IMP-FE-05)
  // -------------------------------------------------------------------------

  it('throws a clear, status-coded error when the response is not ok', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        json: vi.fn().mockResolvedValue({}),
      })
    );

    await expect(service.addOwnWord('γεια', 'ch-1', 'book-1')).rejects.toThrow(/503/);
  });

  it('aborts and throws a clear error when the request exceeds the timeout', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            const abortError = new Error('The operation was aborted.');
            abortError.name = 'AbortError';
            reject(abortError);
          });
        });
      })
    );

    const pending = service.addOwnWord('γεια', 'ch-1', 'book-1');
    pending.catch(() => {});

    await vi.advanceTimersByTimeAsync(30_000);

    await expect(pending).rejects.toThrow(/timed out/i);

    vi.useRealTimers();
  });
});
