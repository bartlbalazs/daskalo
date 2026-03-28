import { Component, computed, inject, signal, OnInit } from '@angular/core';
import { ViewportScroller } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NgTemplateOutlet } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { LessonService } from '../../core/services/lesson.service';
import { AuthService } from '../../core/services/auth.service';
import { FavoriteWordsService } from '../../core/services/favorite-words.service';
import { OwnWordsService } from '../../core/services/own-words.service';
import { VocabularyItem, Book, Chapter } from '../../core/models/firestore.models';
import { Storage, ref, getDownloadURL } from '@angular/fire/storage';

interface VocabRow extends VocabularyItem {
  chapterId: string;
  chapterTitle: string;
  chapterOrder: number;
  bookId: string;
  bookTitle: string;
  bookOrder: number;
  isOwnWord?: boolean;
}

interface ChapterGroup {
  chapter: Chapter;
  book: Book;
  words: VocabRow[];
}

interface BookGroup {
  book: Book;
  chapters: ChapterGroup[];
}

@Component({
  selector: 'app-vocabulary',
  standalone: true,
  imports: [RouterLink, NgTemplateOutlet],
  template: `
    <!-- Dashboard Header (Gamified Ribbon) -->
    <div class="w-full bg-gradient-to-b from-greek-700 to-greek-600 border-b border-greek-800 pb-10 pt-8 px-6">
      <div class="max-w-6xl mx-auto">
        <div class="flex items-center justify-between flex-wrap gap-4 mb-8">
          <div>
            <nav class="flex items-center gap-1.5 text-sm text-greek-200 mb-4">
              <a routerLink="/chapters" class="hover:text-white transition-colors">Course</a>
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
              </svg>
              <span class="text-white">Vocabulary</span>
            </nav>
            <h1 class="font-serif text-3xl md:text-4xl font-semibold text-white mb-2">My Vocabulary</h1>
            <p class="text-greek-100 text-sm md:text-base max-w-xl leading-relaxed">
              All the words you've learned so far. This list grows automatically as you complete chapters.
            </p>
          </div>
          
          <!-- Trophy Stats -->
          <div class="flex items-center gap-4 bg-white/10 rounded-2xl p-4 border border-white/20 backdrop-blur-sm shadow-inner">
            <div class="text-center px-4 border-r border-white/20">
              <p class="text-2xl font-bold text-white">{{ allRows().length }}</p>
              <p class="text-xs text-greek-200 uppercase tracking-wider font-semibold">Words</p>
            </div>
            <div class="text-center px-4 border-r border-white/20">
              <p class="text-2xl font-bold text-white">{{ completedChapters().length }}</p>
              <p class="text-xs text-greek-200 uppercase tracking-wider font-semibold">Mastered</p>
            </div>
            <div class="text-center px-4">
              <p class="text-2xl font-bold text-white">{{ favoriteWordsService.allFavorites().length }}</p>
              <p class="text-xs text-greek-200 uppercase tracking-wider font-semibold">Saved</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content Area -->
    <div class="px-6 py-10 max-w-6xl mx-auto">
      
      <!-- Search + Filter Bar -->
      <div class="mb-8 flex flex-col sm:flex-row gap-3 max-w-2xl mx-auto">
        <!-- Search input -->
        <div class="relative flex-1">
          <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            <svg class="w-5 h-5 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
          <input
            type="search"
            [value]="searchQuery()"
            (input)="searchQuery.set($any($event.target).value)"
            placeholder="Search Greek or English words..."
            class="w-full bg-white border border-surface-200 text-surface-900 rounded-2xl pl-11 pr-4 py-4 focus:outline-none focus:ring-2 focus:ring-greek-400 focus:border-transparent shadow-sm transition-shadow hover:shadow-md text-lg"
          />
          @if (searchQuery()) {
            <button (click)="searchQuery.set('')" class="absolute inset-y-0 right-0 pr-4 flex items-center text-surface-400 hover:text-surface-600">
               <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          }
        </div>

        <!-- Favorites filter toggle pill -->
        <button
          (click)="showFavoritesOnly.set(!showFavoritesOnly())"
          class="flex items-center gap-2 px-5 py-3 rounded-2xl border font-semibold text-sm transition-all shadow-sm shrink-0"
          [class]="showFavoritesOnly()
            ? 'bg-greek-600 border-greek-700 text-white shadow-md'
            : 'bg-white border-surface-200 text-surface-600 hover:border-greek-300 hover:text-greek-700'"
        >
          <svg class="w-4 h-4" [attr.fill]="showFavoritesOnly() ? 'currentColor' : 'none'" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
          </svg>
          Favorites
          @if (favoriteWordsService.allFavorites().length > 0) {
            <span class="rounded-full px-1.5 py-0.5 text-xs font-bold leading-none"
              [class]="showFavoritesOnly() ? 'bg-white/20 text-white' : 'bg-surface-100 text-surface-500'">
              {{ favoriteWordsService.allFavorites().length }}
            </span>
          }
        </button>
      </div>

      @if (loading()) {
        <!-- Loading Skeleton (Two Columns) -->
        <div class="flex flex-col lg:flex-row gap-10">
          <div class="lg:w-1/4 hidden lg:block animate-pulse">
             <div class="h-6 bg-surface-200 rounded w-1/2 mb-4"></div>
             <div class="h-4 bg-surface-100 rounded w-3/4 mb-2"></div>
             <div class="h-4 bg-surface-100 rounded w-2/3"></div>
          </div>
          <div class="lg:w-3/4 animate-pulse space-y-6">
            <div class="h-8 bg-surface-200 rounded w-1/3 mb-6"></div>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              @for (i of [1,2,3,4,5,6]; track i) {
                <div class="bg-white border border-surface-200 rounded-xl h-24"></div>
              }
            </div>
          </div>
        </div>
      } @else if (allRows().length === 0) {
        <!-- Empty State -->
        <div class="flex flex-col items-center justify-center py-16 text-center">
          <div class="w-20 h-20 rounded-3xl bg-surface-100 flex items-center justify-center mb-6 shadow-inner">
            <svg class="w-10 h-10 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"/>
            </svg>
          </div>
          <h2 class="font-serif text-2xl font-semibold text-surface-800 mb-3">Your vocabulary is empty</h2>
          <p class="text-surface-500 max-w-md mb-8">
            Complete chapters to automatically add new words to your personal dictionary.
          </p>
          <a routerLink="/chapters"
            class="px-6 py-3 rounded-xl bg-greek-600 text-white font-semibold hover:bg-greek-700 transition-all shadow-md hover:shadow-lg active:scale-95">
            Go to Chapters
          </a>
        </div>
      } @else if (searchQuery() || showFavoritesOnly()) {
        <!-- Filtered Results View (Flat Grid — search results OR favorites filter active) -->
        <div class="space-y-6">
          <div class="flex items-center justify-between border-b border-surface-200 pb-4">
            <h2 class="font-serif text-2xl font-semibold text-greek-900">
              @if (showFavoritesOnly() && !searchQuery()) { Favorites }
              @else if (searchQuery() && !showFavoritesOnly()) { Search Results }
              @else { Filtered Results }
            </h2>
            <p class="text-surface-500 font-medium">{{ filteredRows().length }} word{{ filteredRows().length === 1 ? '' : 's' }}</p>
          </div>
          
          @if (filteredRows().length === 0) {
            <div class="py-16 text-center">
              @if (showFavoritesOnly() && !searchQuery()) {
                <!-- Empty favorites state -->
                <div class="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mx-auto mb-4">
                  <svg class="w-8 h-8 text-surface-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                  </svg>
                </div>
                <p class="text-surface-600 text-lg font-medium mb-2">No favorite words yet</p>
                <p class="text-surface-400 text-sm max-w-sm mx-auto">
                  Tap the
                  <svg class="w-3.5 h-3.5 inline -mt-0.5 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                  </svg>
                  bookmark on any word card to save it here for focused practice.
                </p>
              } @else {
                <p class="text-surface-500 text-lg">No words found matching "<span class="font-semibold text-surface-800">{{ searchQuery() }}</span>"</p>
              }
            </div>
          } @else {
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              @for (word of filteredRows(); track word.greek) {
                <ng-container *ngTemplateOutlet="wordCard; context: { $implicit: word, showSource: true }"></ng-container>
              }
            </div>
          }
        </div>
      } @else {
        <!-- Default View (Grouped by Book/Chapter with Sidebar) -->
        <div class="flex flex-col lg:flex-row gap-10 items-start">
          
          <!-- Left Sidebar (Table of Contents) -->
          <aside class="w-full lg:w-1/4 lg:sticky lg:top-8 bg-white border border-surface-200 rounded-2xl p-5 shadow-sm hidden md:block">
            <h3 class="font-serif text-lg font-semibold text-greek-900 mb-4 border-b border-surface-100 pb-3">Chapters</h3>
            <div class="space-y-6 max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
              @for (bookGroup of groupedVocab(); track bookGroup.book.id) {
                <div>
                  <h4 class="font-bold text-surface-400 text-xs uppercase tracking-widest mb-3">{{ bookGroup.book.title }}</h4>
                  <ul class="space-y-1 border-l-2 border-surface-100 ml-1.5 pl-3">
                    @for (chapterGroup of bookGroup.chapters; track chapterGroup.chapter.id) {
                      <li>
                        <button (click)="scrollTo(chapterGroup.chapter.id)"
                           class="text-left text-sm font-medium text-surface-600 hover:text-greek-600 transition-colors w-full truncate leading-tight py-1.5 px-2 rounded-lg hover:bg-surface-50 focus:outline-none focus:bg-surface-50 flex justify-between items-center group">
                          <span class="truncate">{{ chapterGroup.chapter.order }}. {{ chapterGroup.chapter.title }}</span>
                          <span class="text-xs text-surface-300 group-hover:text-greek-400 font-normal shrink-0 ml-2">{{ chapterGroup.words.length }}</span>
                        </button>
                      </li>
                    }
                  </ul>
                </div>
              }
            </div>
          </aside>

          <!-- Right Content Area (Grouped Lists) -->
          <main class="w-full lg:w-3/4 space-y-16">
            @for (bookGroup of groupedVocab(); track bookGroup.book.id) {
              <div class="space-y-12">
                <!-- Book heading separator -->
                <div class="flex items-center gap-4">
                  <div class="flex-1 h-px bg-surface-200"></div>
                  <h2 class="font-serif text-xl font-bold text-surface-400 uppercase tracking-widest">{{ bookGroup.book.title }}</h2>
                  <div class="flex-1 h-px bg-surface-200"></div>
                </div>

                @for (chapterGroup of bookGroup.chapters; track chapterGroup.chapter.id) {
                  <article [id]="chapterGroup.chapter.id" class="scroll-mt-8">
                    <!-- Chapter Header -->
                    <div class="flex items-end justify-between mb-6 border-b border-surface-200 pb-3">
                      <div>
                        <span class="text-xs font-bold uppercase tracking-widest text-greek-600 mb-1 block">Chapter {{ chapterGroup.chapter.order }}</span>
                        <h3 class="font-serif text-2xl font-semibold text-greek-900 m-0">{{ chapterGroup.chapter.title }}</h3>
                      </div>
                      <span class="text-sm font-medium text-surface-400 mb-1">{{ chapterGroup.words.length }} words</span>
                    </div>
                    
                    <!-- Words Grid -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      @for (word of chapterGroup.words; track word.greek) {
                        <ng-container *ngTemplateOutlet="wordCard; context: { $implicit: word, showSource: false }"></ng-container>
                      }
                    </div>
                  </article>
                }
              </div>
            }
          </main>
        </div>
      }
    </div>

    <!-- Reusable Word Card Template -->
    <ng-template #wordCard let-word let-showSource="showSource">
      <div class="group bg-white border border-surface-200 rounded-2xl p-5 hover:border-greek-300 hover:shadow-md transition-all duration-200 flex flex-col h-full relative">
        <!-- Own-word pencil badge (top-left corner) -->
        @if (word.isOwnWord) {
          <div class="absolute top-2.5 left-2.5 w-5 h-5 rounded-full bg-greek-100 flex items-center justify-center" title="Your own word">
            <svg class="w-3 h-3 text-greek-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
            </svg>
          </div>
        }
        <div class="flex items-start justify-between gap-3 mb-2">
          <div class="min-w-0 flex-1">
            <p class="font-serif text-2xl font-semibold text-greek-900 leading-tight mb-1 truncate">{{ word.greek }}</p>
            <p class="text-surface-600 text-sm leading-snug">{{ word.english }}</p>
          </div>
          <!-- Action buttons: bookmark + audio -->
          <div class="flex items-center gap-1 shrink-0">
            <!-- Bookmark (favorite) toggle -->
            <button
              (click)="favoriteWordsService.toggleFavorite(word, word.chapterId, word.bookId)"
              class="w-10 h-10 rounded-full flex items-center justify-center transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-greek-500"
              [class]="favoriteWordsService.isFavorited(word.chapterId, word.greek)
                ? 'text-greek-600 bg-greek-100 hover:bg-greek-200'
                : 'text-surface-300 hover:text-greek-500 hover:bg-greek-50'"
              [title]="favoriteWordsService.isFavorited(word.chapterId, word.greek) ? 'Remove from favorites' : 'Save to favorites'"
            >
              @if (favoriteWordsService.isFavorited(word.chapterId, word.greek)) {
                <!-- Filled bookmark -->
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 2a2 2 0 00-2 2v18l8-3 8 3V4a2 2 0 00-2-2H6z"/>
                </svg>
              } @else {
                <!-- Outline bookmark -->
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                </svg>
              }
            </button>
            <!-- Audio play button -->
            @if (word.audioUrl) {
              <button
                (click)="playAudio(word.audioUrl, word.greek)"
                class="w-10 h-10 rounded-full bg-greek-50 text-greek-600 flex items-center justify-center hover:bg-greek-600 hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-greek-500"
                title="Listen to pronunciation"
                [disabled]="playingWord() === word.greek"
                [class.opacity-80]="playingWord() === word.greek"
              >
                @if (playingWord() === word.greek) {
                  <svg class="w-5 h-5 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/>
                  </svg>
                } @else {
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0-12L8.464 9.536M12 6l3.536 3.536M8.464 14.464A5 5 0 018.464 9.536M5.05 18.364A9 9 0 015.05 5.636"/>
                  </svg>
                }
              </button>
            }
          </div>
        </div>
        
        <div class="mt-auto pt-3">
           @if (showSource) {
             <div class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface-100 text-surface-500">
               Ch. {{ word.chapterOrder }}
             </div>
           }
        </div>
      </div>
    </ng-template>
  `,
  styles: [`
    /* Custom scrollbar for the TOC */
    .custom-scrollbar::-webkit-scrollbar {
      width: 4px;
    }
    .custom-scrollbar::-webkit-scrollbar-track {
      background: #f1f3f7;
      border-radius: 4px;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
      background: #cdd3df;
      border-radius: 4px;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
      background: #9aa3b5;
    }
  `]
})
export class VocabularyPage implements OnInit {
  private lessonService = inject(LessonService);
  private authService = inject(AuthService);
  readonly favoriteWordsService = inject(FavoriteWordsService);
  readonly ownWordsService = inject(OwnWordsService);
  private scroller = inject(ViewportScroller);
  private storage = inject(Storage);

