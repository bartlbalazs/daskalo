import { Component, Input, Output, EventEmitter, signal } from '@angular/core';
import { Exercise, DictationData, EvaluationResult } from '../../../core/models/firestore.models';
import { AudioPlayerComponent } from './audio-player.component';

@Component({
  selector: 'app-dictation',
  standalone: true,
  imports: [AudioPlayerComponent],
  template: `
    <div class="space-y-4">
      <!-- Instructions -->
      <p class="text-sm text-surface-500 italic">
        Listen carefully to the audio clip, then type exactly what you hear in Greek.
      </p>

      <!-- Audio player -->
      @if (audioUrl()) {
        <app-audio-player [src]="audioUrl()!" />
      } @else {
        <div class="bg-surface-100 rounded-xl px-4 py-3 text-sm text-surface-400 italic">
          Audio not available.
        </div>
      }

      <!-- Textarea -->
      <textarea
        [(value)]="answerValue"
        (input)="onInput($event)"
        [disabled]="submitted()"
        rows="3"
        placeholder="Type what you hear in Greek…"
        class="w-full px-4 py-3 rounded-xl border border-surface-200 text-sm text-surface-800 resize-none focus:outline-none focus:ring-2 focus:ring-greek-400 focus:border-transparent disabled:bg-surface-50 disabled:text-surface-400 transition font-serif"
      ></textarea>

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
            Checking your transcription…
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
        }
      }
    </div>
  `,
})
export class DictationComponent {
  @Input({ required: true }) exercise!: Exercise;
  @Input() chapterStoragePath = '';
  @Input() sentenceAudioUrls: string[] = [];
  @Output() submitted$ = new EventEmitter<string>();
  @Output() answered = new EventEmitter<boolean>();

  submitted = signal(false);
  evaluation = signal<EvaluationResult | null>(null);
  answerValue = '';

  data(): DictationData {
    return this.exercise.data as unknown as DictationData;
  }

  audioUrl(): string | null {
    const idx = this.data()?.sentence_index ?? 0;
    // Prefer exact URL from sentenceAudioUrls if available and non-empty
    const exact = this.sentenceAudioUrls?.[idx];
    if (exact) return exact;
    // Fallback: construct from chapterStoragePath (legacy, likely wrong for prefixed files)
    if (!this.chapterStoragePath) return null;
    const padded = String(idx).padStart(2, '0');
    return `${this.chapterStoragePath}/sentence_${padded}.mp3`;
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

  canSubmit(): boolean {
    return this.answerValue.trim().length > 0;
  }
}
