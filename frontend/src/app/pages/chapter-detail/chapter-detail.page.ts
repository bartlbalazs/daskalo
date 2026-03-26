import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AsyncPipe } from '@angular/common';
import { LessonService } from '../../core/services/lesson.service';
import { AuthService } from '../../core/services/auth.service';
import { Chapter, Exercise, GrammarNote, PassageSentence, VocabularyItem } from '../../core/models/firestore.models';
import { Observable, switchMap } from 'rxjs';
import { GcsUrlPipe } from '../../shared/pipes/gcs-url.pipe';
import { HighlightVocabPipe } from '../../shared/pipes/highlight-vocab.pipe';
import { Storage, ref, getDownloadURL } from '@angular/fire/storage';
import { ExerciseCardComponent } from './exercises/exercise-card.component';
import { AudioPlayerComponent } from './exercises/audio-player.component';
import { environment } from '../../../environments/environment';
import { marked } from 'marked';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

@Component({
  selector: 'app-chapter-detail',
  standalone: true,
  imports: [AsyncPipe, RouterLink, GcsUrlPipe, HighlightVocabPipe, ExerciseCardComponent, AudioPlayerComponent],
  template: `
    @if (chapter$ | async; as chapter) {

      <!-- ===== HERO BAND ===== -->
      <div class="w-full bg-gradient-to-b from-greek-700 to-greek-600 border-b border-greek-800">
        <div class="px-6 py-10 max-w-5xl mx-auto">

          <!-- Breadcrumb -->
          <nav class="flex items-center gap-1.5 text-sm text-greek-200 mb-6">
            <a routerLink="/chapters" class="hover:text-white transition-colors">Course</a>
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <span class="text-white truncate">{{ chapter.title }}</span>
          </nav>

          <!-- Cover image -->
          @if (chapter.coverImageUrl) {
            <img
              [src]="(chapter.coverImageUrl | gcsUrl | async) ?? ''"
              alt=""
              class="w-full h-64 md:h-96 object-cover rounded-2xl mb-7 border border-greek-500 shadow-xl"
            />
          }

          <!-- Badge pills -->
          <div class="flex flex-wrap items-center gap-2 mb-3">
            <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-bold tracking-wide bg-white text-greek-700 shadow-sm">
              Chapter {{ chapter.order }}
            </span>
            @if (chapter.languageSkill) {
              <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-gold-400 text-greek-900 border border-gold-500">
                {{ chapter.languageSkill }}
              </span>
            }
          </div>

          <!-- Title + summary -->
          <h1 class="font-serif text-4xl md:text-5xl font-semibold text-white mb-4 leading-tight">{{ chapter.title }}</h1>
          <p class="text-xl text-greek-100 leading-relaxed">{{ chapter.summary }}</p>
        </div>
      </div>

      <!-- ===== GRAMMAR NOTES BAND ===== -->
      <div class="w-full bg-white border-b border-greek-100">
        <div class="px-6 py-14 max-w-5xl mx-auto">

          <!-- Section header -->
          <div class="flex items-center gap-3 mb-8">
            <div class="w-9 h-9 rounded-lg bg-greek-600 flex items-center justify-center shrink-0 shadow-sm">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
            </div>
            <div>
              <h2 class="font-serif text-3xl font-semibold text-greek-900 leading-none">Grammar Notes</h2>
              <p class="text-sm text-surface-400 mt-0.5">Key concepts for this chapter</p>
            </div>
          </div>

          @if (chapter.grammarNotes.length) {
            <div class="space-y-6">
              @for (note of chapter.grammarNotes; track note.heading) {
                <div class="bg-white border border-greek-100 rounded-2xl overflow-hidden shadow-md">
                  @if (note.imageUrl) {
                    <img [src]="(note.imageUrl | gcsUrl | async) ?? ''" alt="" class="w-full h-48 md:h-64 object-cover border-b border-surface-100" />
                  }
                  <div class="p-6 md:p-10">
                    <h3 class="font-serif text-xl font-semibold text-greek-900 mb-2">{{ note.heading }}</h3>
                    <p class="text-surface-600 mb-5 leading-relaxed">{{ note.explanation }}</p>

                    @if (note.grammar_table) {
                      <div class="mb-5 overflow-x-auto rounded-xl border border-surface-200">
                        <div class="prose prose-sm max-w-none grammar-table"
                          [innerHTML]="renderMarkdown(note.grammar_table)">
                        </div>
                      </div>
                    }

                    @if (note.audioUrl) {
                      <div class="mb-5">
                        <p class="text-xs font-semibold uppercase tracking-wider text-surface-400 mb-2">Listen to examples</p>
                        <app-audio-player [src]="note.audioUrl" />
                      </div>
                    }

                    @if (note.examples.length) {
                      <div class="space-y-2.5">
                        @for (example of note.examples; track example.greek) {
                          <div class="bg-greek-50 rounded-xl p-4 border border-greek-100">
                            <p class="font-medium text-greek-800 text-base mb-0.5"
                               [innerHTML]="example.greek | highlightVocab:chapter.vocabulary"></p>
                            <p class="text-surface-500 text-sm">{{ example.english }}</p>
                            @if (example.note) {
                              <p class="text-xs text-surface-400 mt-2 italic">{{ example.note }}</p>
                            }
                          </div>
                        }
                      </div>
                    }
                  </div>
                </div>
              }
            </div>
          } @else {
            <div class="bg-white border border-surface-200 rounded-2xl px-6 py-6 text-surface-400 text-sm italic shadow-sm">
              No grammar notes for this chapter yet.
            </div>
          }
        </div>
      </div>

      <!-- ===== VOCABULARY BAND ===== -->
      <div class="w-full bg-white border-b border-greek-100">
        <div class="px-6 py-12 max-w-5xl mx-auto">

          <!-- Section header -->
          <div class="flex items-center gap-3 mb-7">
            <div class="w-9 h-9 rounded-lg bg-greek-600 flex items-center justify-center shrink-0 shadow-sm">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"/>
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <h2 class="font-serif text-3xl font-semibold text-greek-900 leading-none">Vocabulary</h2>
              <p class="text-sm text-surface-400 mt-0.5">{{ chapter.vocabulary.length }} words to learn</p>
            </div>
          </div>

          @if (chapter.vocabulary.length) {
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              @for (word of sortedVocabulary(chapter); track word.greek) {
                <div class="group bg-white border border-greek-100 rounded-xl p-4 hover:border-greek-300 hover:shadow-md transition-all duration-150">
                  <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0">
                      <p class="font-serif text-2xl font-semibold text-greek-800 leading-tight mb-0.5">{{ word.greek }}</p>
                      <p class="text-surface-500 text-sm">{{ word.english }}</p>
                    </div>
                    @if (word.audioUrl) {
                      <button
                        (click)="playAudio(word.audioUrl, word.greek)"
                        class="shrink-0 w-9 h-9 rounded-full bg-greek-50 text-greek-600 flex items-center justify-center hover:bg-greek-600 hover:text-white transition-colors mt-0.5"
                        title="Listen to pronunciation"
                        [disabled]="playingWord() === word.greek"
                      >
                        @if (playingWord() === word.greek) {
                          <svg class="w-4 h-4 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/>
                          </svg>
                        } @else {
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0-12L8.464 9.536M12 6l3.536 3.536M8.464 14.464A5 5 0 018.464 9.536M5.05 18.364A9 9 0 015.05 5.636"/>
                          </svg>
                        }
                      </button>
                    }
                  </div>
                </div>
              }
            </div>
          } @else {
            <div class="bg-surface-100 rounded-xl px-6 py-5 text-surface-400 text-sm italic">
              No vocabulary listed for this chapter.
            </div>
          }
        </div>
      </div>

      <!-- ===== EXERCISES BAND ===== -->
      <div class="w-full bg-greek-50">
        <div class="px-6 py-16 max-w-5xl mx-auto">

          <!-- Section header -->
          <div class="flex items-center gap-3 mb-8">
            <div class="w-9 h-9 rounded-lg bg-greek-600 flex items-center justify-center shrink-0 shadow-sm">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
              </svg>
            </div>
            <div>
              <h2 class="font-serif text-3xl font-semibold text-greek-900 leading-none">Exercises</h2>
              <p class="text-sm text-surface-400 mt-0.5">{{ visibleExercises(chapter).length }} exercises — complete all to finish the chapter</p>
            </div>
          </div>

          @if (visibleExercises(chapter).length) {

            <!-- Progress bar -->
            @if (gradableCount(chapter) > 0) {
              <div class="mb-8">
                <div class="flex justify-between items-center text-xs text-surface-500 mb-2">
                  <span>Progress</span>
                  <span class="font-semibold text-greek-700">{{ answeredCount(chapter) }} / {{ gradableCount(chapter) }} completed</span>
                </div>
                <div class="w-full bg-greek-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    class="h-2.5 rounded-full transition-all duration-500"
                    [class]="allAnswered(chapter) ? 'bg-emerald-500' : 'bg-greek-500'"
                    [style.width.%]="answeredCount(chapter) / gradableCount(chapter) * 100">
                  </div>
                </div>
              </div>
            }

            <div class="space-y-12 mb-8">
              @for (exercise of visibleExercises(chapter); track $index) {
                <app-exercise-card
                  [exercise]="exercise"
                  [index]="$index"
                  [chapterId]="chapter.id"
                  [chapterStoragePath]="chapterStoragePath(chapter.id)"
                  [sentenceAudioUrls]="chapter.sentenceAudioUrls ?? []"
                  [passageAudioUrl]="chapter.passageAudioUrl ?? ''"
                  [passage]="chapter.passage ?? []"
                  [passageText]="chapter.passage_text ?? ''"
                  [vocabulary]="chapter.vocabulary"
                  (answered)="onExerciseAnswered($event, chapter)"
                />
              }
            </div>

            <!-- Already completed banner (shown when revisiting a prior-completed chapter) -->
            @if (alreadyCompleted()) {
              <div class="mb-8 rounded-2xl bg-greek-50 border border-greek-200 px-6 py-4 flex items-center gap-3 shadow-sm">
                <div class="w-8 h-8 rounded-full bg-greek-600 flex items-center justify-center shrink-0">
                  <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                  </svg>
                </div>
                <div class="flex-1">
                  <p class="font-semibold text-greek-800 text-sm">Chapter already completed</p>
                  <p class="text-greek-600 text-xs mt-0.5">Feel free to review the content and practise the exercises.</p>
                </div>
                <a routerLink="/grammar-book"
                  class="shrink-0 inline-flex items-center gap-1 text-xs font-medium text-greek-600 hover:text-greek-800 transition-colors">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                  </svg>
                  Grammar Book
                </a>
              </div>
            }

            <!-- Complete Chapter button — shown when all exercises have been attempted -->
            @if (allAnswered(chapter) && !chapterCompleted() && !alreadyCompleted()) {
              <div class="rounded-2xl bg-emerald-50 border-2 border-emerald-300 px-6 py-6 flex flex-col sm:flex-row items-center gap-4 shadow-sm">
                <div class="flex-1 text-center sm:text-left">
                  <p class="font-bold text-emerald-800 text-base">All exercises passed!</p>
                  <p class="text-emerald-700 text-sm mt-0.5">Save your progress and unlock the next chapter.</p>
                </div>
                <button
                  (click)="onCompleteChapter(chapter.id)"
                  [disabled]="completing()"
                  class="shrink-0 px-7 py-3 rounded-xl bg-emerald-600 text-white font-bold text-sm hover:bg-emerald-700 active:scale-95 transition-all shadow-md disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  @if (completing()) {
                    <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                    </svg>
                    Saving…
                  } @else {
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                    </svg>
                    Complete Chapter
                  }
                </button>
              </div>
            }

            <!-- Chapter completed celebration banner -->
            @if (chapterCompleted()) {
              <div class="rounded-2xl bg-gradient-to-br from-emerald-50 to-greek-50 border-2 border-emerald-300 px-6 py-7 text-center shadow-md">
                <div class="w-14 h-14 rounded-full bg-emerald-500 flex items-center justify-center mx-auto mb-4 shadow-lg">
                  <svg class="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                  </svg>
                </div>
                <p class="font-bold text-emerald-800 text-xl font-serif mb-1">Chapter Complete!</p>
                <p class="text-emerald-700 text-sm">
                  Your progress has been saved.
                </p>
                <div class="mt-4 flex items-center justify-center gap-4 flex-wrap">
                  <a routerLink="/chapters" class="text-sm font-semibold text-greek-600 hover:text-greek-800 transition-colors">
                    Back to course &rarr;
                  </a>
                  <a routerLink="/grammar-book" class="inline-flex items-center gap-1.5 text-sm font-semibold text-greek-600 hover:text-greek-800 transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                    </svg>
                    View in Grammar Book
                  </a>
                </div>
              </div>
            }

            <!-- Error banner -->
            @if (completeError()) {
              <div class="mt-4 rounded-2xl border border-red-300 bg-red-50 px-6 py-4 flex items-center gap-3">
                <svg class="w-5 h-5 text-red-400 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
                <p class="text-sm text-red-700">{{ completeError() }}</p>
              </div>
            }

          } @else {
            <div class="bg-white border border-surface-200 rounded-2xl px-6 py-6 text-surface-400 text-sm italic shadow-sm">
              No exercises for this chapter yet.
            </div>
          }
        </div>
      </div>

    } @else {
      <!-- Loading skeleton — banded to match real layout -->
      <div class="w-full bg-white border-b border-surface-200 animate-pulse">
        <div class="px-6 py-10 max-w-5xl mx-auto">
          <div class="h-4 bg-surface-200 rounded w-40 mb-6"></div>
          <div class="h-64 md:h-96 bg-surface-200 rounded-2xl w-full mb-7"></div>
          <div class="flex gap-2 mb-3">
            <div class="h-6 bg-surface-200 rounded-full w-20"></div>
            <div class="h-6 bg-surface-100 rounded-full w-28"></div>
          </div>
          <div class="h-12 bg-surface-200 rounded w-3/4 mb-4"></div>
          <div class="h-6 bg-surface-100 rounded w-full mb-1.5"></div>
          <div class="h-6 bg-surface-100 rounded w-2/3"></div>
        </div>
      </div>
      <div class="w-full bg-surface-50 border-b border-surface-200 animate-pulse">
        <div class="px-6 py-14 max-w-5xl mx-auto">
          <div class="h-8 bg-surface-200 rounded w-40 mb-8"></div>
          <div class="bg-white border border-surface-200 rounded-2xl overflow-hidden shadow-md">
            <div class="h-48 bg-surface-100 w-full"></div>
            <div class="p-10">
              <div class="h-6 bg-surface-200 rounded w-1/3 mb-3"></div>
              <div class="h-4 bg-surface-100 rounded w-full mb-2"></div>
              <div class="h-4 bg-surface-100 rounded w-5/6 mb-5"></div>
              <div class="bg-greek-50 rounded-xl p-4">
                <div class="h-4 bg-greek-100 rounded w-1/4 mb-2"></div>
                <div class="h-3 bg-greek-100 rounded w-1/3"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="w-full bg-white border-b border-surface-200 animate-pulse">
        <div class="px-6 py-12 max-w-5xl mx-auto">
          <div class="h-8 bg-surface-200 rounded w-32 mb-7"></div>
          <div class="grid grid-cols-3 gap-3">
            @for (i of [1, 2, 3, 4, 5, 6]; track i) {
              <div class="bg-white border border-surface-100 rounded-xl p-4">
                <div class="h-7 bg-surface-100 rounded w-24 mb-2"></div>
                <div class="h-4 bg-surface-100 rounded w-16"></div>
              </div>
            }
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    :host ::ng-deep .grammar-table table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
    }
    :host ::ng-deep .grammar-table th,
    :host ::ng-deep .grammar-table td {
      border: 1px solid #e2e8f0;
      padding: 0.375rem 0.75rem;
      text-align: left;
    }
    :host ::ng-deep .grammar-table th {
      background-color: #f8f7f4;
      font-weight: 600;
      color: #3d3093;
    }
    :host ::ng-deep .grammar-table tr:nth-child(even) td {
      background-color: #faf9f7;
    }
  `],
})
export class ChapterDetailPage implements OnInit {
  private route = inject(ActivatedRoute);
  private lessonService = inject(LessonService);
  private authService = inject(AuthService);
  private storage = inject(Storage);
  private sanitizer = inject(DomSanitizer);

