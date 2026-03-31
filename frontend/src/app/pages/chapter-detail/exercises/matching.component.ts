import { Component, Input, Output, EventEmitter, signal, OnInit } from '@angular/core';
import { Exercise, MatchingData } from '../../../core/models/firestore.models';

interface MatchingPairWithAudio {
  greek: string;
  english: string;
  audioUrl?: string;
}

type PairState = 'idle' | 'selected' | 'correct' | 'error';

@Component({
  selector: 'app-matching',
  standalone: true,
  styles: [`
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      20%       { transform: translateX(-6px); }
      40%       { transform: translateX(6px); }
      60%       { transform: translateX(-4px); }
      80%       { transform: translateX(4px); }
    }
    .shake { animation: shake 0.4s ease; }
  `],
  template: `
    <div class="grid grid-cols-2 gap-3">
      <!-- Greek column (left) -->
      <div class="space-y-2">
        @for (pair of shuffledGreek(); track pair.idx) {
          <button
            (click)="selectGreek(pair.idx)"
            [disabled]="greekState()[pair.idx] === 'correct'"
            class="w-full text-left px-4 py-3 rounded-xl border text-sm font-medium transition-all duration-150 flex items-center gap-2"
            [class]="greekClass(pair.idx)"
            [class.shake]="greekError()[pair.idx]"
          >
            <!-- Audio icon -->
            <svg class="w-4 h-4 shrink-0 opacity-60" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.617.784L4.8 13.6H3a1 1 0 01-1-1v-3a1 1 0 011-1h1.8l3.583-3.184a1 1 0 011 .024zM14.657 2.929a1 1 0 011.414 0A9.972 9.972 0 0119 10a9.972 9.972 0 01-2.929 7.071 1 1 0 01-1.414-1.414A7.971 7.971 0 0017 10c0-2.21-.894-4.208-2.343-5.657a1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0A5.983 5.983 0 0115 10a5.984 5.984 0 01-1.757 4.243 1 1 0 01-1.415-1.415A3.984 3.984 0 0013 10a3.983 3.983 0 00-1.172-2.828 1 1 0 010-1.415z" clip-rule="evenodd"/>
            </svg>
            <span>{{ pair.greek }}</span>
          </button>
        }
      </div>

      <!-- English column (right) -->
      <div class="space-y-2">
        @for (pair of shuffledEnglish(); track pair.idx) {
          <button
            (click)="selectEnglish(pair.idx)"
            [disabled]="englishState()[pair.idx] === 'correct'"
            class="w-full text-left px-4 py-3 rounded-xl border text-sm transition-all duration-150"
            [class]="englishClass(pair.idx)"
            [class.shake]="englishError()[pair.idx]"
          >
            {{ pair.english }}
          </button>
        }
      </div>
    </div>

    <!-- Progress indicator -->
    <div class="mt-4 flex items-center gap-2">
      @for (i of pairsRange(); track i) {
        <div class="h-1.5 flex-1 rounded-full transition-all duration-300"
          [class]="i < matchedCount() ? 'bg-emerald-400' : 'bg-surface-200'">
        </div>
      }
      @if (allMatched()) {
        <span class="text-xs font-semibold text-emerald-600 ml-1">All matched!</span>
      }
    </div>
  `,
})
export class MatchingComponent implements OnInit {
  @Input({ required: true }) exercise!: Exercise;
  @Output() answered = new EventEmitter<boolean>();

  shuffledGreek = signal<Array<{ idx: number; greek: string; audioUrl?: string }>>([]);
  shuffledEnglish = signal<Array<{ idx: number; english: string }>>([]);

  greekState = signal<Record<number, PairState>>({});
  englishState = signal<Record<number, PairState>>({});
  greekError = signal<Record<number, boolean>>({});
  englishError = signal<Record<number, boolean>>({});

  selectedGreekIdx = signal<number | null>(null);
  selectedEnglishIdx = signal<number | null>(null);
  matchedCount = signal(0);
  allMatched = signal(false);

  private _pairs: MatchingPairWithAudio[] = [];
  private _audioCache: Map<string, HTMLAudioElement> = new Map();

  ngOnInit(): void {
    const data = this.exercise.data as unknown as MatchingData;
    this._pairs = (data?.pairs ?? []) as MatchingPairWithAudio[];

    const greekItems = this._pairs.map((p, i) => ({ idx: i, greek: p.greek, audioUrl: (p as any).audioUrl }));
    const englishItems = this._pairs.map((p, i) => ({ idx: i, english: p.english }));

    this.shuffledGreek.set(this._shuffle(greekItems));
    this.shuffledEnglish.set(this._shuffle(englishItems));

    const initialState: Record<number, PairState> = {};
    this._pairs.forEach((_, i) => { initialState[i] = 'idle'; });
    this.greekState.set({ ...initialState });
    this.englishState.set({ ...initialState });
    this.greekError.set({});
    this.englishError.set({});
  }

