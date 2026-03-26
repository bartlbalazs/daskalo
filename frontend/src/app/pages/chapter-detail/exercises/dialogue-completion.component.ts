import { Component, Input, Output, EventEmitter, signal, OnInit } from '@angular/core';
import { Exercise, DialogueCompletionData, DialogueCompletionOption, VocabularyItem } from '../../../core/models/firestore.models';
import { HighlightVocabPipe } from '../../../shared/pipes/highlight-vocab.pipe';

@Component({
  selector: 'app-dialogue-completion',
  standalone: true,
  imports: [HighlightVocabPipe],
  template: `
    <div class="space-y-4">
      <!-- Dialogue display -->
      <div class="bg-surface-50 border border-surface-200 rounded-xl p-4 space-y-2">
        @for (line of data().dialogue; track $index) {
          @if (line === '___') {
            <div class="flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-greek-500 shrink-0"></span>
              <span class="flex-1 bg-greek-100 border border-greek-300 rounded-lg px-3 py-1.5 text-sm text-greek-800 font-medium min-h-[2rem] flex items-center italic">
                {{ selectedText() ?? '...' }}
              </span>
            </div>
          } @else {
            <div class="flex items-start gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-surface-400 shrink-0 mt-2"></span>
              <p class="text-sm text-surface-700 leading-relaxed"
                 [innerHTML]="line | highlightVocab:vocabulary"></p>
            </div>
          }
        }
      </div>

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
export class DialogueCompletionComponent implements OnInit {
  @Input({ required: true }) exercise!: Exercise;
  @Input() vocabulary: VocabularyItem[] = [];
  @Output() answered = new EventEmitter<boolean>();

  selectedIndex = signal<number | null>(null);
  submitted = signal(false);
  private _options = signal<DialogueCompletionOption[]>([]);

  ngOnInit(): void {
    const raw = (this.exercise.data as unknown as DialogueCompletionData)?.options ?? [];
    this._options.set(this._shuffle(raw));
  }

  options(): DialogueCompletionOption[] {
    return this._options();
  }

  data(): DialogueCompletionData {
    return this.exercise.data as unknown as DialogueCompletionData;
  }

  selectedText(): string | null {
    const i = this.selectedIndex();
    return i !== null ? this.options()[i]?.text ?? null : null;
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
