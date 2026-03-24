import { Component, Input, Output, EventEmitter, signal, inject, OnInit, OnDestroy } from '@angular/core';
import {
  Exercise,
  ConversationData,
  ConversationLine,
  ConversationCheckpoint,
  McqCheckpoint,
  TrueFalseCheckpoint,
  TranslationCheckpoint,
  VocabularyItem,
} from '../../../core/models/firestore.models';
import { Storage, ref, getDownloadURL } from '@angular/fire/storage';
import { HighlightVocabPipe } from '../../../shared/pipes/highlight-vocab.pipe';

type LineStep = { kind: 'line'; line: ConversationLine; lineIndex: number };
type CheckpointStep = { kind: 'checkpoint'; checkpoint: ConversationCheckpoint; checkpointIndex: number };
type ConversationStep = LineStep | CheckpointStep;

@Component({
  selector: 'app-conversation',
  standalone: true,
  imports: [HighlightVocabPipe],
  template: `
    <div class="space-y-3">

      <!-- Play All / Stop button -->
      <div class="flex items-center gap-3 pb-1">
        @if (!playingAll()) {
          <button
            (click)="startPlayAll()"
            [disabled]="steps().length === 0"
            class="flex items-center gap-2 px-4 py-2 rounded-xl bg-greek-600 text-white text-xs font-semibold hover:bg-greek-700 active:scale-95 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
            </svg>
            Play Conversation
          </button>
        } @else {
          <button
            (click)="stopPlayAll()"
            class="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500 text-white text-xs font-semibold hover:bg-red-600 active:scale-95 transition-all shadow-sm"
          >
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clip-rule="evenodd"/>
            </svg>
            Stop
          </button>
        }
        @if (playingAll()) {
          <span class="text-xs text-surface-400 italic animate-pulse">Playing conversation…</span>
        }
      </div>

      @for (step of steps(); track $index; let si = $index) {
        @if (step.kind === 'line') {
          <!-- Conversation line -->
          <div class="flex gap-3 transition-all duration-300"
            [class]="step.line.speaker === 'male' ? 'justify-start' : 'justify-end'">
            <div class="max-w-[80%] rounded-2xl px-4 py-3 border transition-all duration-300"
              [class]="lineBubbleClass(step.line.speaker, step.lineIndex)">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-semibold"
                  [class]="step.line.speaker === 'male' ? 'text-greek-700' : 'text-gold-700'">
                  {{ step.line.speaker === 'male' ? 'Νίκος' : 'Ελένη' }}
                </span>
                @if (step.line.audioPath) {
                  <button
                    (click)="playLine(step.line, step.lineIndex)"
                    [disabled]="playingIndex() === step.lineIndex"
                    class="w-5 h-5 rounded-full flex items-center justify-center transition-colors"
                    [class]="step.line.speaker === 'male'
                      ? 'text-greek-500 hover:text-greek-700'
                      : 'text-gold-500 hover:text-gold-700'"
                    title="Play audio"
                  >
                    @if (playingIndex() === step.lineIndex) {
                      <svg class="w-3.5 h-3.5 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/>
                      </svg>
                    } @else {
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                      </svg>
                    }
                  </button>
                }
              </div>
              <p class="text-[15px] font-medium leading-snug"
                [class]="step.line.speaker === 'male' ? 'text-greek-900' : 'text-surface-800'"
                [innerHTML]="step.line.text | highlightVocab:vocabulary">
              </p>
              @if (step.line.translation) {
                <p class="text-xs mt-1 italic"
                  [class]="step.line.speaker === 'male' ? 'text-greek-500' : 'text-gold-600'">
                  {{ step.line.translation }}
                </p>
              }
            </div>
          </div>
        }

        @if (step.kind === 'checkpoint') {
          <!-- Checkpoint question -->
          <div class="border border-amber-200 bg-amber-50 rounded-xl px-4 py-4 my-2"
            [class]="playingAll() && pendingCheckpointIndex() === step.checkpointIndex ? 'ring-2 ring-amber-400' : ''">
            <p class="text-xs font-semibold text-amber-700 uppercase tracking-wider mb-2">Quick Check</p>

            <!-- MCQ checkpoint -->
            @if (step.checkpoint.type === 'mcq') {
              <p class="text-sm font-medium text-surface-700 mb-3">{{ asMcq(step.checkpoint).question }}</p>
              <div class="space-y-2">
                @for (option of asMcq(step.checkpoint).options; track $index; let optIdx = $index) {
                  <button
                    (click)="selectCheckpoint(step.checkpointIndex, optIdx)"
                    [disabled]="checkpointAnswers().has(step.checkpointIndex)"
                    class="w-full text-left px-3 py-2 rounded-lg border text-sm transition-all"
                    [class]="checkpointOptionClass(step.checkpointIndex, optIdx, option.isCorrect)"
                  >
                    {{ option.text }}
                  </button>
                }
              </div>
            }

            <!-- True/False checkpoint -->
            @if (step.checkpoint.type === 'true_false') {
              <p class="text-sm font-medium text-surface-700 mb-3">True or false: {{ asTrueFalse(step.checkpoint).statement }}</p>
              <div class="flex gap-3">
                <button
                  (click)="selectTrueFalse(step.checkpointIndex, true)"
                  [disabled]="checkpointAnswers().has(step.checkpointIndex)"
                  class="flex-1 px-3 py-2 rounded-lg border text-sm font-semibold transition-all"
                  [class]="trueFalseOptionClass(step.checkpointIndex, true, asTrueFalse(step.checkpoint).is_true)"
                >
                  True
                </button>
                <button
                  (click)="selectTrueFalse(step.checkpointIndex, false)"
                  [disabled]="checkpointAnswers().has(step.checkpointIndex)"
                  class="flex-1 px-3 py-2 rounded-lg border text-sm font-semibold transition-all"
                  [class]="trueFalseOptionClass(step.checkpointIndex, false, !asTrueFalse(step.checkpoint).is_true)"
                >
                  False
                </button>
              </div>
              @if (checkpointAnswers().has(step.checkpointIndex)) {
                <p class="mt-2 text-xs font-semibold"
                  [class]="checkpointAnswers().get(step.checkpointIndex) ? 'text-emerald-600' : 'text-red-500'">
                  {{ checkpointAnswers().get(step.checkpointIndex) ? 'Correct!' : 'Incorrect — the statement was ' + (asTrueFalse(step.checkpoint).is_true ? 'true.' : 'false.') }}
                </p>
              }
            }

            <!-- Translation checkpoint -->
            @if (step.checkpoint.type === 'translation') {
              <p class="text-sm font-medium text-surface-700 mb-1">Translate this phrase into English:</p>
              <p class="font-serif text-base font-semibold text-greek-800 mb-3">{{ asTranslation(step.checkpoint).greek_phrase }}</p>
              @if (!checkpointAnswers().has(step.checkpointIndex)) {
                <div class="flex gap-2">
                  <input
                    type="text"
                    #translationInput
                    placeholder="Your translation…"
                    class="flex-1 px-3 py-2 rounded-lg border border-surface-300 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent"
                  />
                  <button
                    (click)="submitTranslation(step.checkpointIndex, asTranslation(step.checkpoint).english_answer, translationInput.value)"
                    class="px-4 py-2 rounded-lg bg-amber-500 text-white text-xs font-semibold hover:bg-amber-600 transition-colors"
                  >
                    Check
                  </button>
                </div>
              } @else {
                <div class="rounded-lg px-3 py-2 text-sm"
                  [class]="checkpointAnswers().get(step.checkpointIndex) ? 'bg-emerald-50 border border-emerald-200' : 'bg-surface-50 border border-surface-200'">
                  <p class="text-xs font-semibold mb-1"
                    [class]="checkpointAnswers().get(step.checkpointIndex) ? 'text-emerald-600' : 'text-surface-500'">
                    {{ checkpointAnswers().get(step.checkpointIndex) ? 'Good!' : 'Answer:' }}
                  </p>
                  <p class="text-surface-700">{{ asTranslation(step.checkpoint).english_answer }}</p>
                </div>
              }
            }

            <!-- Correct / incorrect feedback for mcq -->
            @if (step.checkpoint.type === 'mcq' && checkpointAnswers().has(step.checkpointIndex)) {
              <p class="mt-2 text-xs font-semibold"
                [class]="checkpointAnswers().get(step.checkpointIndex) ? 'text-emerald-600' : 'text-red-500'">
                {{ checkpointAnswers().get(step.checkpointIndex) ? 'Correct!' : 'Incorrect' }}
              </p>
            }

            <!-- Continue button (shown in Play All mode after answering) -->
            @if (playingAll() && pendingCheckpointIndex() === step.checkpointIndex && checkpointAnswers().has(step.checkpointIndex)) {
              <div class="mt-3 flex justify-end">
                <button
                  (click)="continueAfterCheckpoint()"
                  class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-greek-600 text-white text-xs font-semibold hover:bg-greek-700 active:scale-95 transition-all shadow-sm"
                >
                  Continue
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                  </svg>
                </button>
              </div>
            }
          </div>
        }
      }

      <!-- Submit button — shown after all checkpoints have been answered -->
      @if (allCheckpointsAnswered() && !submitted()) {
        <div class="pt-2 flex justify-end">
          <button
            (click)="submitConversation()"
            class="px-4 py-2 rounded-lg bg-greek-600 text-white text-xs font-semibold hover:bg-greek-700 transition-colors"
          >
            Submit
          </button>
        </div>
      }
    </div>
  `,
})
export class ConversationComponent implements OnInit, OnDestroy {
  @Input({ required: true }) exercise!: Exercise;
  @Input() chapterStoragePath = '';
  @Input() vocabulary: VocabularyItem[] = [];
  @Output() answered = new EventEmitter<boolean>();