  searchQuery = signal('');
  showFavoritesOnly = signal(false);
  loading = signal(true);
  playingWord = signal<string | null>(null);

  allRows = signal<VocabRow[]>([]);
  completedChapters = signal<Chapter[]>([]);

  // ---------------------------------------------------------------------------
  // Computed: filtered flat list (used for search / favorites filter views)
  // ---------------------------------------------------------------------------

  filteredRows = computed<VocabRow[]>(() => {
    const q = this.searchQuery().toLowerCase().trim();
    const favoritesOnly = this.showFavoritesOnly();
    let rows = this.allRows();

    if (favoritesOnly) {
      rows = rows.filter(r => this.favoriteWordsService.isFavorited(r.chapterId, r.greek));
    }

    if (q) {
      rows = rows.filter(
        r => r.greek.toLowerCase().includes(q) || r.english.toLowerCase().includes(q)
      );
    }

    return rows;
  });

  // ---------------------------------------------------------------------------
  // Computed: grouped list for the default (no filter, no search) view
  // ---------------------------------------------------------------------------

  groupedVocab = computed<BookGroup[]>(() => {
    const rows = this.allRows();
    if (rows.length === 0) return [];

    // Group by Book
    const bookMap = new Map<string, BookGroup>();
    
    for (const row of rows) {
      if (!bookMap.has(row.bookId)) {
        bookMap.set(row.bookId, {
          book: { id: row.bookId, title: row.bookTitle, order: row.bookOrder } as Book,
          chapters: []
        });
      }
      
      const bookGroup = bookMap.get(row.bookId)!;
      
      // Group by Chapter within Book
      let chapterGroup = bookGroup.chapters.find(c => c.chapter.id === row.chapterId);
      if (!chapterGroup) {
        chapterGroup = {
          chapter: { id: row.chapterId, title: row.chapterTitle, order: row.chapterOrder } as Chapter,
          book: bookGroup.book,
          words: []
        };
        bookGroup.chapters.push(chapterGroup);
      }
      
      chapterGroup.words.push(row);
    }

    // Sort Books
    const sortedBooks = Array.from(bookMap.values()).sort((a, b) => a.book.order - b.book.order);
    
    // Sort Chapters within Books, and words alphabetically within chapters
    for (const book of sortedBooks) {
      book.chapters.sort((a, b) => a.chapter.order - b.chapter.order);
      for (const chap of book.chapters) {
        chap.words.sort((a, b) => a.greek.localeCompare(b.greek, 'el'));
      }
    }

    return sortedBooks;
  });

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------

