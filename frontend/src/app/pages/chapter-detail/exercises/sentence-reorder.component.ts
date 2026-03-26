import {
  Component, Input, Output, EventEmitter, signal, OnInit
} from '@angular/core';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { Exercise, SentenceReorderData } from '../../../core/models/firestore.models';

@Component({
  selector: 'app-sentence-reorder',
  standalone: true,
  imports: [DragDropModule],
  template: `
    <div class="space-y-4">
      <p class="text-xs font-semibold uppercase tracking-widest text-surface-400">Drag words into the correct order</p>

      <!-- Drag list -->
      <div
        cdkDropList
        cdkDropListOrientation="mixed"
        [cdkDropListData]="words()"
        (cdkDropListDropped)="drop($event)"
        class="flex flex-wrap gap-2 min-h-[3.5rem] rounded-xl border-2 border-dashed p-3 transition-colors"
        [class]="submitted()
          ? (isCorrect() ? 'border-emerald-300 bg-emerald-50' : 'border-red-200 bg-red-50')
          : 'border-surface-300 bg-surface-50'"
      >
        @for (word of words(); track $index) {
          <div
            cdkDrag
            [cdkDragDisabled]="submitted()"
            class="px-3 py-2 rounded-lg text-sm font-medium select-none transition-colors"
            [class]="submitted()
              ? (isCorrect() ? 'bg-emerald-500 text-white cursor-default' : 'bg-red-400 text-white cursor-default')
              : 'bg-white border border-greek-300 text-greek-800 shadow-sm cursor-grab active:cursor-grabbing hover:border-greek-500 hover:bg-greek-50'"
          >
            {{ word }}
          </div>
        }
      </div>

      <!-- Feedback -->
      @if (submitted()) {
        @if (isCorrect()) {
          <div class="flex items-center gap-2 text-emerald-700 text-sm font-medium">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
            </svg>
            Correct order!
          </div>
        } @else {
          <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
            <p class="font-semibold mb-1">Correct order:</p>
            <p class="font-serif">{{ correctOrderStr() }}</p>
          </div>
        }
      }
    </div>
  `,
})
export class SentenceReorderComponent implements OnInit {
  @Input({ required: true }) exercise!: Exercise;
  @Output() answered = new EventEmitter<boolean>();

  words = signal<string[]>([]);
  submitted = signal(false);

  private _correctOrder: string[] = [];

  ngOnInit(): void {
    const d = this.exercise.data as unknown as SentenceReorderData;
    this._correctOrder = d?.correct_order ?? [];
    // Ignore the LLM-generated scrambled_order — it may have mismatched capitalisation
    // or punctuation. Instead shuffle correct_order locally so the pieces always match.
    this.words.set(this._shuffle([...this._correctOrder]));
  }

  drop(event: CdkDragDrop<string[]>): void {
    if (this.submitted()) return;
    const arr = [...this.words()];
    moveItemInArray(arr, event.previousIndex, event.currentIndex);
    this.words.set(arr);
  }

  isCorrect(): boolean {
    const w = this.words();
    return w.length === this._correctOrder.length && w.every((v, i) => v === this._correctOrder[i]);
  }

  correctOrderStr(): string {
    return this._correctOrder.join(' ');
  }

  submit(): void {
    if (this.submitted()) return;
    this.submitted.set(true);
    this.answered.emit(this.isCorrect());
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