  private storage = inject(Storage);

  steps = signal<ConversationStep[]>([]);
  playingIndex = signal<number | null>(null);
  /** Maps checkpointIndex -> whether user answered correctly */
  checkpointAnswers = signal<Map<number, boolean>>(new Map());
  /** Maps checkpointIndex -> selected option index (for MCQ) */
  private selectedOptions = new Map<number, number>();
  submitted = signal(false);

  /** Whether "Play All" sequential mode is active */
  playingAll = signal(false);
  /**
   * When playing all, paused at this checkpoint index waiting for the user
   * to answer AND press Continue before resuming. null = not paused.
   */
  pendingCheckpointIndex = signal<number | null>(null);

  /** Current step index in the sequential playback queue */
  private playAllStepIndex = 0;
  /** Currently playing Audio object — so we can stop it */
  private currentAudio: HTMLAudioElement | null = null;

  ngOnInit(): void {
    const data = this.exercise.data as unknown as ConversationData;
    if (!data?.lines) return;

    const built: ConversationStep[] = [];
    const checkpoints = [...(data.checkpoints ?? [])].sort(
      (a, b) => a.after_line_index - b.after_line_index
    );
    let cpIdx = 0;

    for (let i = 0; i < data.lines.length; i++) {
      built.push({ kind: 'line', line: data.lines[i], lineIndex: i });
      while (cpIdx < checkpoints.length && checkpoints[cpIdx].after_line_index === i) {
        built.push({ kind: 'checkpoint', checkpoint: checkpoints[cpIdx], checkpointIndex: cpIdx });
        cpIdx++;
      }
    }
    while (cpIdx < checkpoints.length) {
      built.push({ kind: 'checkpoint', checkpoint: checkpoints[cpIdx], checkpointIndex: cpIdx });
      cpIdx++;
    }

    this.steps.set(built);
  }

