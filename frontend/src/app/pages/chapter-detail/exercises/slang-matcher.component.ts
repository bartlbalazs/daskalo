import {
  Component, Input, Output, EventEmitter, signal, computed, OnInit
} from '@angular/core';
import { CdkDragDrop, DragDropModule, moveItemInArray, transferArrayItem } from '@angular/cdk/drag-drop';
import { Exercise, SlangMatcherData } from '../../../core/models/firestore.models';

interface MatchSlot {
  formal: string;
  slang: string | null; // null = empty slot
}

@Component({
  selector: 'app-slang-matcher',
  standalone: true,
  imports: [DragDropModule],
  template: `
    <div class="space-y-5">
      <!-- Unplaced slang bank -->
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-2">Drag the slang expressions to their formal match</p>
        <div
          cdkDropList
          id="slang-bank"
          [cdkDropListData]="bank()"
          [cdkDropListConnectedTo]="slotIds()"
          (cdkDropListDropped)="dropToBank($event)"
          class="min-h-[2.75rem] flex flex-wrap gap-2 rounded-xl border-2 border-dashed border-surface-300 p-3 bg-surface-50"
        >
          @for (item of bank(); track item) {
            <div
              cdkDrag
              class="px-3 py-1.5 rounded-lg bg-greek-600 text-white text-sm font-medium cursor-grab active:cursor-grabbing shadow-sm select-none"
            >
              {{ item }}
            </div>
          }
          @if (bank().length === 0) {
            <span class="text-xs text-surface-400 italic self-center">All expressions placed</span>
          }
        </div>
      </div>

      <!-- Formal ← → Slang rows -->
      <div class="space-y-2.5">
        @for (slot of slots(); track slot.formal; let i = $index) {
          <div class="flex items-center gap-3">
            <!-- Formal phrase -->
            <div class="flex-1 bg-white border rounded-xl px-4 py-2.5 text-sm text-surface-700"
              [class]="submitted() ? (slotCorrect(i) ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50') : 'border-surface-200'">
              {{ slot.formal }}
            </div>

            <!-- Arrow -->
            <svg class="w-4 h-4 text-surface-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
            </svg>

            <!-- Drop target for slang -->
            <div
              cdkDropList
              [id]="'slot-' + i"
              [cdkDropListData]="slotArrayFor(i)"
              [cdkDropListConnectedTo]="['slang-bank'].concat(otherSlotIds(i))"
              (cdkDropListDropped)="dropToSlot($event, i)"
              class="flex-1 min-h-[2.5rem] rounded-xl border-2 border-dashed flex items-center px-3 transition-colors"
              [class]="slotBorderClass(i)"
            >
              @if (slot.slang) {
                <div
                  cdkDrag
                  [cdkDragDisabled]="submitted()"
                  class="px-3 py-1.5 rounded-lg text-sm font-medium cursor-grab active:cursor-grabbing select-none w-full"
                  [class]="submitted() ? (slotCorrect(i) ? 'bg-emerald-500 text-white' : 'bg-red-400 text-white') : 'bg-greek-600 text-white'"
                >
                  {{ slot.slang }}
                </div>
              } @else {
                <span class="text-xs text-surface-400 italic">Drop here</span>
              }
            </div>

            <!-- Result icon -->
            @if (submitted()) {
              @if (slotCorrect(i)) {
                <svg class="w-5 h-5 text-emerald-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                </svg>
              } @else {
                <svg class="w-5 h-5 text-red-400 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
              }
            }
          </div>
        }
      </div>

      <!-- Show correct answers after wrong submission -->
      @if (submitted() && !isAllCorrect()) {
        <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          <p class="font-semibold mb-2">Correct matches:</p>
          <ul class="space-y-1">
            @for (pair of pairs(); track pair.formal) {
              <li><span class="font-medium">{{ pair.formal }}</span> → {{ pair.slang }}</li>
            }
          </ul>
        </div>
      }
    </div>
  `,
})
export class SlangMatcherComponent implements OnInit {
  @Input({ required: true }) exercise!: Exercise;
  @Output() answered = new EventEmitter<boolean>();

  submitted = signal(false);

  private _slots = signal<MatchSlot[]>([]);
  private _bank = signal<string[]>([]);

  slots = this._slots.asReadonly();
  bank = this._bank.asReadonly();

  ngOnInit(): void {
    const pairs = this.pairs();
    this._slots.set(pairs.map(p => ({ formal: p.formal, slang: null })));
    this._bank.set([...pairs.map(p => p.slang)].sort(() => Math.random() - 0.5));
  }

  pairs(): { formal: string; slang: string }[] {
    return (this.exercise.data as unknown as SlangMatcherData)?.pairs ?? [];
  }

  slotIds(): string[] {
    return this.slots().map((_, i) => 'slot-' + i);
  }

  otherSlotIds(exclude: number): string[] {
    return this.slots().map((_, i) => 'slot-' + i).filter((_, i) => i !== exclude);
  }

  slotArrayFor(i: number): string[] {
    const s = this.slots()[i];
    return s?.slang ? [s.slang] : [];
  }

  slotCorrect(i: number): boolean {
    const slot = this.slots()[i];
    const pair = this.pairs()[i];
    return slot?.slang === pair?.slang;
  }

  isAllCorrect(): boolean {
    return this.slots().every((_, i) => this.slotCorrect(i));
  }

  slotBorderClass(i: number): string {
    if (!this.submitted()) {
      const s = this.slots()[i];
      return s?.slang ? 'border-greek-300 bg-greek-50/50' : 'border-surface-300 bg-white';
    }
    return this.slotCorrect(i) ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50';
  }

  dropToSlot(event: CdkDragDrop<string[]>, slotIndex: number): void {
    if (this.submitted()) return;
    const slots = [...this._slots()];
    const bank = [...this._bank()];

    const item: string = event.item.data ?? event.previousContainer.data[event.previousIndex];

    // Return whatever was previously in this slot to the bank
    if (slots[slotIndex].slang) {
      bank.push(slots[slotIndex].slang!);
    }

    // Remove from source
    if (event.previousContainer.id === 'slang-bank') {
      const bi = bank.indexOf(item);
      if (bi !== -1) bank.splice(bi, 1);
    } else {
      // came from another slot
      const srcIndex = parseInt(event.previousContainer.id.split('-')[1], 10);
      slots[srcIndex] = { ...slots[srcIndex], slang: null };
    }

    slots[slotIndex] = { ...slots[slotIndex], slang: item };
    this._slots.set(slots);
    this._bank.set(bank);
  }

  dropToBank(event: CdkDragDrop<string[]>): void {
    if (this.submitted()) return;
    if (event.previousContainer.id === 'slang-bank') {
      moveItemInArray(this._bank(), event.previousIndex, event.currentIndex);
      this._bank.set([...this._bank()]);
      return;
    }
    // Returned from a slot
    const srcIndex = parseInt(event.previousContainer.id.split('-')[1], 10);
    const slots = [...this._slots()];
    const bank = [...this._bank()];
    if (slots[srcIndex].slang) {
      bank.push(slots[srcIndex].slang!);
      slots[srcIndex] = { ...slots[srcIndex], slang: null };
    }
    this._slots.set(slots);
    this._bank.set(bank);
  }

  submit(): void {
    if (this.submitted()) return;
    this.submitted.set(true);
    this.answered.emit(this.isAllCorrect());
  }

  isComplete(): boolean {
    return this._bank().length === 0;
  }
}
