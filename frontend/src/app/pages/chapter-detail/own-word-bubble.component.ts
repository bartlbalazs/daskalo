import { Component, Input, signal, inject } from '@angular/core';
import { OwnWordsService } from '../../core/services/own-words.service';

type BubbleState = 'idle' | 'open' | 'submitting' | 'success' | 'error';

@Component({
  selector: 'app-own-word-bubble',
  standalone: true,
  imports: [],
  template: `
    <!-- Floating bubble button (fixed bottom-right) -->
    <div class="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">

      <!-- Expanded card -->
      @if (state() !== 'idle') {
        <div class="bg-white rounded-2xl shadow-2xl border border-greek-100 p-5 w-80 animate-in fade-in slide-in-from-bottom-4 duration-200">

          <!-- Header -->
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <!-- Pencil icon -->
              <div class="w-7 h-7 rounded-lg bg-greek-600 flex items-center justify-center">
                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
                </svg>
              </div>
              <p class="font-semibold text-greek-900 text-sm">Add Your Own Word</p>
            </div>
            <button
              (click)="close()"
              class="w-7 h-7 rounded-full flex items-center justify-center text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors"
              title="Close"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          @if (state() === 'success') {
            <!-- Success state -->
            <div class="flex flex-col items-center py-4 text-center">
              <div class="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center mb-3">
                <svg class="w-6 h-6 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                </svg>
              </div>
              <p class="font-semibold text-emerald-800 text-sm mb-0.5">Word added!</p>
              <p class="text-emerald-700 text-xs">
                <span class="font-bold font-serif text-base">{{ successGreek() }}</span>
                @if (successEnglish()) { — {{ successEnglish() }} }
              </p>
              <button
                (click)="resetToOpen()"
                class="mt-4 text-xs text-greek-600 hover:text-greek-800 font-medium underline underline-offset-2 transition-colors"
              >
                Add another word
              </button>
            </div>

          } @else {
            <!-- Input state (open / submitting / error) -->
            <p class="text-xs text-surface-500 mb-3 leading-snug">
              Enter a Greek word or phrase from this chapter that you want to remember. We'll translate and create audio for it.
            </p>

            <div class="relative mb-1">
              <input
                #wordInput
                type="text"
                [value]="inputText()"
                (input)="onInput($any($event.target).value)"
                (keydown.enter)="onSubmit()"
                placeholder="e.g. καλημέρα"
                maxlength="50"
                [disabled]="state() === 'submitting'"
                class="w-full border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-greek-400 focus:border-transparent transition-shadow pr-12 disabled:opacity-60"
                [class]="state() === 'error'
                  ? 'border-red-300 bg-red-50'
                  : 'border-surface-200 bg-white'"
              />
              <!-- Char counter -->
              <span class="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-medium pointer-events-none"
                [class]="inputText().length >= 45 ? 'text-amber-500' : 'text-surface-300'">
                {{ inputText().length }}/50
              </span>
            </div>

            @if (state() === 'error' && errorMessage()) {
              <p class="text-xs text-red-600 mb-2 leading-snug">{{ errorMessage() }}</p>
            }

            <button
              (click)="onSubmit()"
              [disabled]="state() === 'submitting' || inputText().trim().length === 0"
              class="w-full mt-2 py-2.5 rounded-xl bg-greek-600 text-white font-semibold text-sm hover:bg-greek-700 active:scale-95 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              @if (state() === 'submitting') {
                <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
                Processing…
              } @else {
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                </svg>
                Add Word
              }
            </button>
          }
        </div>
      }

      <!-- Floating action button -->
      <button
        (click)="toggle()"
        class="w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all active:scale-90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-greek-500"
        [class]="state() !== 'idle'
          ? 'bg-greek-700 text-white hover:bg-greek-800'
          : 'bg-greek-600 text-white hover:bg-greek-700'"
        title="Add your own word"
      >
        <!-- Pencil icon -->
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
        </svg>
      </button>
    </div>
  `,
})
export class OwnWordBubbleComponent {
  @Input({ required: true }) chapterId!: string;
  @Input({ required: true }) bookId!: string;

  private ownWordsService = inject(OwnWordsService);

  state = signal<BubbleState>('idle');
  inputText = signal('');
  errorMessage = signal<string | null>(null);
  successGreek = signal('');
  successEnglish = signal('');

  toggle(): void {
    if (this.state() !== 'idle') {
      this.close();
    } else {
      this.state.set('open');
    }
  }

  close(): void {
    this.state.set('idle');
    this.inputText.set('');
    this.errorMessage.set(null);
  }

  resetToOpen(): void {
    this.state.set('open');
    this.inputText.set('');
    this.errorMessage.set(null);
  }

  onInput(value: string): void {
    this.inputText.set(value);
    // Clear error on new input
    if (this.state() === 'error') {
      this.state.set('open');
      this.errorMessage.set(null);
    }
  }

  async onSubmit(): Promise<void> {
    const text = this.inputText().trim();
    if (!text || this.state() === 'submitting') return;

    this.state.set('submitting');
    this.errorMessage.set(null);

    try {
      const result = await this.ownWordsService.addOwnWord(text, this.chapterId, this.bookId);
      this.successGreek.set(result.greek);
      this.successEnglish.set(result.english);
      this.state.set('success');
    } catch (err) {
      this.errorMessage.set(
        err instanceof Error ? err.message : 'Something went wrong. Please try again.'
      );
      this.state.set('error');
    }
  }
}
