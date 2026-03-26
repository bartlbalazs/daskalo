import { Component, Input, Output, EventEmitter, signal } from '@angular/core';
import { Exercise, PassageComprehensionData, PassageSentence, VocabularyItem } from '../../../core/models/firestore.models';
import { AudioPlayerComponent } from './audio-player.component';
import { HighlightVocabPipe } from '../../../shared/pipes/highlight-vocab.pipe';

interface QState {
  selected: number | null;
}

@Component({
  selector: 'app-passage-comprehension',
  standalone: true,
  imports: [AudioPlayerComponent, HighlightVocabPipe],
  template: `
    <div class="space-y-6">
      <!-- Passage text block — sentence-by-sentence click-to-translate -->
      @if (passage.length > 0) {
        <div class="bg-greek-50 border border-greek-100 rounded-xl p-4 mb-2 font-serif text-greek-900 leading-relaxed text-[15px]">
          <p class="text-xs text-surface-400 mb-2 italic font-sans">Click any sentence to reveal its translation.</p>
          @for (sentence of passage; track $index; let si = $index) {
            <span
              class="cursor-pointer rounded px-0.5 transition-colors duration-150 inline"
              [class]="revealed().has(si) ? 'bg-amber-100 text-amber-900' : 'hover:bg-greek-100'"
              (click)="toggleSentence(si)"
              [title]="revealed().has(si) ? sentence.english : 'Click to translate'"
              [innerHTML]="(sentence.greek + ' ') | highlightVocab:vocabulary"
            ></span>
            @if (revealed().has(si)) {
              <span class="inline-block text-xs text-amber-700 italic ml-1 mr-2 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
                {{ sentence.english }}
              </span>
            }
          }
        </div>
      } @else if (passageText) {
        <!-- Legacy fallback for old string-based passage -->
        <div class="bg-greek-50 border border-greek-100 rounded-xl p-4 mb-2 font-serif text-greek-900 leading-relaxed text-[15px]"
             [innerHTML]="passageText | highlightVocab:vocabulary">
        </div>
      }

      <!-- Passage audio player -->
      @if (passageAudioUrl) {
        <app-audio-player [src]="passageAudioUrl" />
      }

      @for (q of data().questions; track $index; let qi = $index) {
        <div class="space-y-3">
          <p class="text-base font-medium text-surface-800">{{ qi + 1 }}. {{ q.question }}</p>

          <div class="space-y-2">
            @for (opt of q.options; track $index; let oi = $index) {
              <button
                (click)="select(qi, oi)"
                [disabled]="submitted()"
                class="w-full text-left px-4 py-2.5 rounded-xl border text-sm transition-all duration-150 flex items-center gap-3"
                [class]="optionClass(qi, oi)"
              >
                <span class="w-6 h-6 rounded-full border text-xs font-semibold flex items-center justify-center shrink-0"
                  [class]="badgeClass(qi, oi)">
                  {{ optionLetter(oi) }}
                </span>
                <span class="flex-1">{{ opt.text }}</span>
                @if (submitted()) {
                  @if (qState(qi).selected === oi && opt.isCorrect) {
                    <svg class="w-4 h-4 text-emerald-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                    </svg>
                  } @else if (qState(qi).selected === oi && !opt.isCorrect) {
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
      }
    </div>
  `,
})
export class PassageComprehensionComponent {
  @Input({ required: true }) exercise!: Exercise;
  /** Full GCS URL of the passage audio, e.g. gs://bucket/chapters/chapterId/passage.mp3 */
  @Input() passageAudioUrl = '';
  /** Structured passage sentences for click-to-translate (preferred). */
  @Input() passage: PassageSentence[] = [];
  /** Legacy plain-text passage string (fallback for older chapters). */
  @Input() passageText = '';
  @Input() vocabulary: VocabularyItem[] = [];
  @Output() answered = new EventEmitter<boolean>();

  submitted = signal(false);
  /** Set of sentence indices whose English translation is currently revealed. */
  revealed = signal<Set<number>>(new Set());
  private _states = signal<QState[]>([]);
  private _initialized = false;

  toggleSentence(index: number): void {
    this.revealed.update(s => {
      const next = new Set(s);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }

  data(): PassageComprehensionData {
    this._ensureInit();
    return this.exercise.data as unknown as PassageComprehensionData;
  }

  qState(qi: number): QState {
    this._ensureInit();
    return this._states()[qi] ?? { selected: null };
  }

  select(qi: number, oi: number): void {
    if (this.submitted()) return;
    this._ensureInit();
    const states = [...this._states()];
    states[qi] = { selected: oi };
    this._states.set(states);
  }

  submit(): void {
    if (this.submitted()) return;
    this.submitted.set(true);
    const correct = this.data().questions.every((q, qi) => {
      const s = this._states()[qi];
      return s && s.selected !== null && q.options[s.selected]?.isCorrect;
    });
    this.answered.emit(correct);
  }

  isAllAnswered(): boolean {
    this._ensureInit();
    return this._states().every(s => s.selected !== null);
  }

  isCorrect(): boolean {
    return this.data().questions.every((q, qi) => {
      const s = this._states()[qi];
      return s && s.selected !== null && q.options[s.selected]?.isCorrect;
    });
  }

  optionClass(qi: number, oi: number): string {
    if (!this.submitted()) {
      return this.qState(qi).selected === oi
        ? 'border-greek-500 bg-greek-50 text-greek-800'
        : 'border-surface-200 bg-white text-surface-700 hover:border-greek-300 hover:bg-greek-50/50';
    }
    const opt = this.data().questions[qi].options[oi];
    if (opt.isCorrect) return 'border-emerald-300 bg-emerald-50 text-emerald-800';
    if (this.qState(qi).selected === oi) return 'border-red-300 bg-red-50 text-red-800';
    return 'border-surface-100 bg-surface-50 text-surface-400';
  }

  badgeClass(qi: number, oi: number): string {
    if (!this.submitted()) {
      return this.qState(qi).selected === oi
        ? 'border-greek-500 bg-greek-500 text-white'
        : 'border-surface-300 text-surface-500';
    }
    const opt = this.data().questions[qi].options[oi];
    if (opt.isCorrect) return 'border-emerald-400 bg-emerald-400 text-white';
    if (this.qState(qi).selected === oi) return 'border-red-400 bg-red-400 text-white';
    return 'border-surface-200 text-surface-300';
  }

  optionLetter(index: number): string {
    return String.fromCharCode(65 + index);
  }

  private _ensureInit(): void {
    if (this._initialized) return;
    this._initialized = true;
    const d = this.exercise.data as unknown as PassageComprehensionData;
    // Shuffle options for each question in-place so indices remain consistent
    (d?.questions ?? []).forEach(q => {
      q.options = this._shuffle(q.options);
    });
    this._states.set((d?.questions ?? []).map(() => ({ selected: null })));
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
