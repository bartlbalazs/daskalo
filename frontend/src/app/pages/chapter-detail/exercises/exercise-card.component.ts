import {
  Component, Input, Output, EventEmitter, signal, ViewChild, inject
} from '@angular/core';
import { Exercise, ExerciseType, EvaluationResult, PassageSentence, VocabularyItem } from '../../../core/models/firestore.models';
import { LessonService } from '../../../core/services/lesson.service';
import { MultipleChoiceComponent } from './multiple-choice.component';
import { SlangMatcherComponent } from './slang-matcher.component';
import { WordScrambleComponent } from './word-scramble.component';
import { SentenceReorderComponent } from './sentence-reorder.component';
import { ListeningComprehensionComponent } from './listening-comprehension.component';
import { PassageComprehensionComponent } from './passage-comprehension.component';
import { DialogueCompletionComponent } from './dialogue-completion.component';
import { ImageDescriptionComponent } from './image-description.component';
import { TranslationChallengeComponent } from './translation-challenge.component';
import { DictationComponent } from './dictation.component';
import { ConversationComponent } from './conversation.component';
import { PronunciationPracticeComponent } from './pronunciation-practice.component';

export type ExerciseState = 'unanswered' | 'correct' | 'incorrect' | 'evaluating' | 'evaluated';

const TYPE_LABELS: Record<ExerciseType, string> = {
  slang_matcher: 'Slang Matcher',
  vocab_flashcard: 'Vocabulary',
  fill_in_the_blank: 'Fill in the Blank',
  word_scramble: 'Word Scramble',
  odd_one_out: 'Odd One Out',
  image_description: 'Image Description',
  translation_challenge: 'Translation Challenge',
  sentence_reorder: 'Sentence Reorder',
  passage_comprehension: 'Reading Comprehension',
  listening_comprehension: 'Listening Comprehension',
  dictation: 'Dictation',
  pronunciation_practice: 'Pronunciation',
  roleplay_choice: 'Roleplay',
  dialogue_completion: 'Dialogue Completion',
  cultural_context: 'Cultural Context',
  lyrics_fill: 'Lyrics Fill',
  conversation: 'Conversation',
};

