import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { of } from 'rxjs';
import { VocabularyPage } from './vocabulary.page';
import { LessonService } from '../../core/services/lesson.service';
import { AuthService } from '../../core/services/auth.service';
import { FavoriteWordsService } from '../../core/services/favorite-words.service';
import { OwnWordsService } from '../../core/services/own-words.service';
import { Storage } from '@angular/fire/storage';
import { Chapter, Book } from '../../core/models/firestore.models';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BOOK: Book = { id: 'book-1', title: 'Book One', description: '', order: 2, isActive: true };
const CHAPTER: Chapter = {
  id: 'ch-1',
  curriculumChapterId: 'c1',
  topic: 'Animals',
  bookId: 'book-1',
  title: 'Chapter One',
  order: 3,
  summary: '',
  grammarNotes: [],
  vocabulary: [{ greek: 'σκύλος', english: 'dog' }],
  exercises: [],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setup(opts: { ownWords?: { greek: string; english: string; chapterId: string; bookId: string }[] } = {}) {
  const mockLessonService = {
    getChaptersByIds: vi.fn().mockReturnValue(of([CHAPTER])),
    getBooks: vi.fn().mockReturnValue(of([BOOK])),
  };
  const mockAuthService = {
    currentUser: () => ({ progress: { completedChapterIds: ['ch-1'], xp: 0, currentBookId: '' } }),
  };
  const mockFavoriteWordsService = {
    ensureLoaded: vi.fn().mockResolvedValue(undefined),
    allFavorites: () => [],
    isFavorited: () => false,
  };
  const mockOwnWordsService = {
    ensureLoaded: vi.fn().mockResolvedValue(undefined),
    allOwnWords: () => opts.ownWords ?? [],
  };

  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: LessonService, useValue: mockLessonService },
      { provide: AuthService, useValue: mockAuthService },
      { provide: FavoriteWordsService, useValue: mockFavoriteWordsService },
      { provide: OwnWordsService, useValue: mockOwnWordsService },
      { provide: Storage, useValue: {} },
    ],
  });

  const fixture = TestBed.createComponent(VocabularyPage);
  return fixture;
}

// ---------------------------------------------------------------------------
// FE-02 — source badge must include the book, not just the chapter
// ---------------------------------------------------------------------------

describe('VocabularyPage — FE-02 source badge', () => {
  it('renders both the book order and chapter order in the flat-grid source badge', async () => {
    const fixture = setup();
    await fixture.componentInstance.ngOnInit();

    // Force the filtered flat-grid view (showSource = true) via a search query
    // matching our fixture word.
    fixture.componentInstance.searchQuery.set('σκύλος');
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Book 2');
    expect(text).toContain('Ch. 3');
  });

  it('populates bookOrder and chapterOrder distinctly on every row', async () => {
    const fixture = setup();
    await fixture.componentInstance.ngOnInit();

    const row = fixture.componentInstance.allRows().find(r => r.greek === 'σκύλος');
    expect(row?.bookOrder).toBe(2);
    expect(row?.chapterOrder).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// FE-07 — own-word dedup against chapter vocabulary
// ---------------------------------------------------------------------------

describe('VocabularyPage — FE-07 own-word dedup', () => {
  it('filters out an own word whose Greek text matches an existing chapter word (case-insensitive)', async () => {
    const fixture = setup({
      ownWords: [{ greek: 'ΣΚΎΛΟΣ', english: 'dog (custom)', chapterId: 'ch-1', bookId: 'book-1' }],
    });
    await fixture.componentInstance.ngOnInit();

    const matches = fixture.componentInstance.allRows().filter(r => r.greek.toLowerCase() === 'σκύλος');
    expect(matches.length).toBe(1);
    // The surviving row must be the chapter-sourced one, not the own-word duplicate.
    expect(matches[0].isOwnWord).toBeFalsy();
  });

  it('keeps an own word that does not duplicate any chapter vocabulary', async () => {
    const fixture = setup({
      ownWords: [{ greek: 'γάτα', english: 'cat', chapterId: 'ch-1', bookId: 'book-1' }],
    });
    await fixture.componentInstance.ngOnInit();

    const rows = fixture.componentInstance.allRows();
    expect(rows.some(r => r.greek === 'γάτα' && r.isOwnWord)).toBe(true);
    expect(rows.length).toBe(2); // chapter word + own word, no dedup false-positive
  });
});