  ngOnDestroy(): void {
    this.stopPlayAll();
  }

  // ---------------------------------------------------------------------------
  // Checkpoint type guards / casts
  // ---------------------------------------------------------------------------

  asMcq(cp: ConversationCheckpoint): McqCheckpoint {
    return cp as McqCheckpoint;
  }

  asTrueFalse(cp: ConversationCheckpoint): TrueFalseCheckpoint {
    return cp as TrueFalseCheckpoint;
  }

  asTranslation(cp: ConversationCheckpoint): TranslationCheckpoint {
    return cp as TranslationCheckpoint;
  }

  // ---------------------------------------------------------------------------
  // Individual line playback
  // ---------------------------------------------------------------------------

  playLine(line: ConversationLine, idx: number): void {
    if (!line.audioPath) return;
    this.playingIndex.set(idx);
    this._resolveAndPlay(line.audioPath,
      () => this.playingIndex.set(null),
      () => this.playingIndex.set(null)
    );
  }

  // ---------------------------------------------------------------------------
  // Play All sequential mode
  // ---------------------------------------------------------------------------

  startPlayAll(): void {
    this.playAllStepIndex = 0;
    this.playingAll.set(true);
    this.pendingCheckpointIndex.set(null);
    this._playNextStep();
  }

  stopPlayAll(): void {
    this.playingAll.set(false);
    this.pendingCheckpointIndex.set(null);
    this.playingIndex.set(null);
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
  }