@Component({
  selector: 'app-exercise-card',
  standalone: true,
  imports: [
    MultipleChoiceComponent,
    SlangMatcherComponent,
    WordScrambleComponent,
    SentenceReorderComponent,
    ListeningComprehensionComponent,
    PassageComprehensionComponent,
    DialogueCompletionComponent,
    ImageDescriptionComponent,
    TranslationChallengeComponent,
    DictationComponent,
    ConversationComponent,
    PronunciationPracticeComponent,
  ],
  template: `
    <div class="rounded-2xl border shadow-sm transition-all duration-200"
      [class]="cardBorderClass()">

      <!-- Card header -->
      <div class="flex items-center gap-3 px-5 py-4 border-b rounded-t-2xl"
        [class]="cardHeaderClass()">
        <!-- Number badge -->
        <span class="w-7 h-7 rounded-full text-sm font-bold flex items-center justify-center shrink-0"
          [class]="numberBadgeClass()">
          {{ index + 1 }}
        </span>

        <!-- Type label -->
        <span class="text-xs font-semibold uppercase tracking-widest"
          [class]="typeLabelClass()">
          {{ typeLabel() }}
        </span>

        <!-- State indicator -->
        <div class="ml-auto">
          @if (state() === 'correct') {
            <div class="flex items-center gap-1.5 text-emerald-600 text-xs font-semibold">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
              </svg>
              Correct
            </div>
          } @else if (state() === 'incorrect') {
            <div class="flex items-center gap-1.5 text-red-500 text-xs font-semibold">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
              </svg>
              Incorrect
            </div>
          } @else if (state() === 'evaluating') {
            <div class="flex items-center gap-1.5 text-greek-600 text-xs font-semibold">
              <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Evaluating…
            </div>
          } @else if (state() === 'evaluated') {
            <div class="flex items-center gap-1.5 text-greek-600 text-xs font-semibold">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
              </svg>
              Evaluated
            </div>
          }
        </div>
      </div>

      <!-- Card body -->
      <div class="px-5 py-5 bg-white">
        <!-- Prompt (hidden for fill_in_the_blank — the child renders the sentence with the interactive blank) -->
        @if (exercise.type !== 'fill_in_the_blank') {
          <p class="text-sm font-medium text-surface-700 mb-4 leading-relaxed">{{ exercise.prompt }}</p>
        }

        <!-- Exercise content -->

        @if (isPronunciation()) {
          <app-pronunciation-practice
            #pronunciationPractice
            [exercise]="exercise"
            [chapterStoragePath]="chapterStoragePath"
            (submitted$)="onPronunciationSubmit($event)"
            (answered)="onAiAnswered($event)"
            (retried)="onPronunciationRetry()"
          />
        }

        @if (isMCQ()) {
          <app-multiple-choice
            #mcq
            [exercise]="exercise"
            (answered)="onFrontendAnswer($event)"
          />
        }

        @if (exercise.type === 'slang_matcher') {
          <app-slang-matcher
            #slangMatcher
            [exercise]="exercise"
            (answered)="onFrontendAnswer($event)"
          />
        }

        @if (exercise.type === 'word_scramble') {
          <app-word-scramble
            #wordScramble
            [exercise]="exercise"
            (answered)="onFrontendAnswer($event)"
          />
        }

        @if (exercise.type === 'sentence_reorder') {
          <app-sentence-reorder
            #sentenceReorder
            [exercise]="exercise"
            (answered)="onFrontendAnswer($event)"
          />
        }

        @if (exercise.type === 'listening_comprehension') {
          <app-listening-comprehension
            #listeningComp
            [exercise]="exercise"
            [chapterStoragePath]="chapterStoragePath"
            [sentenceAudioUrls]="sentenceAudioUrls"
            (answered)="onFrontendAnswer($event)"
          />
        }

        @if (exercise.type === 'passage_comprehension') {
          <app-passage-comprehension
            #passageComp
            [exercise]="exercise"
            [passageAudioUrl]="passageAudioUrl"
            [passage]="passage"
            [passageText]="passageText"
            [vocabulary]="vocabulary"
            (answered)="onFrontendAnswer($event)"
          />
        }

        @if (exercise.type === 'dialogue_completion') {
          <app-dialogue-completion
            #dialogueComp
            [exercise]="exercise"
            [vocabulary]="vocabulary"
            (answered)="onFrontendAnswer($event)"
          />
        }

        @if (exercise.type === 'image_description') {
          <app-image-description
            #imageDesc
            [exercise]="exercise"
            (submitted$)="onAiSubmit($event)"
            (answered)="onAiAnswered($event)"
          />
        }

        @if (exercise.type === 'translation_challenge') {
          <app-translation-challenge
            #translationChallenge
            [exercise]="exercise"
            (submitted$)="onAiSubmit($event)"
            (answered)="onAiAnswered($event)"
          />
        }

        @if (exercise.type === 'dictation') {
          <app-dictation
            #dictation
            [exercise]="exercise"
            [chapterStoragePath]="chapterStoragePath"
            [sentenceAudioUrls]="sentenceAudioUrls"
            (submitted$)="onAiSubmit($event)"
            (answered)="onAiAnswered($event)"
          />
        }

        @if (exercise.type === 'conversation') {
          <app-conversation
            #conversationComp
            [exercise]="exercise"
            [chapterStoragePath]="chapterStoragePath"
            [vocabulary]="vocabulary"
            (answered)="onFrontendAnswer($event)"
          />
        }
      </div>

      <!-- Card footer: per-exercise Check button -->
      @if (!isPronunciation() && exercise.type !== 'conversation' && !isAiGraded() && state() === 'unanswered') {
        <div class="px-5 py-3 bg-surface-50 border-t border-surface-100 flex justify-end rounded-b-2xl">
          <button
            (click)="submit()"
            class="px-4 py-2 rounded-lg bg-greek-600 text-white text-xs font-semibold hover:bg-greek-700 transition-colors"
          >
            Check
          </button>
        </div>
      }
    </div>
  `,
})
export class ExerciseCardComponent {
  @Input({ required: true }) exercise!: Exercise;
  @Input({ required: true }) index!: number;
  @Input() chapterId = '';
  @Input() chapterStoragePath = '';
  @Input() sentenceAudioUrls: string[] = [];
  @Input() passageAudioUrl = '';
  /** Structured passage sentences for click-to-translate (preferred). */
  @Input() passage: PassageSentence[] = [];
  /** Legacy plain-text passage string (fallback for older chapters). */
  @Input() passageText = '';
  @Input() vocabulary: VocabularyItem[] = [];
  /** Emits when the exercise result is known (correct or not). */
  @Output() answered = new EventEmitter<{ index: number; correct: boolean }>();

