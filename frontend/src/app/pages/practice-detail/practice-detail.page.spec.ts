import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { vi } from 'vitest';
import { BehaviorSubject, of } from 'rxjs';
import { PracticeDetailPage } from './practice-detail.page';
import { LessonService } from '../../core/services/lesson.service';
import { AuthService } from '../../core/services/auth.service';
import { PracticeSet, Chapter } from '../../core/models/firestore.models';

// ---------------------------------------------------------------------------
// FE-04 — per-attempt state must reset when navigating between practice sets
// ---------------------------------------------------------------------------

describe('PracticeDetailPage — FE-04 route-change state reset', () => {
  function makePracticeSet(id: string): PracticeSet {
    return { id, chapterId: 'ch-1', title: `Practice ${id}`, exercises: [] };
  }

  it('resets answeredMap, practiceCompleted, completeError and earnedXp when the :id param changes', () => {
    const paramMapSubject = new BehaviorSubject(convertToParamMap({ id: 'ps-1' }));

    const mockLessonService = {
      getPracticeSet: vi.fn((id: string) => of(makePracticeSet(id))),
      getChapter: vi.fn().mockReturnValue(of({ id: 'ch-1', bookId: 'book-1' } as Chapter)),
    };
    const mockAuthService = {
      currentUser: () => ({ progress: { completedPracticeSetIds: [] as string[] } }),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: ActivatedRoute, useValue: { paramMap: paramMapSubject.asObservable() } },
        { provide: LessonService, useValue: mockLessonService },
        { provide: AuthService, useValue: mockAuthService },
      ],
    });

    const fixture = TestBed.createComponent(PracticeDetailPage);
    const page = fixture.componentInstance;

    // Simulate the student having answered an exercise, seen a completion
    // screen and an error, while viewing practice set "ps-1".
    page.answeredMap.set(new Map([[0, true]]));
    page.practiceCompleted.set(true);
    page.completeError.set('Something went wrong');
    page.earnedXp.set(300);

    expect(page.practiceSet()?.id).toBe('ps-1');

    // Navigate to a different practice set.
    paramMapSubject.next(convertToParamMap({ id: 'ps-2' }));

    expect(page.practiceSet()?.id).toBe('ps-2');
    expect(page.answeredMap().size).toBe(0);
    expect(page.practiceCompleted()).toBe(false);
    expect(page.completeError()).toBeNull();
    expect(page.earnedXp()).toBe(175);
  });

  it('does not carry over stale answeredMap entries across three consecutive navigations', () => {
    const paramMapSubject = new BehaviorSubject(convertToParamMap({ id: 'ps-a' }));

    const mockLessonService = {
      getPracticeSet: vi.fn((id: string) => of(makePracticeSet(id))),
      getChapter: vi.fn().mockReturnValue(of({ id: 'ch-1', bookId: 'book-1' } as Chapter)),
    };
    const mockAuthService = {
      currentUser: () => ({ progress: { completedPracticeSetIds: [] as string[] } }),
    };

    TestBed.configureTestingModule({
      providers: [
        { provide: ActivatedRoute, useValue: { paramMap: paramMapSubject.asObservable() } },
        { provide: LessonService, useValue: mockLessonService },
        { provide: AuthService, useValue: mockAuthService },
      ],
    });

    const fixture = TestBed.createComponent(PracticeDetailPage);
    const page = fixture.componentInstance;

    page.onExerciseAnswered({ index: 0, correct: true });
    expect(page.answeredMap().size).toBe(1);

    paramMapSubject.next(convertToParamMap({ id: 'ps-b' }));
    expect(page.answeredMap().size).toBe(0);

    page.onExerciseAnswered({ index: 0, correct: false });
    page.onExerciseAnswered({ index: 1, correct: true });
    expect(page.answeredMap().size).toBe(2);

    paramMapSubject.next(convertToParamMap({ id: 'ps-c' }));
    expect(page.answeredMap().size).toBe(0);
  });
});