  /** Advance to the next step in the sequential playback. */
  private _playNextStep(): void {
    if (!this.playingAll()) return;

    const steps = this.steps();
    if (this.playAllStepIndex >= steps.length) {
      // Reached end of conversation
      this.playingAll.set(false);
      this.pendingCheckpointIndex.set(null);
      return;
    }

    const step = steps[this.playAllStepIndex];

    if (step.kind === 'checkpoint') {
      // Pause playback — wait for user to answer AND press Continue
      this.pendingCheckpointIndex.set(step.checkpointIndex);
      // continueAfterCheckpoint() will be called when the user presses the button
      return;
    }

    // It's a line — play its audio then advance
    const line = step.line;
    this.playingIndex.set(line ? step.lineIndex : null);
    this.playAllStepIndex++;

    if (!line.audioPath) {
      // No audio for this line — move on after a short pause
      setTimeout(() => this._playNextStep(), 400);
      return;
    }

    this._resolveAndPlay(
      line.audioPath,
      () => {
        this.playingIndex.set(null);
        // Small gap between lines
        setTimeout(() => this._playNextStep(), 300);
      },
      () => {
        this.playingIndex.set(null);
        setTimeout(() => this._playNextStep(), 300);
      }
    );
  }

  /** Called when the user presses the "Continue" button after a checkpoint. */
  continueAfterCheckpoint(): void {
    if (!this.playingAll()) return;
    this.pendingCheckpointIndex.set(null);
    this.playAllStepIndex++;
    setTimeout(() => this._playNextStep(), 400);
  }

  // ---------------------------------------------------------------------------
  // Checkpoint selection
  // ---------------------------------------------------------------------------

  selectCheckpoint(cpIdx: number, optionIdx: number): void {
    if (this.checkpointAnswers().has(cpIdx)) return;
    const cpStep = this.steps().find(
      (s): s is CheckpointStep => s.kind === 'checkpoint' && s.checkpointIndex === cpIdx
    );
    if (!cpStep || cpStep.checkpoint.type !== 'mcq') return;
    const isCorrect = (cpStep.checkpoint as McqCheckpoint).options[optionIdx]?.isCorrect ?? false;
    this.selectedOptions.set(cpIdx, optionIdx);
    this.checkpointAnswers.update(m => {
      const next = new Map(m);
      next.set(cpIdx, isCorrect);
      return next;
    });
  }

  selectTrueFalse(cpIdx: number, selected: boolean): void {
    if (this.checkpointAnswers().has(cpIdx)) return;
    const cpStep = this.steps().find(
      (s): s is CheckpointStep => s.kind === 'checkpoint' && s.checkpointIndex === cpIdx
    );
    if (!cpStep || cpStep.checkpoint.type !== 'true_false') return;
    const isCorrect = selected === (cpStep.checkpoint as TrueFalseCheckpoint).is_true;
    this.selectedOptions.set(cpIdx, selected ? 1 : 0);
    this.checkpointAnswers.update(m => {
      const next = new Map(m);
      next.set(cpIdx, isCorrect);
      return next;
    });
  }

