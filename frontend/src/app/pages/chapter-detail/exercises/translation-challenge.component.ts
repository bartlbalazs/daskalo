import { Component, Input, Output, EventEmitter, signal, ChangeDetectionStrategy } from '@angular/core';
import { Exercise, TranslationChallengeData, EvaluationResult } from '../../../core/models/firestore.models';

@Component({
  selector: 'app-translation-challenge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="space-y-4">
      <!-- English sentence to translate -->
      <div class="bg-greek-50 border border-greek-100 rounded-xl px-5 py-4">
        <p class="text-xs font-semibold uppercase tracking-widest text-greek-500 mb-1">Translate into Greek</p>
        <p class="text-base text-greek-900 font-medium leading-relaxed">{{ data().english_sentence }}</p>
      </div>

      <!-- Textarea -->
      <textarea
        (input)="onInput($event)"
        [disabled]="submitted()"
        rows="3"
        maxlength="300"
        placeholder="Type your Greek translation here…"
        class="w-full px-4 py-3 rounded-xl border border-surface-200 text-sm text-surface-800 resize-none focus:outline-none focus:ring-2 focus:ring-greek-400 focus:border-transparent disabled:bg-surface-50 disabled:text-surface-400 transition font-serif"
      ></textarea>
      <div class="flex justify-end text-xs"
        [class]="charCount >= 270 ? 'text-red-500' : 'text-surface-400'">
        {{ charCount }} / {{ maxChars }}
      </div>

      <!-- Submit button -->
      @if (!submitted()) {
        <div class="flex justify-end">
          <button
            (click)="submit()"
            [disabled]="!canSubmit()"
            class="px-4 py-2 rounded-lg bg-greek-600 text-white text-xs font-semibold hover:bg-greek-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Submit
          </button>
        </div>
      }

      <!-- Evaluation feedback -->
      @if (submitted()) {
        @if (!evaluation()) {
          <div class="flex items-center gap-3 bg-greek-50 border border-greek-200 rounded-xl px-4 py-3 text-sm text-greek-700">
            <svg class="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            Evaluating your translation…
          </div>
        } @else {
          <div class="rounded-xl border p-4 text-sm"
            [class]="evaluation()!.isCorrect ? 'border-emerald-300 bg-emerald-50' : 'border-amber-200 bg-amber-50'">
            <div class="flex items-center gap-2 mb-2">
              <span class="font-semibold"
                [class]="evaluation()!.isCorrect ? 'text-emerald-700' : 'text-amber-700'">
                Score: {{ evaluation()!.score }}/100
              </span>
              @if (evaluation()!.isCorrect) {
                <svg class="w-4 h-4 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                </svg>
              }
            </div>
            <p [class]="evaluation()!.isCorrect ? 'text-emerald-800' : 'text-amber-800'">
              {{ evaluation()!.feedback }}
            </p>
          </div>

          <!-- Retry button — always available so a failed evaluation (e.g. network
               error) doesn't permanently lock the student out of resubmitting. -->
          <div class="flex justify-end">
            <button
              (click)="retry()"
              class="px-4 py-2 rounded-lg border border-greek-300 text-greek-700 text-xs font-semibold hover:bg-greek-50 transition-colors"
            >
              Try Again
            </button>
          </div>
        }
      }
    </div>
  `,
})
export class TranslationChallengeComponent {
  @Input({ required: true }) exercise!: Exercise;
  @Output() submitted$ = new EventEmitter<string>();
  @Output() answered = new EventEmitter<boolean>();
  @Output() retried = new EventEmitter<void>();

  submitted = signal(false);
  evaluation = signal<EvaluationResult | null>(null);
  answerValue = '';
  readonly maxChars = 300;
  get charCount(): number { return this.answerValue.length; }

  data(): TranslationChallengeData {
    return this.exercise.data as unknown as TranslationChallengeData;
  }

  onInput(event: Event): void {
    this.answerValue = (event.target as HTMLTextAreaElement).value;
  }

  submit(): void {
    if (this.submitted() || !this.answerValue.trim()) return;
    this.submitted.set(true);
    this.submitted$.emit(this.answerValue.trim());
  }

  setEvaluation(result: EvaluationResult): void {
    this.evaluation.set(result);
    this.answered.emit(result.isCorrect);
  }

  /** Reset the card to an answerable state so the student can resubmit
   *  (e.g. after an evaluation request failure). Keeps the typed answer
   *  so they don't have to retype it. */
  retry(): void {
    this.submitted.set(false);
    this.evaluation.set(null);
    this.retried.emit();
  }

  canSubmit(): boolean {
    return this.answerValue.trim().length > 0;
  }
}
