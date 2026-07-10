import { AsyncPipe, DatePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { toObservable } from '@angular/core/rxjs-interop';
import { combineLatest, map } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { LessonService } from '../../core/services/lesson.service';
import { Book, Chapter } from '../../core/models/firestore.models';
import { GcsUrlPipe } from '../../shared/pipes/gcs-url.pipe';

interface CurriculumRow {
  book: Book;
  curriculumChapterId: string;
  order: number;
  selected: Chapter;
  variants: Chapter[];
}

@Component({
  selector: 'app-curriculum',
  standalone: true,
  imports: [AsyncPipe, DatePipe, GcsUrlPipe, RouterLink],
  template: `
    <div class="px-4 sm:px-6 py-8 max-w-6xl mx-auto">
      <div class="mb-8">
        <h1 class="font-serif text-3xl font-semibold text-greek-900 mb-1">Curriculum</h1>
        <p class="text-greek-700 text-sm">Choose which lesson variant appears in your course map.</p>
      </div>

      @if (rows$ | async; as rows) {
        @if (rows.length === 0) {
          <div class="bg-white border border-surface-200 rounded-2xl px-6 py-12 text-center text-surface-400">
            No selectable lessons are available yet.
          </div>
        } @else {
          <div class="space-y-8">
            @for (row of rows; track row.curriculumChapterId) {
              <section class="bg-white border border-greek-100 rounded-2xl shadow-sm overflow-hidden">
                <div class="px-5 py-4 border-b border-greek-100 bg-greek-50">
                  <div class="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wider text-greek-600 mb-2">
                    <span>Book {{ row.book.order }}: {{ row.book.title }}</span>
                    <span>Lesson {{ row.order }}</span>
                    <span>{{ row.curriculumChapterId }}</span>
                  </div>
                  <h2 class="font-serif text-2xl font-semibold text-greek-900">{{ row.selected.topic }}</h2>
                </div>

                <div class="flex gap-4 overflow-x-auto p-5 snap-x">
                  @for (variant of row.variants; track variant.id) {
                    <article class="min-w-[18rem] sm:min-w-[21rem] max-w-[21rem] snap-start border rounded-2xl overflow-hidden bg-white"
                      [class.border-greek-500]="variant.id === row.selected.id"
                      [class.border-surface-200]="variant.id !== row.selected.id">
                      @if (variant.coverImageUrl) {
                        <img [src]="(variant.coverImageUrl | gcsUrl | async) ?? ''" alt="" class="h-36 w-full object-cover" />
                      } @else {
                        <div class="h-36 w-full bg-greek-100"></div>
                      }
                      <div class="p-4">
                        <div class="flex items-center gap-2 mb-2">
                          @if (variant.id === row.selected.id) {
                            <span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-greek-600 text-white">Selected</span>
                          }
                          @if (isCompleted(variant.id)) {
                            <span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-gold-100 text-gold-700">Completed</span>
                          }
                          @if (variant.isSelectableAlternative === false) {
                            <span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-surface-100 text-surface-500">No longer offered</span>
                          }
                        </div>

                        <p class="text-xs font-semibold uppercase tracking-wider text-greek-600 mb-1">{{ variant.topic }}</p>
                        <h3 class="font-serif text-xl font-semibold text-surface-900 mb-2">{{ variant.title }}</h3>
                        <p class="text-sm text-surface-500 line-clamp-3 mb-4">{{ variant.summary }}</p>

                        <dl class="grid grid-cols-2 gap-2 text-xs text-surface-500 mb-4">
                          <div><dt class="font-semibold text-surface-700">Generated</dt><dd>{{ variant.generatedAt?.toDate() | date:'mediumDate' }}</dd></div>
                          <div><dt class="font-semibold text-surface-700">Length</dt><dd class="capitalize">{{ variant.length || 'n/a' }}</dd></div>
                          <div><dt class="font-semibold text-surface-700">Skill</dt><dd>{{ variant.languageSkill || 'n/a' }}</dd></div>
                          <div><dt class="font-semibold text-surface-700">Exercises</dt><dd>{{ variant.exercises.length }}</dd></div>
                          <div><dt class="font-semibold text-surface-700">Practice</dt><dd>{{ variant.practiceSetIds?.length || 0 }} set(s)</dd></div>
                        </dl>

                        <div class="flex gap-2">
                          <a [routerLink]="['/chapters', variant.id]" class="flex-1 text-center px-3 py-2 rounded-lg border border-greek-200 text-sm font-semibold text-greek-700 hover:bg-greek-50">Open</a>
                          <button
                            type="button"
                            class="flex-1 px-3 py-2 rounded-lg text-sm font-semibold"
                            [class.bg-greek-600]="variant.id !== row.selected.id"
                            [class.text-white]="variant.id !== row.selected.id"
                            [class.bg-surface-100]="variant.id === row.selected.id"
                            [class.text-surface-400]="variant.id === row.selected.id"
                            [disabled]="variant.id === row.selected.id || variant.isSelectableAlternative === false"
                            (click)="select(row.curriculumChapterId, variant.id)"
                          >
                            {{ variant.id === row.selected.id ? 'Selected' : 'Select' }}
                          </button>
                        </div>
                      </div>
                    </article>
                  }
                </div>
              </section>
            }
          </div>
        }
      }
    </div>
  `,
})
export class CurriculumPage {
  private readonly lessonService = inject(LessonService);
  private readonly authService = inject(AuthService);
  private readonly user$ = toObservable(this.authService.currentUser);

  readonly rows$ = combineLatest([
    this.lessonService.getBooks(),
    this.lessonService.getAllChapters(),
    this.user$,
  ]).pipe(
    map(([books, chapters, user]) => this.buildRows(books, chapters, user?.curriculum?.selectedChapterIdsByCurriculumChapterId ?? {}))
  );

  async select(curriculumChapterId: string, chapterId: string): Promise<void> {
    await this.lessonService.setCurriculumSelection(curriculumChapterId, chapterId);
  }

  isCompleted(chapterId: string): boolean {
    return this.authService.currentUser()?.progress?.completedChapterIds?.includes(chapterId) ?? false;
  }

  private buildRows(books: Book[], chapters: Chapter[], selectedBySlot: Record<string, string>): CurriculumRow[] {
    const booksById = new Map(books.map((book) => [book.id, book]));
    const groups = new Map<string, Chapter[]>();
    for (const chapter of chapters) {
      groups.set(chapter.curriculumChapterId, [...(groups.get(chapter.curriculumChapterId) ?? []), chapter]);
    }

    const rows: CurriculumRow[] = [];
    for (const [slot, variants] of groups) {
      const selectedId = selectedBySlot[slot];
      const visible = variants.filter((chapter) => chapter.isSelectableAlternative !== false || chapter.id === selectedId);
      if (!visible.length) continue;

      const selected = visible.find((chapter) => chapter.id === selectedId) ?? this.newestSelectable(visible);
      if (!selected) continue;
      const book = booksById.get(selected.bookId);
      if (!book) continue;

      rows.push({
        book,
        curriculumChapterId: slot,
        order: selected.order,
        selected,
        variants: visible.sort((a, b) => this.alternativeSort(a, b, selected.id)),
      });
    }

    return rows.sort((a, b) =>
      a.book.order - b.book.order || a.order - b.order || a.curriculumChapterId.localeCompare(b.curriculumChapterId)
    );
  }

  private newestSelectable(chapters: Chapter[]): Chapter | undefined {
    return chapters.filter((chapter) => chapter.isSelectableAlternative !== false).sort((a, b) => this.generatedAtMs(b) - this.generatedAtMs(a) || b.id.localeCompare(a.id))[0];
  }

  private alternativeSort(a: Chapter, b: Chapter, selectedId: string): number {
    if (a.id === selectedId) return -1;
    if (b.id === selectedId) return 1;
    return this.generatedAtMs(b) - this.generatedAtMs(a) || b.id.localeCompare(a.id);
  }

  private generatedAtMs(chapter: Chapter): number {
    return chapter.generatedAt?.toMillis() ?? Number.NEGATIVE_INFINITY;
  }
}