  chapter$!: Observable<Chapter>;
  playingWord = signal<string | null>(null);

  /** Tracks which exercise indices have been answered and their result (index -> correct). */
  private answeredMap = signal<Map<number, boolean>>(new Map());
  completing = signal(false);
  chapterCompleted = signal(false);
  /** True when the chapter was already completed on page load (prior session). */
  alreadyCompleted = signal(false);
  completeError = signal<string | null>(null);

  ngOnInit(): void {
    this.chapter$ = this.route.paramMap.pipe(
      switchMap(params => {
        const id = params.get('id')!;
        this.answeredMap.set(new Map());
        this.chapterCompleted.set(false);
        this.completeError.set(null);
        // Check if this chapter was already completed in a prior session.
        const completedIds = this.authService.currentUser()?.progress?.completedChapterIds ?? [];
        this.alreadyCompleted.set(completedIds.includes(id));
        return this.lessonService.getChapter(id);
      })
    );
  }

  /** Exercise types that have no interactive implementation and should be hidden. */
  private readonly _hiddenTypes = new Set(['vocab_flashcard', 'lyrics_fill']);

  /** Return exercises that should be shown (skip unimplemented types). */
  visibleExercises(chapter: Chapter): Exercise[] {
    return chapter.exercises.filter(ex => !this._hiddenTypes.has(ex.type));
  }