  private lessonService = inject(LessonService);

  state = signal<ExerciseState>('unanswered');

  @ViewChild('mcq') mcqRef?: MultipleChoiceComponent;
  @ViewChild('slangMatcher') slangMatcherRef?: SlangMatcherComponent;
  @ViewChild('wordScramble') wordScrambleRef?: WordScrambleComponent;
  @ViewChild('sentenceReorder') sentenceReorderRef?: SentenceReorderComponent;
  @ViewChild('listeningComp') listeningCompRef?: ListeningComprehensionComponent;
  @ViewChild('passageComp') passageCompRef?: PassageComprehensionComponent;
  @ViewChild('dialogueComp') dialogueCompRef?: DialogueCompletionComponent;
  @ViewChild('imageDesc') imageDescRef?: ImageDescriptionComponent;
  @ViewChild('translationChallenge') translationChallengeRef?: TranslationChallengeComponent;
  @ViewChild('dictation') dictationRef?: DictationComponent;
  @ViewChild('conversationComp') conversationCompRef?: ConversationComponent;
  @ViewChild('pronunciationPractice') pronunciationPracticeRef?: PronunciationPracticeComponent;

  typeLabel(): string {
    return TYPE_LABELS[this.exercise.type] ?? this.exercise.type;
  }

  isPronunciation(): boolean {
    return this.exercise.type === 'pronunciation_practice';
  }

  isMCQ(): boolean {
    return ['fill_in_the_blank', 'roleplay_choice', 'odd_one_out', 'cultural_context'].includes(this.exercise.type);
  }

  isAiGraded(): boolean {
    return ['image_description', 'translation_challenge', 'dictation', 'pronunciation_practice'].includes(this.exercise.type);
  }

  isAnswered(): boolean {
    return this.state() !== 'unanswered';
  }

  /** Trigger submission of this exercise (used by the Check button and externally). */
  submit(): void {
    if (this.isAnswered()) return;
    if (this.isMCQ()) { this.mcqRef?.submit(); return; }
    if (this.exercise.type === 'slang_matcher') { this.slangMatcherRef?.submit(); return; }
    if (this.exercise.type === 'word_scramble') { this.wordScrambleRef?.submit(); return; }
    if (this.exercise.type === 'sentence_reorder') { this.sentenceReorderRef?.submit(); return; }
    if (this.exercise.type === 'listening_comprehension') { this.listeningCompRef?.submit(); return; }
    if (this.exercise.type === 'passage_comprehension') { this.passageCompRef?.submit(); return; }
    if (this.exercise.type === 'dialogue_completion') { this.dialogueCompRef?.submit(); return; }
    if (this.exercise.type === 'image_description') { this.imageDescRef?.submit(); return; }
    if (this.exercise.type === 'translation_challenge') { this.translationChallengeRef?.submit(); return; }
    if (this.exercise.type === 'dictation') { this.dictationRef?.submit(); return; }
  }

