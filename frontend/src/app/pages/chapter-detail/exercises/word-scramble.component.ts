import {
  Component, Input, Output, EventEmitter, signal, OnInit
} from '@angular/core';
import { Exercise, WordScrambleData } from '../../../core/models/firestore.models';

@Component({
  selector: 'app-word-scramble',
  standalone: true,
  template: `
    <div class="space-y-4">
      <!-- Scrambled letters -->
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-2">Scrambled letters</p>
        <div class="flex flex-wrap gap-2">
          @for (letter of scrambledLetters(); track $index) {
            <button
              (click)="pickLetter($index)"
              [disabled]="usedIndices().has($index) || submitted()"
              class="w-10 h-10 rounded-lg border-2 font-serif text-lg font-semibold transition-all duration-100"
              [class]="usedIndices().has($index)
                ? 'border-surface-200 text-surface-300 bg-surface-50 cursor-default'
                : 'border-greek-400 text-greek-700 bg-greek-50 hover:bg-greek-100 hover:border-greek-500'"
            >
              {{ letter }}
            </button>
          }
        </div>
      </div>

      <!-- User's answer -->
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-2">Your answer</p>
        <div class="flex flex-wrap gap-2 min-h-[3rem] bg-surface-50 border-2 rounded-xl p-2"
          [class]="submitted()
            ? (isCorrect() ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50')
            : 'border-surface-200'">
          @for (item of answer(); track $index) {
            <button
              (click)="removeLetter($index)"
              [disabled]="submitted()"
              class="w-10 h-10 rounded-lg border-2 font-serif text-lg font-semibold transition-all duration-100"
              [class]="submitted()
                ? (isCorrect() ? 'border-emerald-400 text-emerald-700 bg-emerald-100 cursor-default' : 'border-red-400 text-red-700 bg-red-100 cursor-default')
                : 'border-greek-500 text-greek-700 bg-greek-100 hover:bg-red-50 hover:border-red-300'"
            >
              {{ item.letter }}
            </button>
          }
          @if (answer().length === 0 && !submitted()) {
            <span class="text-xs text-surface-400 italic self-center px-1">Click letters above to build the word</span>
          }
        </div>
      </div>

      <!-- Feedback -->
      @if (submitted()) {
        @if (isCorrect()) {
          <div class="flex items-center gap-2 text-emerald-700 text-sm font-medium">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
            </svg>
            Correct! The word is <span class="font-semibold font-serif">{{ correctWord() }}</span>
          </div>
        } @else {
          <div class="flex items-center gap-2 text-red-700 text-sm">
            <svg class="w-5 h-5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
            </svg>
            The correct answer is <span class="font-semibold font-serif ml-1">{{ correctWord() }}</span>
          </div>
        }
      }

      <!-- Clear button -->
      @if (!submitted() && answer().length > 0) {
        <button (click)="clear()" class="text-xs text-surface-400 hover:text-surface-600 transition-colors underline">
          Clear
        </button>
      }
    </div>
  `,
})
export class WordScrambleComponent implements OnInit {
  @Input({ required: true }) exercise!: Exercise;
  @Output() answered = new EventEmitter<boolean>();

  scrambledLetters = signal<string[]>([]);
  usedIndices = signal<Set<number>>(new Set());
  answer = signal<{ letter: string; srcIndex: number }[]>([]);
  submitted = signal(false);

  ngOnInit(): void {
    const d = this.exercise.data as unknown as WordScrambleData;
    const word = d?.word ?? '';
    // Ignore the LLM-generated scrambled field — the LLM often drops or adds letters.
    // Shuffle the correct word's characters ourselves so the set is always exactly right.
    this.scrambledLetters.set(this._shuffle(word.split('')));
  }

  correctWord(): string {
    return (this.exercise.data as unknown as WordScrambleData)?.word ?? '';
  }

  pickLetter(index: number): void {
    if (this.usedIndices().has(index) || this.submitted()) return;
    const used = new Set(this.usedIndices());
    used.add(index);
    this.usedIndices.set(used);
    this.answer.update(a => [...a, { letter: this.scrambledLetters()[index], srcIndex: index }]);
  }

  removeLetter(answerIndex: number): void {
    if (this.submitted()) return;
    const item = this.answer()[answerIndex];
    const used = new Set(this.usedIndices());
    used.delete(item.srcIndex);
    this.usedIndices.set(used);
    this.answer.update(a => a.filter((_, i) => i !== answerIndex));
  }

  clear(): void {
    this.usedIndices.set(new Set());
    this.answer.set([]);
  }

  isCorrect(): boolean {
    return this.answer().map(a => a.letter).join('') === this.correctWord();
  }

  submit(): void {
    if (this.submitted()) return;
    this.submitted.set(true);
    this.answered.emit(this.isCorrect());
  }

  /** Fisher-Yates shuffle — returns a new array with elements in random order. */
  private _shuffle<T>(arr: T[]): T[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
}
