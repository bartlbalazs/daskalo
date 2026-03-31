import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { LessonService } from '../../core/services/lesson.service';
import { AuthService } from '../../core/services/auth.service';
import { PracticeSet } from '../../core/models/firestore.models';
import { switchMap } from 'rxjs';
import { GcsUrlPipe } from '../../shared/pipes/gcs-url.pipe';
import { AsyncPipe } from '@angular/common';
import { ExerciseCardComponent } from '../chapter-detail/exercises/exercise-card.component';
import { LightboxComponent } from '../../shared/components/lightbox.component';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-practice-detail',
  standalone: true,
  imports: [AsyncPipe, RouterLink, GcsUrlPipe, ExerciseCardComponent, LightboxComponent],
  template: `
    @if (practiceSet(); as ps) {

      <!-- ===== HERO BAND (practice purple) ===== -->
      <div class="w-full bg-gradient-to-b from-practice-700 to-practice-600 border-b border-practice-800">
        <div class="px-6 py-10 max-w-5xl mx-auto">

          <!-- Breadcrumb -->
          <nav class="flex items-center gap-1.5 text-sm text-practice-200 mb-6">
            <a routerLink="/chapters" class="hover:text-white transition-colors">Course</a>
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <span class="text-white truncate">{{ ps.title }}</span>
          </nav>

          <!-- Cover image -->
          @if (ps.coverImageUrl) {
            <img
              [src]="(ps.coverImageUrl | gcsUrl | async) ?? ''"
              alt=""
              class="w-full h-48 md:h-72 object-cover rounded-2xl mb-7 border border-practice-500 shadow-xl cursor-pointer"
              (click)="openLightboxFromEvent($event)"
            />
          }

          <!-- Badge -->
          <div class="flex flex-wrap items-center gap-2 mb-3">
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold bg-white text-practice-700 shadow-sm">
              <!-- Dumbbell icon -->
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">
                <path d="M14.4 14.4 9.6 9.6"/><path d="M18.657 21.485a2 2 0 1 1-2.829-2.828l-1.767 1.768a2 2 0 1 1-2.829-2.829l6.364-6.364a2 2 0 1 1 2.829 2.829l-1.768 1.767a2 2 0 1 1 2.828 2.829z"/><path d="m21.5 21.5-1.4-1.4"/><path d="M3.9 3.9 2.5 2.5"/><path d="M6.404 12.768a2 2 0 1 1-2.829-2.829l1.768-1.767a2 2 0 1 1-2.828-2.829l2.828-2.828a2 2 0 1 1 2.829 2.828l1.767-1.768a2 2 0 1 1 2.829 2.829z"/>
              </svg>
              Practice Set
            </span>
            @if (isCompleted()) {
              <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-emerald-400 text-emerald-900 border border-emerald-500">
                Completed
              </span>
            }
          </div>

          <h1 class="font-serif text-4xl md:text-5xl font-semibold text-white mb-2 leading-tight">{{ ps.title }}</h1>
          
          @if (ps.introduction) {
            <p class="text-practice-100 text-lg mb-4">{{ ps.introduction }}</p>
          }

          @if (ps.skills && ps.skills.length > 0) {
            <div class="flex flex-wrap gap-2 mb-4">
              @for (skill of ps.skills; track skill) {
                <span class="px-2.5 py-1 rounded-full text-xs font-medium bg-white/20 text-white backdrop-blur-sm">
                  {{ skill }}
                </span>
              }
            </div>
          }

          <p class="text-practice-200 text-sm">{{ ps.exercises.length }} exercises</p>
        </div>
      </div>

      <!-- ===== EXERCISES BAND ===== -->
      <div class="w-full bg-surface-50">
        <div class="px-6 py-10 max-w-5xl mx-auto">
          <div class="space-y-5">
            @for (exercise of ps.exercises; track $index) {
              <app-exercise-card
                [exercise]="exercise"
                [index]="$index"
                [chapterId]="ps.chapterId"
                [chapterStoragePath]="practiceStoragePath(ps.id)"
                (answered)="onExerciseAnswered($event)"
              />
            }
          </div>

          <!-- Complete section -->
          @if (allAnswered(ps) && !isCompleted()) {
            <div class="mt-10 p-6 bg-white rounded-2xl border border-practice-200 shadow text-center">
              <div class="text-4xl mb-2">🏋️</div>
              <h2 class="font-serif text-2xl font-semibold text-practice-800 mb-1">Practice Complete!</h2>
              <p class="text-surface-500 text-sm mb-5">You've worked through all the exercises. Ready to save your progress?</p>
              @if (completeError()) {
                <p class="text-red-500 text-sm mb-3">{{ completeError() }}</p>
              }
              <button
                (click)="onCompletePractice(ps.id)"
                [disabled]="completing()"
                class="px-6 py-3 rounded-xl bg-practice-600 text-white font-semibold hover:bg-practice-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                @if (completing()) { Saving… } @else { Save Progress }
              </button>
            </div>
          }

          <!-- Already completed / XP gained screen -->
          @if (practiceCompleted()) {
            <div class="mt-10 p-8 bg-white rounded-2xl border border-emerald-200 shadow text-center">
              <div class="text-5xl mb-3">🎉</div>
              <h2 class="font-serif text-2xl font-semibold text-emerald-700 mb-1">Well done!</h2>
              <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gold-400 text-greek-900 font-bold text-lg mb-4">
                +{{ earnedXp() }} XP
              </div>
              <p class="text-surface-500 text-sm">Keep practising to reinforce your Greek vocabulary and grammar.</p>
              <a routerLink="/chapters"
                class="mt-5 inline-block px-5 py-2.5 rounded-xl bg-practice-600 text-white font-semibold hover:bg-practice-700 transition-colors">
                Back to Course
              </a>
            </div>
          }

          @if (isCompleted() && !practiceCompleted()) {
            <div class="mt-8 text-center">
              <p class="text-sm text-surface-400">You've already completed this practice set.</p>
              <a routerLink="/chapters" class="mt-2 inline-block text-sm text-practice-600 font-semibold hover:underline">Back to Course</a>
            </div>
          }
        </div>
      </div>

    } @else {
      <!-- Loading skeleton -->
      <div class="px-6 py-10 max-w-5xl mx-auto space-y-4 animate-pulse">
        <div class="h-8 bg-surface-200 rounded w-56 mb-6"></div>
        <div class="h-48 bg-surface-200 rounded-2xl mb-6"></div>
        @for (i of [1,2,3,4,5]; track i) {
          <div class="h-24 bg-surface-200 rounded-xl"></div>
        }
      </div>
    }

    <!-- Image lightbox -->
    <app-lightbox [imageUrl]="lightboxUrl()" (closed)="closeLightbox()" />
  `,
})
export class PracticeDetailPage implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly lessonService = inject(LessonService);
  private readonly authService = inject(AuthService);

  answeredMap = signal<Map<number, boolean>>(new Map());
  completing = signal(false);
  completeError = signal<string | null>(null);
  practiceCompleted = signal(false);
  earnedXp = signal(175);
  alreadyCompleted = signal(false);
  lightboxUrl = signal<string | null>(null);

  practiceSet = toSignal(
    this.route.paramMap.pipe(
      switchMap(params => {
        const id = params.get('id') ?? '';
        const completedIds = this.authService.currentUser()?.progress?.completedPracticeSetIds ?? [];
        this.alreadyCompleted.set(completedIds.includes(id));
        return this.lessonService.getPracticeSet(id);
      })
    )
  );

  ngOnInit(): void {}

  openLightboxFromEvent(event: Event): void {
    const src = (event.target as HTMLImageElement).src;
    if (src) this.lightboxUrl.set(src);
  }

  closeLightbox(): void {
    this.lightboxUrl.set(null);
  }

  isCompleted(): boolean {
    const ps = this.practiceSet();
    if (!ps) return false;
    const completed = this.authService.currentUser()?.progress?.completedPracticeSetIds ?? [];
    return completed.includes(ps.id) || this.practiceCompleted();
  }

  practiceStoragePath(practiceSetId: string): string {
    return `gs://${environment.firebase.storageBucket}/practice_sets/${practiceSetId}`;
  }

  onExerciseAnswered(event: { index: number; correct: boolean }): void {
    this.answeredMap.update(m => {
      const next = new Map(m);
      next.set(event.index, event.correct);
      return next;
    });
  }

  allAnswered(ps: PracticeSet): boolean {
    const count = ps.exercises.length;
    if (count === 0) return false;
    return this.answeredMap().size >= count;
  }

  async onCompletePractice(practiceSetId: string): Promise<void> {
    this.completing.set(true);
    this.completeError.set(null);
    try {
      const result = await this.lessonService.completePractice(practiceSetId);
      this.practiceCompleted.set(true);
      this.earnedXp.set(result.xpGained || 175);
    } catch (err) {
      this.completeError.set(err instanceof Error ? err.message : 'Failed to save progress. Please try again.');
    } finally {
      this.completing.set(false);
    }
  }
}
