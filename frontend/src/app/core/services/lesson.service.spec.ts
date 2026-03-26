import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { LessonService } from './lesson.service';
import { AuthService } from './auth.service';
import { Firestore } from '@angular/fire/firestore';
import { Auth } from '@angular/fire/auth';
import { signal } from '@angular/core';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

/** Minimal stub so Firestore injection token resolves without a real app. */
const mockFirestore = {} as Firestore;

/** Minimal stub for Firebase Auth. currentUser provides getIdToken(). */
const mockAuth = {
  currentUser: { getIdToken: vi.fn().mockResolvedValue('fake-id-token') },
} as unknown as Auth;

/** Stub AuthService — provides a signed-in user signal. */
function makeMockAuthService(uid = 'user-123') {
  return {
    firebaseUser: signal({ uid }),
    loadCurrentUser: vi.fn().mockResolvedValue(undefined),
  };
}

/** Mock addDoc: captures the written attempt and returns a ref with an id. */
const mockAddDoc = vi.fn().mockResolvedValue({ id: 'attempt-abc' });

vi.mock('@angular/fire/firestore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@angular/fire/firestore')>();
  return {
    ...actual,
    addDoc: (...args: unknown[]) => mockAddDoc(...args),
    collection: vi.fn().mockReturnValue({}),
    collectionData: vi.fn().mockReturnValue({ pipe: vi.fn() }),
    doc: vi.fn().mockReturnValue({}),
    docData: vi.fn().mockReturnValue({ pipe: vi.fn() }),
    getDocs: vi.fn().mockResolvedValue({ docs: [] }),
    query: vi.fn().mockReturnValue({}),
    orderBy: vi.fn(),
    where: vi.fn(),
    documentId: vi.fn(),
    serverTimestamp: vi.fn().mockReturnValue('SERVER_TS'),
  };
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LessonService', () => {
  let service: LessonService;
  let mockAuthService: ReturnType<typeof makeMockAuthService>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockAddDoc.mockResolvedValue({ id: 'attempt-abc' });
    mockAuthService = makeMockAuthService();

    TestBed.configureTestingModule({
      providers: [
        LessonService,
        { provide: Firestore, useValue: mockFirestore },
        { provide: Auth, useValue: mockAuth },
        { provide: AuthService, useValue: mockAuthService },
      ],
    });
    service = TestBed.inject(LessonService);
  });

  // -------------------------------------------------------------------------
  // evaluateAttempt — happy path
  // -------------------------------------------------------------------------

  it('calls evaluate endpoint and returns the evaluation result', async () => {
    const fakeResult = { score: 88, feedback: 'Great!', isCorrect: true };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: vi.fn().mockResolvedValue({ result: fakeResult }),
      })
    );

    const result = await service.evaluateAttempt('ch-1', 'ex_0', 'translation_challenge', {
      text: 'Γεια σου',
    });

    expect(result).toEqual(fakeResult);
    expect(fetch).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // evaluateAttempt — audioBase64 is NOT written to Firestore
  // -------------------------------------------------------------------------

  it('strips audioBase64 from the Firestore payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: vi.fn().mockResolvedValue({ result: { score: 70, feedback: 'OK', isCorrect: false } }),
      })
    );

    await service.evaluateAttempt('ch-1', 'ex_0', 'pronunciation_practice', {
      audioBase64: 'c29tZWF1ZGlv',
    } as never);

    // First arg to addDoc is the collection ref; second is the document data.
    const writtenDoc = mockAddDoc.mock.calls[0][1];
    expect(writtenDoc).not.toHaveProperty('audioBase64');
    expect(writtenDoc.payload).not.toHaveProperty('audioBase64');
  });

  // -------------------------------------------------------------------------
  // evaluateAttempt — audioBase64 IS included in the HTTP request body
  // -------------------------------------------------------------------------

  it('includes audioBase64 in the HTTP request body when present', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({ result: { score: 70, feedback: 'OK', isCorrect: false } }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await service.evaluateAttempt('ch-1', 'ex_0', 'pronunciation_practice', {
      audioBase64: 'c29tZWF1ZGlv',
    } as never);

    const callArgs = fetchMock.mock.calls[0];
    const requestBody = JSON.parse(callArgs[1].body as string);
    expect(requestBody.data.audioBase64).toBe('c29tZWF1ZGlv');
    expect(requestBody.data.attemptId).toBe('attempt-abc');
  });

  // -------------------------------------------------------------------------
  // evaluateAttempt — unauthenticated throws
  // -------------------------------------------------------------------------

  it('throws when user is not authenticated', async () => {
    // Override the auth service to return no user
    const unauthService = { ...mockAuthService, firebaseUser: signal(null) };
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        LessonService,
        { provide: Firestore, useValue: mockFirestore },
        { provide: Auth, useValue: mockAuth },
        { provide: AuthService, useValue: unauthService },
      ],
    });
    const unauthLessonService = TestBed.inject(LessonService);

    await expect(
      unauthLessonService.evaluateAttempt('ch-1', 'ex_0', 'translation_challenge', { text: 'hi' })
    ).rejects.toThrow('not authenticated');
  });

  // -------------------------------------------------------------------------
  // evaluateAttempt — surfaces callable error from backend
  // -------------------------------------------------------------------------

  it('throws when the backend returns a callable error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: vi.fn().mockResolvedValue({ error: { status: 'INTERNAL', message: 'Something failed.' } }),
      })
    );

    await expect(
      service.evaluateAttempt('ch-1', 'ex_0', 'translation_challenge', { text: 'hi' })
    ).rejects.toThrow('Something failed.');
  });

  // -------------------------------------------------------------------------
  // completeChapter — happy path
  // -------------------------------------------------------------------------

  it('completeChapter calls the endpoint and refreshes the user profile', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: vi.fn().mockResolvedValue({ result: { xpGained: 50 } }),
      })
    );

    const result = await service.completeChapter('ch-1');

    expect(result.xpGained).toBe(50);
    expect(mockAuthService.loadCurrentUser).toHaveBeenCalledOnce();
  });
});
