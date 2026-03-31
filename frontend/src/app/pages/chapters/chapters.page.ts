import { Component, inject, OnInit } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { RouterLink, Router } from '@angular/router';
import { LessonService } from '../../core/services/lesson.service';
import { AuthService } from '../../core/services/auth.service';
import { Book, Chapter } from '../../core/models/firestore.models';
import { Observable, map } from 'rxjs';

interface BookWithChapters extends Book {
  chapters$: Observable<Chapter[]>;
}

@Component({
  selector: 'app-chapters',
  standalone: true,
  imports: [AsyncPipe, RouterLink],  template: `
    <div class="px-6 py-8 max-w-4xl mx-auto">

      <!-- Page heading -->
      <div class="mb-8">
        <h1 class="font-serif text-3xl font-semibold text-greek-900 mb-1">Your Course</h1>
        <p class="text-greek-700 text-sm">Pick up where you left off and keep learning Modern Greek.</p>
      </div>

      <!-- Book sections -->
      @if (booksWithChapters$ | async; as books) {
        @if (books.length === 0) {
          <!-- Empty state -->
          <div class="flex flex-col items-center justify-center py-20 text-center">
            <div class="w-16 h-16 rounded-full bg-greek-50 flex items-center justify-center mb-4">
              <svg class="w-8 h-8 text-greek-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
              </svg>
            </div>
            <h2 class="font-serif text-xl font-semibold text-surface-700 mb-2">No content yet</h2>
            <p class="text-surface-400 text-sm max-w-xs">
              Course books will appear here once they've been published by the instructor.
            </p>
          </div>
        } @else {
          <div class="space-y-10">
            @for (book of books; track book.id) {
              <section>
                <!-- Book header -->
                <div class="flex items-center gap-3 mb-4">
                  <div class="flex items-center justify-center w-8 h-8 rounded-lg bg-greek-600 text-white text-xs font-bold shrink-0">
                    {{ book.order }}
                  </div>
                  <div>
                    <h2 class="font-serif text-lg font-semibold text-greek-900 leading-tight">{{ book.title }}</h2>
                    <p class="text-surface-400 text-xs">{{ book.description }}</p>
                  </div>
                </div>

                <!-- Chapter cards -->
                @if (book.chapters$ | async; as chapters) {
                  @if (chapters.length === 0) {
                    <div class="bg-white border border-surface-200 rounded-xl px-5 py-8 text-center">
                      <p class="text-surface-400 text-sm">No chapters in this book yet.</p>
                    </div>
                  } @else {
                    <div class="space-y-2.5">
                      @for (chapter of chapters; track chapter.id) {
                        <!-- Chapter card: outer div (not <a>) so we can nest buttons inside -->
                        <div
                          class="group bg-white border border-greek-200 rounded-xl hover:border-greek-400 hover:shadow-md hover:bg-greek-50 transition-all duration-150 overflow-hidden"
                        >
                          <!-- Clickable chapter row -->
                          <a
                            [routerLink]="['/chapters', chapter.id]"
                            class="flex items-center gap-4 px-5 py-4"
                          >
                            <!-- Chapter number badge -->
                            <div class="shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-colors"
                              [class]="getChapterBadgeClass(chapter.id)">
                              @if (isCompleted(chapter.id)) {
                                <svg class="w-4.5 h-4.5" fill="currentColor" viewBox="0 0 20 20">
                                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                                </svg>
                              } @else {
                                {{ chapter.order }}
                              }
                            </div>

                            <!-- Text -->
                            <div class="flex-1 min-w-0">
                              <p class="font-semibold text-surface-800 group-hover:text-greek-700 transition-colors truncate">
                                {{ chapter.title }}
                              </p>
                              @if (chapter.length) {
                                <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-surface-100 text-surface-500 capitalize ml-2 align-middle">
                                  ⏱️ {{ chapter.length }}
                                </span>
                              }
                              <p class="text-surface-400 text-sm mt-0.5 truncate">{{ chapter.summary }}</p>
                            </div>

                            <!-- Arrow -->
                            <svg class="w-4 h-4 text-surface-300 group-hover:text-greek-500 shrink-0 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                            </svg>
                          </a>

                          <!-- Practice Set buttons (shown only if practice sets exist) -->
                          @if (chapter.practiceSetIds && chapter.practiceSetIds.length > 0) {
                            <div class="border-t border-greek-100 px-5 py-2.5 flex items-center gap-2 flex-wrap bg-white/60">
                              <span class="text-[10px] font-semibold uppercase tracking-wider text-surface-400 mr-1">Practice</span>
                              @for (psId of chapter.practiceSetIds; track psId; let i = $index) {
                                <button
                                  (click)="navigateToPractice(psId)"
                                  class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs font-semibold transition-all duration-150"
                                  [class]="getPracticeButtonClass(psId)"
                                  [title]="isPracticeCompleted(psId) ? 'Practice set completed' : 'Start practice set'"
                                >
                                  <!-- Dumbbell icon -->
                                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" [attr.fill]="isPracticeCompleted(psId) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M6.5 6.5h11M6.5 6.5a2 2 0 01-4 0 2 2 0 014 0zM17.5 6.5a2 2 0 004 0 2 2 0 00-4 0zM6.5 17.5h11M6.5 17.5a2 2 0 01-4 0 2 2 0 014 0zM17.5 17.5a2 2 0 004 0 2 2 0 00-4 0zM6.5 6.5v11M17.5 6.5v11"/>
                                  </svg>
                                  Set {{ i + 1 }}
                                </button>
                              }
                            </div>
                          }
                        </div>
                      }
                    </div>
                  }
                } @else {
                  <!-- Skeleton loading state -->
                  <div class="space-y-2.5">
                    @for (i of [1, 2, 3]; track i) {
                      <div class="bg-white border border-surface-200 rounded-xl px-5 py-4 flex items-center gap-4 animate-pulse">
                        <div class="w-9 h-9 rounded-full bg-surface-100 shrink-0"></div>
                        <div class="flex-1">
                          <div class="h-4 bg-surface-100 rounded w-40 mb-2"></div>
                          <div class="h-3 bg-surface-100 rounded w-64"></div>
                        </div>
                      </div>
                    }
                  </div>
                }
              </section>
            }
          </div>
        }
      } @else {
        <!-- Initial loading — books skeleton -->
        <div class="space-y-10">
          @for (i of [1, 2]; track i) {
            <section>
              <div class="flex items-center gap-3 mb-4 animate-pulse">
                <div class="w-8 h-8 rounded-lg bg-surface-200"></div>
                <div>
                  <div class="h-4 bg-surface-200 rounded w-32 mb-1"></div>
                  <div class="h-3 bg-surface-100 rounded w-48"></div>
                </div>
              </div>
              <div class="space-y-2.5">
                @for (j of [1, 2, 3]; track j) {
                  <div class="bg-white border border-surface-200 rounded-xl px-5 py-4 flex items-center gap-4 animate-pulse">
                    <div class="w-9 h-9 rounded-full bg-surface-100 shrink-0"></div>
                    <div class="flex-1">
                      <div class="h-4 bg-surface-100 rounded w-36 mb-2"></div>
                      <div class="h-3 bg-surface-100 rounded w-56"></div>
                    </div>
                  </div>
                }
              </div>
            </section>
          }
        </div>
      }
    </div>
  `,
})
export class ChaptersPage implements OnInit {
  readonly lessonService = inject(LessonService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  booksWithChapters$!: Observable<BookWithChapters[]>;

  ngOnInit() {
    this.booksWithChapters$ = this.lessonService.getBooks().pipe(
      map(books => books.map(book => ({
        ...book,
        chapters$: this.lessonService.getChaptersByBook(book.id)
      })))
    );
  }

  isCompleted(chapterId: string): boolean {
    const completed = this.authService.currentUser()?.progress?.completedChapterIds ?? [];
    return completed.includes(chapterId);
  }

  isPracticeCompleted(practiceSetId: string): boolean {
    const completed = this.authService.currentUser()?.progress?.completedPracticeSetIds ?? [];
    return completed.includes(practiceSetId);
  }

  navigateToPractice(practiceSetId: string): void {
    this.router.navigate(['/practice', practiceSetId]);
  }

  getChapterBadgeClass(chapterId: string): string {
    if (this.isCompleted(chapterId)) {
      return 'bg-greek-600 text-white';
    }
    return 'bg-greek-50 text-greek-700 group-hover:bg-greek-100';
  }

  getPracticeButtonClass(practiceSetId: string): string {
    if (this.isPracticeCompleted(practiceSetId)) {
      return 'border-practice-300 bg-practice-600 text-white hover:bg-practice-700';
    }
    return 'border-practice-300 text-practice-600 hover:bg-practice-50';
  }
}