  async ngOnInit(): Promise<void> {
    // Load favorites in parallel with vocabulary data
    const completedIds = this.authService.currentUser()?.progress?.completedChapterIds ?? [];

    const favoritesPromise = this.favoriteWordsService.ensureLoaded();
    const ownWordsPromise = this.ownWordsService.ensureLoaded();

    if (completedIds.length === 0) {
      await Promise.all([favoritesPromise, ownWordsPromise]);
      // Still merge own words even if no chapters are completed
      this._mergeOwnWords([], new Map(), new Map());
      this.loading.set(false);
      return;
    }

    try {
      // Own words load independently — a failure should not prevent chapter vocab from rendering.
      await ownWordsPromise.catch(err =>
        console.error('[VocabularyPage] Own words failed to load:', err)
      );

      const [chapters, books] = await Promise.all([
        firstValueFrom(this.lessonService.getChaptersByIds(completedIds)),
        firstValueFrom(this.lessonService.getBooks()),
        favoritesPromise,
      ]);

      this.completedChapters.set(chapters ?? []);
      const bookMap = new Map(books?.map(b => [b.id, b]) ?? []);
      const chapterMap = new Map((chapters ?? []).map(c => [c.id, c]));

      const seen = new Set<string>();
      const rows: VocabRow[] = [];

      for (const chapter of (chapters ?? [])) {
        const book = bookMap.get(chapter.bookId);
        if (!book) continue;

        for (const item of chapter.vocabulary ?? []) {
          const key = item.greek.toLowerCase();
          if (!seen.has(key)) {
            seen.add(key);
            rows.push({ 
              ...item, 
              chapterId: chapter.id,
              chapterTitle: chapter.title,
              chapterOrder: chapter.order,
              bookId: book.id,
              bookTitle: book.title,
              bookOrder: book.order
            });
          }
        }
      }

      this._mergeOwnWords(rows, chapterMap, bookMap);
      
    } catch (err) {
      console.error("Failed to load vocabulary:", err);
    } finally {
      this.loading.set(false);
    }
  }

