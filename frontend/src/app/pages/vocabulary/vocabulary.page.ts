import { Component, computed, inject, signal, OnInit } from '@angular/core';
import { LessonService } from '../../core/services/lesson.service';
import { AuthService } from '../../core/services/auth.service';
import { VocabularyItem } from '../../core/models/firestore.models';

interface VocabRow extends VocabularyItem {
  chapterTitle: string;
}

@Component({
  selector: 'app-vocabulary',
  standalone: true,
  template: `
    <div class="px-6 py-8 max-w-4xl mx-auto">

      <!-- Page heading -->
      <div class="mb-8">
        <h1 class="font-serif text-3xl font-semibold text-greek-900 mb-1">Vocabulary</h1>
        <p class="text-greek-700 text-sm">All words from your completed chapters.</p>
      </div>

      <!-- Search -->
      <div class="mb-6">
        <input
          type="search"
          [value]="searchQuery()"
          (input)="searchQuery.set($any($event.target).value)"
          placeholder="Search Greek or English…"
          class="w-full sm:w-80 rounded-xl border border-surface-200 bg-white px-4 py-2.5 text-sm text-surface-800 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-greek-400 focus:border-transparent"
        />
      </div>

      @if (loading()) {
        <!-- Skeleton -->
        <div class="space-y-3">
          @for (i of [1,2,3,4,5,6]; track i) {
            <div class="bg-white border border-surface-200 rounded-xl px-5 py-4 flex items-center gap-4 animate-pulse">
              <div class="h-6 bg-surface-100 rounded w-32"></div>
              <div class="h-4 bg-surface-100 rounded w-48"></div>
            </div>
          }
        </div>
      } @else if (filteredRows().length === 0) {
        <div class="flex flex-col items-center justify-center py-20 text-center">
          <div class="w-16 h-16 rounded-full bg-greek-50 flex items-center justify-center mb-4">
            <svg class="w-8 h-8 text-greek-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          @if (searchQuery()) {
            <h2 class="font-serif text-xl font-semibold text-surface-700 mb-2">No matches</h2>
            <p class="text-surface-400 text-sm max-w-xs">Try a different search term.</p>
          } @else {
            <h2 class="font-serif text-xl font-semibold text-surface-700 mb-2">No vocabulary yet</h2>
            <p class="text-surface-400 text-sm max-w-xs">Complete chapters to build your vocabulary list.</p>
          }
        </div>
      } @else {
        <!-- Word count -->
        <p class="text-surface-400 text-xs mb-3">{{ filteredRows().length }} word{{ filteredRows().length === 1 ? '' : 's' }}</p>

        <!-- Table -->
        <div class="space-y-2">
          @for (row of filteredRows(); track row.greek) {
            <div class="bg-white border border-surface-200 rounded-xl px-5 py-3.5 flex items-center gap-4 hover:border-greek-300 transition-colors">

              <!-- Audio button -->
              @if (row.audioUrl) {
                <button
                  (click)="playAudio(row.audioUrl!)"
                  class="shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-greek-500 hover:bg-greek-50 hover:text-greek-700 transition-colors"
                  aria-label="Play pronunciation"
                >
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
                  </svg>
                </button>
              } @else {
                <div class="shrink-0 w-8 h-8"></div>
              }

              <!-- Greek word -->
              <span class="font-serif text-lg font-semibold text-greek-900 w-40 shrink-0">{{ row.greek }}</span>

              <!-- English translation -->
              <span class="text-surface-600 text-sm flex-1">{{ row.english }}</span>

              <!-- Chapter source -->
              <span class="text-surface-300 text-xs hidden sm:block shrink-0">{{ row.chapterTitle }}</span>
            </div>
          }
        </div>
      }
    </div>
  `,
})
export class VocabularyPage implements OnInit {
  private lessonService = inject(LessonService);
  private authService = inject(AuthService);

  searchQuery = signal('');
  loading = signal(true);

  private allRows = signal<VocabRow[]>([]);

  filteredRows = computed(() => {
    const q = this.searchQuery().toLowerCase().trim();
    if (!q) return this.allRows();
    return this.allRows().filter(
      r => r.greek.toLowerCase().includes(q) || r.english.toLowerCase().includes(q)
    );
  });

  ngOnInit(): void {
    const completedIds = this.authService.currentUser()?.progress?.completedChapterIds ?? [];

    this.lessonService.getChaptersByIds(completedIds).subscribe({
      next: chapters => {
        const seen = new Set<string>();
        const rows: VocabRow[] = [];

        for (const chapter of chapters) {
          for (const item of chapter.vocabulary ?? []) {
            const key = item.greek.toLowerCase();
            if (!seen.has(key)) {
              seen.add(key);
              rows.push({ ...item, chapterTitle: chapter.title });
            }
          }
        }

        // Sort alphabetically by Greek word
        rows.sort((a, b) => a.greek.localeCompare(b.greek, 'el'));
        this.allRows.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  playAudio(url: string): void {
    new Audio(url).play().catch(() => {/* ignore */});
  }
}
