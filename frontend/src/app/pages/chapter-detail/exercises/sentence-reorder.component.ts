import {
  Component, Input, Output, EventEmitter, signal, computed, OnInit, ChangeDetectionStrategy
} from '@angular/core';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { Exercise, SentenceReorderData } from '../../../core/models/firestore.models';

@Component({
  selector: 'app-sentence-reorder',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DragDropModule],
  template: `
    <div class="space-y-4">
      <p class="text-xs font-semibold uppercase tracking-widest text-surface-400">
        Drag words into the correct order, or use Tab + Enter/Space to pick up and place a word.
      </p>

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
        @for (word of words(); track $index; let i = $index) {
          <div
            cdkDrag
            [cdkDragDisabled]="submitted()"
            [attr.tabindex]="submitted() ? null : 0"
            [attr.role]="submitted() ? null : 'button'"
            [attr.aria-pressed]="submitted() ? null : (selectedForMove() === i)"
            [attr.aria-label]="submitted() ? null : tileAriaLabel(word, i)"
            (keydown.enter)="onTileActivate(i)"
            (keydown.space)="$event.preventDefault(); onTileActivate(i)"
            (keydown.escape)="cancelMove()"
            class="px-3 py-2 rounded-lg text-sm font-medium select-none transition-colors"
            [class]="submitted()
              ? (isCorrect() ? 'bg-emerald-500 text-white cursor-default' : 'bg-red-400 text-white cursor-default')
              : (selectedForMove() === i
                ? 'bg-greek-100 border-2 border-greek-500 text-greek-900 shadow-md cursor-grab ring-2 ring-greek-300'
                : 'bg-white border border-greek-300 text-greek-800 shadow-sm cursor-grab active:cursor-grabbing hover:border-greek-500 hover:bg-greek-50')"
          >
            {{ word }}
          </div>
        }
      </div>

      <!-- Screen-reader-only status announcements for keyboard pick-up/place/cancel -->
      <div class="sr-only" aria-live="polite">{{ moveStatusMessage() }}</div>

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

  /** Index (in the current words() order) of the word tile currently
   *  "picked up" via keyboard — the keyboard-operable alternative to CDK
   *  drag-drop (IMP-FE-07). null = nothing picked up. */
  selectedForMove = signal<number | null>(null);
  /** Screen-reader-only status announcements for pick-up/place/cancel actions. */
  moveStatusMessage = signal('');

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

  /**
   * Keyboard-operable "select then place" alternative to dragging (IMP-FE-07):
   *   1. Enter/Space on a word with nothing picked up yet — picks it up.
   *   2. Enter/Space on the SAME word again — cancels the pick-up.
   *   3. Enter/Space on a DIFFERENT word — moves the picked-up word to that position.
   * Escape (bound separately below) always cancels.
   */
  onTileActivate(index: number): void {
    if (this.submitted()) return;
    const picked = this.selectedForMove();

    if (picked === null) {
      this.selectedForMove.set(index);
      this.moveStatusMessage.set(
        `Picked up "${this.words()[index]}". Choose a position to place it, or press Escape to cancel.`
      );
      return;
    }

    if (picked === index) {
      this.cancelMove();
      return;
    }

    const arr = [...this.words()];
    moveItemInArray(arr, picked, index);
    this.words.set(arr);
    this.moveStatusMessage.set(`Moved "${arr[index]}" to position ${index + 1}.`);
    this.selectedForMove.set(null);
  }

  cancelMove(): void {
    if (this.selectedForMove() !== null) {
      this.moveStatusMessage.set('Cancelled.');
    }
    this.selectedForMove.set(null);
  }

  tileAriaLabel(word: string, index: number): string {
    const picked = this.selectedForMove();
    if (picked === index) {
      return `${word}, selected. Press Enter to cancel, or select another word's position to place it here.`;
    }
    if (picked !== null) {
      return `${word}. Press Enter to place the selected word here.`;
    }
    return `${word}. Press Enter or Space to pick up and reorder.`;
  }

  /** Whether the current word order matches the correct order — called
   *  repeatedly from the template (border/tile colors + feedback banner), so
   *  memoized as a computed rather than a plain method. _correctOrder is a
   *  plain field but is only ever assigned once in ngOnInit and never
   *  mutated again, so words() (a real signal) is the only thing that
   *  actually varies — this is behaviorally identical to the previous
   *  plain-method version, just cached until words() changes. */
  isCorrect = computed<boolean>(() => {
    const w = this.words();
    return w.length === this._correctOrder.length && w.every((v, i) => v === this._correctOrder[i]);
  });

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
