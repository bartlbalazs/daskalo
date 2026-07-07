import {
  Component, Input, Output, EventEmitter, signal, computed, OnInit, ChangeDetectionStrategy
} from '@angular/core';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { Exercise, SlangMatcherData } from '../../../core/models/firestore.models';

interface MatchSlot {
  formal: string;
  slang: string | null; // null = empty slot
}

@Component({
  selector: 'app-slang-matcher',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DragDropModule],
  template: `
    <div class="space-y-5">
      <!-- Unplaced slang bank -->
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-2">
          Drag the slang expressions to their formal match, or use Tab + Enter/Space to pick up and place one.
        </p>
        <div
          cdkDropList
          id="slang-bank"
          [cdkDropListData]="bank()"
          [cdkDropListConnectedTo]="slotIds()"
          (cdkDropListDropped)="dropToBank($event)"
          [attr.tabindex]="submitted() ? null : 0"
          [attr.role]="submitted() ? null : 'button'"
          [attr.aria-label]="submitted() ? null : bankZoneAriaLabel()"
          (keydown.enter)="activateBankZone()"
          (keydown.space)="$event.preventDefault(); activateBankZone()"
          (keydown.escape)="cancelSelection()"
          class="min-h-[2.75rem] flex flex-wrap gap-2 rounded-xl border-2 border-dashed border-surface-300 p-3 bg-surface-50"
        >
          @for (item of bank(); track item) {
            <div
              cdkDrag
              [attr.tabindex]="submitted() ? null : 0"
              [attr.role]="submitted() ? null : 'button'"
              [attr.aria-pressed]="submitted() ? null : isBankItemSelected(item)"
              [attr.aria-label]="submitted() ? null : bankItemAriaLabel(item)"
              (keydown.enter)="$event.stopPropagation(); activateBankItem(item)"
              (keydown.space)="$event.preventDefault(); $event.stopPropagation(); activateBankItem(item)"
              (keydown.escape)="$event.stopPropagation(); cancelSelection()"
              class="px-3 py-1.5 rounded-lg text-sm font-medium cursor-grab active:cursor-grabbing shadow-sm select-none transition-colors"
              [class]="isBankItemSelected(item)
                ? 'bg-greek-800 text-white ring-2 ring-greek-400'
                : 'bg-greek-600 text-white'"
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
              [attr.tabindex]="submitted() ? null : 0"
              [attr.role]="submitted() ? null : 'button'"
              [attr.aria-pressed]="submitted() ? null : (selectedSlang()?.from === i)"
              [attr.aria-label]="submitted() ? null : slotAriaLabel(slot, i)"
              (keydown.enter)="activateSlot(i)"
              (keydown.space)="$event.preventDefault(); activateSlot(i)"
              (keydown.escape)="cancelSelection()"
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

      <!-- Screen-reader-only status announcements for keyboard pick-up/place/cancel -->
      <div class="sr-only" aria-live="polite">{{ statusMessage() }}</div>

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

  /** Currently "picked up" slang word for keyboard-based placement — the
   *  keyboard-operable alternative to CDK drag-drop (IMP-FE-07). Tracks
   *  where the word came from ('bank' or a slot index) so cancelling or
   *  placing elsewhere can put things back correctly. */
  selectedSlang = signal<{ value: string; from: 'bank' | number } | null>(null);
  /** Screen-reader-only status announcements for pick-up/place/cancel actions. */
  statusMessage = signal('');

  ngOnInit(): void {
    const pairs = this.pairs();
    this._slots.set(pairs.map(p => ({ formal: p.formal, slang: null })));
    this._bank.set([...pairs.map(p => p.slang)].sort(() => Math.random() - 0.5));
  }

  pairs(): { formal: string; slang: string }[] {
    return (this.exercise.data as unknown as SlangMatcherData)?.pairs ?? [];
  }

  /** DOM ids of every slot's drop list — used to connect the slang bank and
   *  every other slot as valid drop targets for cross-list dragging. */
  slotIds = computed<string[]>(() => this.slots().map((_, i) => 'slot-' + i));

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
    if (this.submitted()) {
      return this.slotCorrect(i) ? 'border-emerald-300 bg-emerald-50' : 'border-red-300 bg-red-50';
    }
    if (this.selectedSlang()?.from === i) {
      return 'border-greek-500 bg-greek-50 ring-2 ring-greek-300';
    }
    const s = this.slots()[i];
    return s?.slang ? 'border-greek-300 bg-greek-50/50' : 'border-surface-300 bg-white';
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

  // ---------------------------------------------------------------------------
  // Keyboard-operable "select then place" alternative to dragging (IMP-FE-07)
  // ---------------------------------------------------------------------------

  isBankItemSelected(value: string): boolean {
    const picked = this.selectedSlang();
    return picked?.from === 'bank' && picked.value === value;
  }

  /** Activate a bank word: picks it up, switches the pick-up to it, or cancels. */
  activateBankItem(value: string): void {
    if (this.submitted()) return;
    if (this.isBankItemSelected(value)) {
      this.cancelSelection();
      return;
    }
    this.selectedSlang.set({ value, from: 'bank' });
    this.statusMessage.set(
      `Picked up "${value}" from the word bank. Choose a slot to place it, or press Escape to cancel.`
    );
  }

  /** Activate a slot: picks up its word, places a held word here, or cancels. */
  activateSlot(index: number): void {
    if (this.submitted()) return;
    const picked = this.selectedSlang();

    if (picked === null) {
      const slot = this.slots()[index];
      if (slot?.slang) {
        this.selectedSlang.set({ value: slot.slang, from: index });
        this.statusMessage.set(
          `Picked up "${slot.slang}". Choose a slot to place it, or press Escape to cancel.`
        );
      }
      return;
    }

    if (picked.from === index) {
      this.cancelSelection();
      return;
    }

    const slots = [...this._slots()];
    const bank = [...this._bank()];

    // Displace whatever is currently in the target slot back to the bank
    // (mirrors dropToSlot()'s swap behaviour for pointer drag-drop).
    if (slots[index].slang) bank.push(slots[index].slang!);

    if (picked.from === 'bank') {
      const bi = bank.indexOf(picked.value);
      if (bi !== -1) bank.splice(bi, 1);
    } else {
      slots[picked.from] = { ...slots[picked.from], slang: null };
    }

    slots[index] = { ...slots[index], slang: picked.value };
    this._slots.set(slots);
    this._bank.set(bank);
    this.statusMessage.set(`Placed "${picked.value}" next to "${slots[index].formal}".`);
    this.selectedSlang.set(null);
  }

  /** Activate the word-bank drop zone itself: returns a held slot word to the bank. */
  activateBankZone(): void {
    if (this.submitted()) return;
    const picked = this.selectedSlang();
    if (!picked || picked.from === 'bank') {
      this.cancelSelection();
      return;
    }

    const slots = [...this._slots()];
    const bank = [...this._bank(), picked.value];
    slots[picked.from] = { ...slots[picked.from], slang: null };
    this._slots.set(slots);
    this._bank.set(bank);
    this.statusMessage.set(`Returned "${picked.value}" to the word bank.`);
    this.selectedSlang.set(null);
  }

  cancelSelection(): void {
    if (this.selectedSlang()) {
      this.statusMessage.set('Cancelled.');
    }
    this.selectedSlang.set(null);
  }

  bankZoneAriaLabel(): string {
    const picked = this.selectedSlang();
    if (picked && picked.from !== 'bank') {
      return `Word bank. Press Enter to return "${picked.value}" here.`;
    }
    return 'Word bank.';
  }

  bankItemAriaLabel(value: string): string {
    if (this.isBankItemSelected(value)) {
      return `${value}, selected. Press Enter to cancel.`;
    }
    return `${value}. Press Enter or Space to pick up.`;
  }

  slotAriaLabel(slot: MatchSlot, index: number): string {
    const picked = this.selectedSlang();
    const base = slot.slang ? `${slot.formal}: currently matched with ${slot.slang}.` : `${slot.formal}: empty.`;

    if (picked?.from === index) {
      return `${base} Selected for moving. Press Enter to cancel.`;
    }
    if (picked) {
      return `${base} Press Enter to place "${picked.value}" here.`;
    }
    return slot.slang ? `${base} Press Enter to pick up "${slot.slang}".` : `${base} Nothing to pick up here.`;
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
