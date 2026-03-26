import { Component, Input, Output, EventEmitter, signal, OnInit } from '@angular/core';
import { Exercise, ListeningComprehensionData, ListeningOption } from '../../../core/models/firestore.models';
import { AudioPlayerComponent } from './audio-player.component';

@Component({
  selector: 'app-listening-comprehension',
  standalone: true,
  imports: [AudioPlayerComponent],
  template: `
    <div class="space-y-4">
      <!-- Audio player -->
      @if (audioUrl()) {
        <app-audio-player [src]="audioUrl()!" />
      } @else {
        <div class="bg-surface-100 rounded-xl px-4 py-3 text-sm text-surface-400 italic">
          Audio not available for this exercise.
        </div>
      }

      <!-- Question -->
      <p class="text-base font-medium text-surface-800">{{ data().question }}</p>

      <!-- Options -->
      <div class="space-y-2.5">
        @for (opt of options(); track $index) {
          <button
            (click)="select($index)"
            [disabled]="submitted()"
            class="w-full text-left px-4 py-3 rounded-xl border text-sm transition-all duration-150 flex items-center gap-3"
            [class]="optionClass($index)"
          >
            <span class="w-6 h-6 rounded-full border text-xs font-semibold flex items-center justify-center shrink-0"
              [class]="badgeClass($index)">
              {{ optionLetter($index) }}
            </span>
            <span class="flex-1">{{ opt.text }}</span>
            @if (submitted()) {
              @if (selectedIndex() === $index && opt.isCorrect) {
                <svg class="w-4 h-4 text-emerald-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                </svg>
              } @else if (selectedIndex() === $index && !opt.isCorrect) {
                <svg class="w-4 h-4 text-red-400 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
              } @else if (opt.isCorrect) {
                <svg class="w-4 h-4 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
              }
            }
          </button>
        }
      </div>
    </div>
  `,
})
export class ListeningComprehensionComponent implements OnInit {
  @Input({ required: true }) exercise!: Exercise;
  /** Base GCS path of the chapter, e.g. gs://bucket/chapters/chapterId */
  @Input() chapterStoragePath = '';
  /** Exact resolved GCS URLs for each sentence audio file. */
  @Input() sentenceAudioUrls: string[] = [];
  @Output() answered = new EventEmitter<boolean>();

  selectedIndex = signal<number | null>(null);
  submitted = signal(false);
  private _options = signal<ListeningOption[]>([]);

  ngOnInit(): void {
    const raw = (this.exercise.data as unknown as ListeningComprehensionData)?.options ?? [];
    this._options.set(this._shuffle(raw));
  }

  options(): ListeningOption[] {
    return this._options();
  }

  data(): ListeningComprehensionData {
    return this.exercise.data as unknown as ListeningComprehensionData;
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

  select(index: number): void {
    if (this.submitted()) return;
    this.selectedIndex.set(index);
  }

  submit(): void {
    if (this.selectedIndex() === null || this.submitted()) return;
    this.submitted.set(true);
    const correct = this.options()[this.selectedIndex()!]?.isCorrect ?? false;
    this.answered.emit(correct);
  }

  isCorrect(): boolean {
    if (!this.submitted() || this.selectedIndex() === null) return false;
    return this.options()[this.selectedIndex()!]?.isCorrect ?? false;
  }

  optionClass(index: number): string {
    if (!this.submitted()) {
      return this.selectedIndex() === index
        ? 'border-greek-500 bg-greek-50 text-greek-800'
        : 'border-surface-200 bg-white text-surface-700 hover:border-greek-300 hover:bg-greek-50/50';
    }
    const opt = this.options()[index];
    if (opt.isCorrect) return 'border-emerald-300 bg-emerald-50 text-emerald-800';
    if (this.selectedIndex() === index) return 'border-red-300 bg-red-50 text-red-800';
    return 'border-surface-100 bg-surface-50 text-surface-400';
  }

  badgeClass(index: number): string {
    if (!this.submitted()) {
      return this.selectedIndex() === index
        ? 'border-greek-500 bg-greek-500 text-white'
        : 'border-surface-300 text-surface-500';
    }
    const opt = this.options()[index];
    if (opt.isCorrect) return 'border-emerald-400 bg-emerald-400 text-white';
    if (this.selectedIndex() === index) return 'border-red-400 bg-red-400 text-white';
    return 'border-surface-200 text-surface-300';
  }

  optionLetter(index: number): string {
    return String.fromCharCode(65 + index);
  }

  private _shuffle<T>(arr: T[]): T[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
}
