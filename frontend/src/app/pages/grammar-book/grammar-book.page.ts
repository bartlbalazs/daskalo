import { Component, inject, computed, OnInit, signal } from '@angular/core';
import { ViewportScroller } from '@angular/common';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { LessonService } from '../../core/services/lesson.service';
import { Book, Chapter } from '../../core/models/firestore.models';
import { marked } from 'marked';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

interface BookGroup {
  book: Book;
  chapters: Chapter[];
}

@Component({
  selector: 'app-grammar-book',
  standalone: true,
  imports: [RouterLink],
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
              <span class="text-white">Grammar Dashboard</span>
            </nav>
            <h1 class="font-serif text-3xl md:text-4xl font-semibold text-white mb-2">My Grammar Book</h1>
            <p class="text-greek-100 text-sm md:text-base max-w-xl leading-relaxed">
              Your personal language reference. This library grows automatically as you master new chapters.
            </p>
          </div>
          
          <!-- Trophy Stats -->
          <div class="flex items-center gap-4 bg-white/10 rounded-2xl p-4 border border-white/20 backdrop-blur-sm shadow-inner">
            <div class="text-center px-4 border-r border-white/20">
              <p class="text-2xl font-bold text-white">{{ currentUser()?.progress?.xp || 0 }}</p>
              <p class="text-xs text-greek-200 uppercase tracking-wider font-semibold">Total XP</p>
            </div>
            <div class="text-center px-4 border-r border-white/20">
              <p class="text-2xl font-bold text-white">{{ completedChapters().length }}</p>
              <p class="text-xs text-greek-200 uppercase tracking-wider font-semibold">Mastered</p>
            </div>
            <div class="text-center px-4">
              <p class="text-2xl font-bold text-white">{{ bookGroups().length }}</p>
              <p class="text-xs text-greek-200 uppercase tracking-wider font-semibold">Books</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content Area (Two Columns) -->
    <div class="px-6 py-10 max-w-6xl mx-auto">
      @if (loading()) {
        <!-- Loading skeleton -->
        <div class="flex flex-col lg:flex-row gap-10">
          <div class="lg:w-1/4 hidden lg:block animate-pulse">
             <div class="h-6 bg-surface-200 rounded w-1/2 mb-4"></div>
             <div class="h-4 bg-surface-100 rounded w-3/4 mb-2"></div>
             <div class="h-4 bg-surface-100 rounded w-2/3"></div>
          </div>
          <div class="lg:w-3/4 animate-pulse space-y-6">
            <div class="h-40 bg-surface-200 rounded-2xl w-full"></div>
            <div class="h-64 bg-surface-200 rounded-2xl w-full"></div>
          </div>
        </div>
      } @else if (bookGroups().length === 0) {
        <!-- Empty state -->
        <div class="flex flex-col items-center justify-center py-16 text-center">
          <div class="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
            <svg class="w-8 h-8 text-surface-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <h2 class="font-serif text-lg font-semibold text-surface-700 mb-2">Your grammar book is empty</h2>
          <p class="text-surface-400 text-sm max-w-sm">
            Complete chapters to automatically build your personal grammar reference.
          </p>
          <a routerLink="/chapters"
            class="mt-6 px-5 py-2.5 rounded-xl bg-greek-600 text-white text-sm font-semibold hover:bg-greek-700 transition-colors shadow-sm">
            Go to Chapters
          </a>
        </div>
      } @else {
        <div class="flex flex-col lg:flex-row gap-10 items-start">
          <!-- Left Sidebar (Table of Contents) -->
          <aside class="w-full lg:w-1/4 lg:sticky lg:top-8 bg-white border border-surface-200 rounded-2xl p-5 shadow-sm">
            <h3 class="font-serif text-lg font-semibold text-greek-900 mb-4 border-b border-surface-100 pb-3">Table of Contents</h3>
            <div class="space-y-6 max-h-[70vh] overflow-y-auto pr-2 custom-scrollbar">
              @for (group of bookGroups(); track group.book.id) {
                <div>
                  <h4 class="font-bold text-surface-400 text-xs uppercase tracking-widest mb-3">{{ group.book.title }}</h4>
                  <ul class="space-y-1 border-l-2 border-surface-100 ml-1.5 pl-3">
                    @for (chapter of group.chapters; track chapter.id) {
                      <li>
                        <button (click)="scrollTo(chapter.id)"
                           class="text-left text-sm font-medium text-surface-600 hover:text-greek-600 transition-colors w-full truncate leading-tight py-1.5 px-2 rounded-lg hover:bg-surface-50 focus:outline-none focus:bg-surface-50">
                          {{ chapter.order }}. {{ chapter.title }}
                        </button>
                      </li>
                    }
                  </ul>
                </div>
              }
            </div>
          </aside>

          <!-- Right Content Area -->
          <main class="w-full lg:w-3/4 space-y-12">
            @for (group of bookGroups(); track group.book.id) {
              <div class="space-y-8">
                <!-- Book heading separator -->
                <div class="flex items-center gap-4 mb-2">
                  <div class="flex-1 h-px bg-surface-200"></div>
                  <h2 class="font-serif text-xl font-bold text-surface-400 uppercase tracking-widest">{{ group.book.title }}</h2>
                  <div class="flex-1 h-px bg-surface-200"></div>
                </div>

                @for (chapter of group.chapters; track chapter.id) {
                  <!-- Chapter Card -->
                  <article [id]="chapter.id" class="bg-white border border-surface-200 rounded-2xl shadow-sm overflow-hidden scroll-mt-8 transition-shadow hover:shadow-md">
                    <!-- Card Header -->
                    <div class="bg-surface-50 border-b border-surface-200 px-6 md:px-8 py-5 flex items-center justify-between gap-4">
                       <div>
                         <span class="text-xs font-bold uppercase tracking-widest text-greek-600 mb-1.5 block">Chapter {{ chapter.order }}</span>
                         <h3 class="font-serif text-2xl font-semibold text-greek-900 m-0">{{ chapter.title }}</h3>
                       </div>
                       <a [routerLink]="['/chapters', chapter.id]"
                          class="shrink-0 w-10 h-10 rounded-full bg-white border border-surface-200 flex items-center justify-center text-surface-400 hover:text-greek-600 hover:border-greek-300 hover:bg-greek-50 transition-all shadow-sm"
                          title="Review Lesson">
                         <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                         </svg>
                       </a>
                    </div>
                    
                    <!-- Card Body -->
                    <div class="p-6 md:p-8">
                      @if (chapter.grammarSummary) {
                        <div class="prose prose-sm max-w-none grammar-book-content"
                          [innerHTML]="renderMarkdown(chapter.grammarSummary)">
                        </div>
                      } @else {
                        <div class="rounded-xl bg-surface-50 px-5 py-8 border border-surface-100 text-center text-sm text-surface-400 italic">
                          Grammar summary not available for this chapter.
                        </div>
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
  `,
  styles: [`
    :host ::ng-deep .grammar-book-content h1,
    :host ::ng-deep .grammar-book-content h2,
    :host ::ng-deep .grammar-book-content h3 {
      font-family: var(--font-serif, Georgia, serif);
      color: #1a1060;
      margin-top: 2rem;
      margin-bottom: 0.5rem;
    }
    :host ::ng-deep .grammar-book-content h1:first-child,
    :host ::ng-deep .grammar-book-content h2:first-child,
    :host ::ng-deep .grammar-book-content h3:first-child {
      margin-top: 0;
    }
    :host ::ng-deep .grammar-book-content h2 {
      font-size: 1.25rem;
      font-weight: 600;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 0.5rem;
    }
    :host ::ng-deep .grammar-book-content h3 {
      font-size: 1.05rem;
      font-weight: 600;
      color: #3d3093;
    }
    :host ::ng-deep .grammar-book-content p {
      color: #4a5568;
      line-height: 1.7;
      margin-bottom: 1rem;
      font-size: 0.95rem;
    }
    :host ::ng-deep .grammar-book-content table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8125rem;
      margin: 1.25rem 0;
      overflow-x: auto;
      display: block;
      border-radius: 0.5rem;
      border: 1px solid #e2e8f0;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    :host ::ng-deep .grammar-book-content th,
    :host ::ng-deep .grammar-book-content td {
      border-bottom: 1px solid #e2e8f0;
      border-right: 1px solid #e2e8f0;
      padding: 0.6rem 0.875rem;
      text-align: left;
    }
    :host ::ng-deep .grammar-book-content th {
      background-color: #0d5eaf; /* Primary Greek blue */
      font-weight: 600;
      color: white;
      text-transform: uppercase;
      font-size: 0.75rem;
      letter-spacing: 0.05em;
    }
    :host ::ng-deep .grammar-book-content tr:nth-child(even) td {
      background-color: #f8f9fb;
    }
    :host ::ng-deep .grammar-book-content ul,
    :host ::ng-deep .grammar-book-content ol {
      padding-left: 1.5rem;
      margin-bottom: 1rem;
      font-size: 0.95rem;
      color: #4a5568;
    }
    :host ::ng-deep .grammar-book-content li {
      margin-bottom: 0.4rem;
    }
    :host ::ng-deep .grammar-book-content strong {
      color: #0d5eaf; /* Distinct Greek blue for highlights */
      font-weight: 700;
    }
    :host ::ng-deep .grammar-book-content em {
      color: #3d3093;
    }
    :host ::ng-deep .grammar-book-content hr {
      border-color: #e2e8f0;
      margin: 1.5rem 0;
    }
    :host ::ng-deep .grammar-book-content blockquote {
      background-color: #eef5fc; /* Soft Greek blue background */
      border-left: 4px solid #4293d8; /* Brighter border */
      border-radius: 0 0.5rem 0.5rem 0;
      padding: 1rem 1.25rem;
      color: #0a4d92; /* Deep blue text */
      margin: 1.25rem 0;
      position: relative;
    }
    :host ::ng-deep .grammar-book-content blockquote p {
      color: inherit;
      margin: 0;
      font-size: 0.95rem;
      line-height: 1.6;
    }
    :host ::ng-deep .grammar-book-content blockquote::before {
      content: "ℹ️ TIP";
      display: block;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #4293d8;
      margin-bottom: 0.25rem;
      font-family: var(--font-sans);
    }
    
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
  `],
})
export class GrammarBookPage implements OnInit {
  authService = inject(AuthService);
  private lessonService = inject(LessonService);
  private sanitizer = inject(DomSanitizer);
  private scroller = inject(ViewportScroller);

  loading = signal(true);
  currentUser = this.authService.currentUser;

  completedChapters = signal<Chapter[]>([]);
  private books = signal<Book[]>([]);

  /** Chapters grouped by book, sorted by book order then chapter order. */
  bookGroups = computed<BookGroup[]>(() => {
    const chapters = this.completedChapters();
    const allBooks = this.books();
    if (chapters.length === 0 || allBooks.length === 0) return [];

    // Build a map of bookId → book for quick lookup
    const bookMap = new Map(allBooks.map(b => [b.id, b]));

    // Group chapters by bookId
    const grouped = new Map<string, Chapter[]>();
    for (const ch of chapters) {
      const existing = grouped.get(ch.bookId) ?? [];
      grouped.set(ch.bookId, [...existing, ch]);
    }

    // Sort chapters within each book by order
    for (const [bookId, chs] of grouped) {
      grouped.set(bookId, [...chs].sort((a, b) => a.order - b.order));
    }

    // Build BookGroup array sorted by book order
    const groups: BookGroup[] = [];
    for (const [bookId, chs] of grouped) {
      const book = bookMap.get(bookId);
      if (book) {
        groups.push({ book, chapters: chs });
      }
    }
    groups.sort((a, b) => a.book.order - b.book.order);
    return groups;
  });

  async ngOnInit(): Promise<void> {
    const completedIds = this.authService.currentUser()?.progress?.completedChapterIds ?? [];

    if (completedIds.length === 0) {
      this.loading.set(false);
      return;
    }

    // Fetch chapters and books in parallel
    const [chapters, books] = await Promise.all([
      firstValueFrom(this.lessonService.getChaptersByIds(completedIds)),
      firstValueFrom(this.lessonService.getBooks()),
    ]);

    this.completedChapters.set(chapters ?? []);
    this.books.set(books ?? []);
    this.loading.set(false);
  }

  renderMarkdown(md: string): SafeHtml {
    const html = marked.parse(md, { async: false }) as string;
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }

  scrollTo(id: string): void {
    this.scroller.scrollToAnchor(id);
  }
}