  /** Merge own words into the rows array and set allRows signal. */
  private _mergeOwnWords(
    chapterRows: VocabRow[],
    chapterMap: Map<string, Chapter>,
    bookMap: Map<string, Book>
  ): void {
    const seen = new Set<string>(chapterRows.map(r => r.greek.toLowerCase()));
    const ownRows: VocabRow[] = this.ownWordsService.allOwnWords().map(w => {
      const chapter = chapterMap.get(w.chapterId);
      const book = bookMap.get(w.bookId);
      return {
        greek: w.greek,
        english: w.english,
        ...(w.audioUrl ? { audioUrl: w.audioUrl } : {}),
        chapterId: w.chapterId,
        chapterTitle: chapter?.title ?? 'My Words',
        chapterOrder: chapter?.order ?? 9999,
        bookId: w.bookId,
        bookTitle: book?.title ?? 'My Words',
        bookOrder: book?.order ?? 9999,
        isOwnWord: true,
      };
    });

    // Deduplicate own words by greek (in case of near-duplicates across chapters)
    const ownDeduped = ownRows.filter(r => {
      const key = `own__${r.greek.toLowerCase()}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    const rows = [...chapterRows, ...ownDeduped];
    // Sort full list alphabetically by Greek
    rows.sort((a, b) => a.greek.localeCompare(b.greek, 'el'));
    this.allRows.set(rows);
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  scrollTo(id: string): void {
    this.scroller.scrollToAnchor(id);
  }

  playAudio(url: string, word?: string): void {
    if (word) this.playingWord.set(word);

    const play = (resolvedUrl: string) => {
      const audio = new Audio(resolvedUrl);
      audio.play();
      audio.onended = () => {
        if (word) this.playingWord.set(null);
      };
      audio.onerror = () => {
        if (word) this.playingWord.set(null);
      };
    };

    if (url.startsWith('gs://')) {
      getDownloadURL(ref(this.storage, url))
        .then(play)
        .catch(() => {
          if (word) this.playingWord.set(null);
        });
    } else {
      play(url);
    }
  }
}