  /** Return vocabulary sorted alphabetically by Greek word. */
  sortedVocabulary(chapter: Chapter) {
    return [...chapter.vocabulary].sort((a, b) => a.greek.localeCompare(b.greek, 'el'));
  }

  /** Build the GCS path prefix for a chapter's assets. */
  chapterStoragePath(chapterId: string): string {
    return `gs://${environment.firebase.storageBucket}/chapters/${chapterId}`;
  }

  /** Called when any exercise-card emits an answer. */
  onExerciseAnswered(event: { index: number; correct: boolean }, _chapter: Chapter): void {
    this.answeredMap.update(m => {
      const next = new Map(m);
      next.set(event.index, event.correct);
      return next;
    });
  }

  /** Exercise types that are never graded (no answered event emitted). */
  private readonly _nonGradableTypes = new Set(['pronunciation_practice', 'lyrics_fill']);

  /** Number of exercises that produce a gradable result. */
  gradableCount(chapter: Chapter): number {
    return this.visibleExercises(chapter).filter(ex => !this._nonGradableTypes.has(ex.type)).length;
  }

  /** Number of gradable exercises that have been answered. */
  answeredCount(chapter: Chapter): number {
    const gradableIndices = this.visibleExercises(chapter)
      .map((ex, i) => ({ ex, i }))
      .filter(({ ex }) => !this._nonGradableTypes.has(ex.type))
      .map(({ i }) => i);
    let count = 0;
    gradableIndices.forEach(i => { if (this.answeredMap().has(i)) count++; });
    return count;
  }

  /** True when every gradable exercise has been attempted (regardless of correctness). */
  allAnswered(chapter: Chapter): boolean {
    const gradable = this.gradableCount(chapter);
    if (gradable === 0) return false;
    return this.answeredCount(chapter) >= gradable;
  }

  async onCompleteChapter(chapterId: string): Promise<void> {
    this.completing.set(true);
    this.completeError.set(null);
    try {
      await this.lessonService.completeChapter(chapterId);
      this.chapterCompleted.set(true);
    } catch (err) {
      this.completeError.set(err instanceof Error ? err.message : 'Failed to save progress. Please try again.');
    } finally {
      this.completing.set(false);
    }
  }

  /** Render a Markdown string to trusted HTML (used for grammar tables). */
  renderMarkdown(md: string): SafeHtml {
    const html = marked.parse(md, { async: false }) as string;
    return this.sanitizer.bypassSecurityTrustHtml(html);
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