  submitTranslation(cpIdx: number, correctAnswer: string, userInput: string): void {
    if (this.checkpointAnswers().has(cpIdx)) return;
    // Lenient check: case-insensitive, ignore leading/trailing spaces and punctuation
    const normalize = (s: string) => s.trim().toLowerCase().replace(/[.!?,]/g, '');
    const isCorrect = normalize(userInput) === normalize(correctAnswer);
    this.checkpointAnswers.update(m => {
      const next = new Map(m);
      next.set(cpIdx, isCorrect);
      return next;
    });
  }

  // ---------------------------------------------------------------------------
  // Styling helpers
  // ---------------------------------------------------------------------------

  lineBubbleClass(speaker: 'male' | 'female', lineIndex: number): string {
    const isActive = this.playingIndex() === lineIndex;
    if (speaker === 'male') {
      return isActive
        ? 'bg-greek-100 border-greek-400 shadow-md rounded-tl-sm'
        : 'bg-greek-50 border-greek-200 rounded-tl-sm';
    }
    // female — gold/amber
    return isActive
      ? 'bg-gold-100 border-gold-400 shadow-md rounded-tr-sm'
      : 'bg-gold-50 border-gold-200 rounded-tr-sm';
  }

  checkpointOptionClass(cpIdx: number, optionIdx: number, isCorrect: boolean): string {
    const answers = this.checkpointAnswers();
    if (!answers.has(cpIdx)) {
      return 'border-surface-200 bg-white text-surface-700 hover:border-greek-300 hover:bg-greek-50';
    }
    if (isCorrect) return 'border-emerald-300 bg-emerald-50 text-emerald-800';
    if (this.selectedOptions.get(cpIdx) === optionIdx) return 'border-red-300 bg-red-50 text-red-700';
    return 'border-surface-200 bg-white text-surface-400';
  }

  trueFalseOptionClass(cpIdx: number, selectedValue: boolean, isCorrectChoice: boolean): string {
    const answers = this.checkpointAnswers();
    if (!answers.has(cpIdx)) {
      return 'border-surface-200 bg-white text-surface-700 hover:border-amber-300 hover:bg-amber-50';
    }
    // After answering — highlight correct choice green; selected wrong choice red
    const userSelectedTrue = (this.selectedOptions.get(cpIdx) ?? -1) === 1;
    const userSelected = selectedValue ? userSelectedTrue : !userSelectedTrue;
    if (isCorrectChoice) return 'border-emerald-300 bg-emerald-50 text-emerald-800';
    if (userSelected) return 'border-red-300 bg-red-50 text-red-700';
    return 'border-surface-200 bg-white text-surface-400';
  }

  totalCheckpoints(): number {
    return this.steps().filter(s => s.kind === 'checkpoint').length;
  }

  allCheckpointsAnswered(): boolean {
    const total = this.totalCheckpoints();
    return total > 0 && this.checkpointAnswers().size >= total;
  }

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------

  submitConversation(): void {
    this.submitted.set(true);
    let allCorrect = true;
    this.checkpointAnswers().forEach(v => { if (!v) allCorrect = false; });
    this.answered.emit(allCorrect);
  }

  /** Public submit() — no-op; conversation is self-driven via checkpoints + Submit button. */
  submit(): void {}

  // ---------------------------------------------------------------------------
  // Audio resolution helper
  // ---------------------------------------------------------------------------

  private _resolveAndPlay(
    audioPath: string,
    onEnded: () => void,
    onError: () => void
  ): void {
    const play = (url: string) => {
      if (this.currentAudio) {
        this.currentAudio.pause();
      }
      const audio = new Audio(url);
      this.currentAudio = audio;
      audio.play().catch(onError);
      audio.onended = () => {
        this.currentAudio = null;
        onEnded();
      };
      audio.onerror = () => {
        this.currentAudio = null;
        onError();
      };
    };

    if (audioPath.startsWith('gs://')) {
      getDownloadURL(ref(this.storage, audioPath))
        .then(play)
        .catch(onError);
    } else if (audioPath.startsWith('http')) {
      play(audioPath);
    } else {
      // Relative path: resolve against chapterStoragePath in GCS
      const gsPath = `${this.chapterStoragePath}/${audioPath}`;
      getDownloadURL(ref(this.storage, gsPath))
        .then(play)
        .catch(onError);
    }
  }
}