  pairsRange(): number[] {
    return Array.from({ length: this._pairs.length }, (_, i) => i);
  }

  selectGreek(idx: number): void {
    const gs = this.greekState();
    if (gs[idx] === 'correct') return;

    // Play audio
    this._playAudio(idx);

    if (gs[idx] === 'selected') {
      // Deselect
      this.greekState.set({ ...gs, [idx]: 'idle' });
      this.selectedGreekIdx.set(null);
      return;
    }

    this.greekState.set({ ...gs, [idx]: 'selected' });
    this.selectedGreekIdx.set(idx);
    this._tryMatch();
  }

  selectEnglish(idx: number): void {
    const es = this.englishState();
    if (es[idx] === 'correct') return;

    if (es[idx] === 'selected') {
      // Deselect
      this.englishState.set({ ...es, [idx]: 'idle' });
      this.selectedEnglishIdx.set(null);
      return;
    }

    this.englishState.set({ ...es, [idx]: 'selected' });
    this.selectedEnglishIdx.set(idx);
    this._tryMatch();
  }

  private _tryMatch(): void {
    const gIdx = this.selectedGreekIdx();
    const eIdx = this.selectedEnglishIdx();
    if (gIdx === null || eIdx === null) return;

    if (gIdx === eIdx) {
      // Correct match
      this.greekState.set({ ...this.greekState(), [gIdx]: 'correct' });
      this.englishState.set({ ...this.englishState(), [eIdx]: 'correct' });
      this.selectedGreekIdx.set(null);
      this.selectedEnglishIdx.set(null);
      const newCount = this.matchedCount() + 1;
      this.matchedCount.set(newCount);
      if (newCount === this._pairs.length) {
        this.allMatched.set(true);
        this.answered.emit(true);
      }
    } else {
      // Wrong match — flash red then reset
      this.greekState.set({ ...this.greekState(), [gIdx]: 'error' });
      this.englishState.set({ ...this.englishState(), [eIdx]: 'error' });
      this.greekError.set({ ...this.greekError(), [gIdx]: true });
      this.englishError.set({ ...this.englishError(), [eIdx]: true });

      setTimeout(() => {
        this.greekState.set({ ...this.greekState(), [gIdx]: 'idle' });
        this.englishState.set({ ...this.englishState(), [eIdx]: 'idle' });
        this.greekError.set({ ...this.greekError(), [gIdx]: false });
        this.englishError.set({ ...this.englishError(), [eIdx]: false });
        this.selectedGreekIdx.set(null);
        this.selectedEnglishIdx.set(null);
      }, 500);
    }
  }

  private _playAudio(idx: number): void {
    const pair = this._pairs[idx] as MatchingPairWithAudio;
    const url = pair?.audioUrl;
    if (!url) return;
    try {
      let audio = this._audioCache.get(url);
      if (!audio) {
        audio = new Audio(url);
        this._audioCache.set(url, audio);
      }
      audio.currentTime = 0;
      audio.play().catch(() => {});
    } catch {
      // Audio not supported — silently ignore
    }
  }

  private _shuffle<T>(arr: T[]): T[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  greekClass(idx: number): string {
    const state = this.greekState()[idx];
    switch (state) {
      case 'selected': return 'border-greek-500 bg-greek-50 text-greek-800 ring-2 ring-greek-300';
      case 'correct':  return 'border-emerald-300 bg-emerald-50 text-emerald-700 cursor-not-allowed opacity-75';
      case 'error':    return 'border-red-400 bg-red-50 text-red-700';
      default:         return 'border-surface-200 bg-white text-surface-700 hover:border-greek-300 hover:bg-greek-50/40';
    }
  }

  englishClass(idx: number): string {
    const state = this.englishState()[idx];
    switch (state) {
      case 'selected': return 'border-greek-500 bg-greek-50 text-greek-800 ring-2 ring-greek-300';
      case 'correct':  return 'border-emerald-300 bg-emerald-50 text-emerald-700 cursor-not-allowed opacity-75';
      case 'error':    return 'border-red-400 bg-red-50 text-red-700';
      default:         return 'border-surface-200 bg-white text-surface-700 hover:border-greek-300 hover:bg-greek-50/40';
    }
  }

  /** For external submit (exercise card "Check" button) — matching auto-submits on completion. */
  submit(): void {
    // Matching is self-submitting; no-op if not all matched
  }

  isCorrect(): boolean {
    return this.allMatched();
  }
}