  /** Called when a frontend-graded exercise emits its result. */
  onFrontendAnswer(correct: boolean): void {
    this.state.set(correct ? 'correct' : 'incorrect');
    this.answered.emit({ index: this.index, correct });
  }

  /** Called when an AI-graded exercise submits its text answer. */
  async onAiSubmit(text: string): Promise<void> {
    this.state.set('evaluating');
    const exerciseId = `ex_${this.index}`;
    try {
      const result = await this.lessonService.evaluateAttempt(
        this.chapterId,
        exerciseId,
        this.exercise.type,
        { text }
      );
      this.state.set(result.isCorrect ? 'correct' : 'incorrect');
      this.imageDescRef?.setEvaluation(result);
      this.translationChallengeRef?.setEvaluation(result);
      this.dictationRef?.setEvaluation(result);
      this.answered.emit({ index: this.index, correct: result.isCorrect });
    } catch {
      this.state.set('incorrect');
      const errorResult: EvaluationResult = {
        score: 0,
        feedback: 'Evaluation failed. Please try again.',
        isCorrect: false,
      };
      this.imageDescRef?.setEvaluation(errorResult);
      this.translationChallengeRef?.setEvaluation(errorResult);
      this.dictationRef?.setEvaluation(errorResult);
      this.answered.emit({ index: this.index, correct: false });
    }
  }

  /** Called when the pronunciation component submits a base64-encoded audio recording. */
  async onPronunciationSubmit(audioBase64: string): Promise<void> {
    this.state.set('evaluating');
    const exerciseId = `ex_${this.index}`;
    try {
      const result = await this.lessonService.evaluateAttempt(
        this.chapterId,
        exerciseId,
        this.exercise.type,
        { audioBase64 }
      );
      this.state.set(result.isCorrect ? 'correct' : 'incorrect');
      this.pronunciationPracticeRef?.setEvaluation(result);
      this.answered.emit({ index: this.index, correct: result.isCorrect });
    } catch {
      this.state.set('incorrect');
      const errorResult: EvaluationResult = {
        score: 0,
        feedback: 'Evaluation failed. Please try again.',
        isCorrect: false,
      };
      this.pronunciationPracticeRef?.setEvaluation(errorResult);
      this.answered.emit({ index: this.index, correct: false });
    }
  }

  /** No-op — state managed in onAiSubmit watcher. */
  onAiAnswered(_correct: boolean): void {}

  /** Reset card state so the student can attempt pronunciation again. */
  onPronunciationRetry(): void {
    this.state.set('unanswered');
  }

  cardBorderClass(): string {
    switch (this.state()) {
      case 'correct': return 'border-emerald-300';
      case 'incorrect': return 'border-red-300';
      case 'evaluating': return 'border-greek-400 animate-pulse';
      case 'evaluated': return 'border-greek-300';
      default: return 'border-surface-200';
    }
  }

  cardHeaderClass(): string {
    switch (this.state()) {
      case 'correct': return 'bg-emerald-50 border-emerald-100';
      case 'incorrect': return 'bg-red-50 border-red-100';
      case 'evaluating': return 'bg-greek-50 border-greek-100';
      case 'evaluated': return 'bg-greek-50 border-greek-100';
      default: return 'bg-surface-50 border-surface-100';
    }
  }

  numberBadgeClass(): string {
    switch (this.state()) {
      case 'correct': return 'bg-emerald-500 text-white';
      case 'incorrect': return 'bg-red-400 text-white';
      case 'evaluating':
      case 'evaluated': return 'bg-greek-600 text-white';
      default: return 'bg-surface-200 text-surface-600';
    }
  }

  typeLabelClass(): string {
    switch (this.state()) {
      case 'correct': return 'text-emerald-700';
      case 'incorrect': return 'text-red-600';
      case 'evaluating':
      case 'evaluated': return 'text-greek-700';
      default: return 'text-surface-500';
    }
  }
}
