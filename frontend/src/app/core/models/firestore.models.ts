// TypeScript models mirroring docs/DATA_MODEL.md
// Keep in sync with backend/models/firestore.py

import { Timestamp } from '@angular/fire/firestore';

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type UserStatus = 'pending' | 'active';

export type AttemptStatus = 'pending' | 'evaluating' | 'completed' | 'error';

export type ExerciseType =
  | 'slang_matcher'
  | 'vocab_flashcard'
  | 'fill_in_the_blank'
  | 'word_scramble'
  | 'odd_one_out'
  | 'image_description'
  | 'translation_challenge'
  | 'sentence_reorder'
  | 'passage_comprehension'
  | 'listening_comprehension'
  | 'dictation'
  | 'pronunciation_practice'
  | 'roleplay_choice'
  | 'dialogue_completion'
  | 'cultural_context'
  | 'lyrics_fill'
  | 'conversation';

// ---------------------------------------------------------------------------
// Exercise data shapes (one per type)
// ---------------------------------------------------------------------------

export interface SlangMatcherPair {
  formal: string;
  slang: string;
}
export interface SlangMatcherData {
  pairs: SlangMatcherPair[];
}

export interface FlashcardItem {
  greek: string;
  english: string;
}
export interface VocabFlashcardData {
  cards: FlashcardItem[];
}

export interface FillBlankOption {
  text: string;
  isCorrect: boolean;
}
export interface FillInTheBlankData {
  sentence: string;
  options: FillBlankOption[];
}

export interface WordScrambleData {
  word: string;
  scrambled: string;
}

export interface OddOneOutData {
  words: string[];
  correct_index: number;
}

export interface TranslationChallengeData {
  english_sentence: string;
}

export interface SentenceReorderData {
  correct_order: string[];
  scrambled_order: string[];
}

export interface ComprehensionOption {
  text: string;
  isCorrect: boolean;
}
export interface ComprehensionQuestion {
  question: string;
  options: ComprehensionOption[];
}
export interface PassageComprehensionData {
  questions: ComprehensionQuestion[];
}

export interface ListeningOption {
  text: string;
  isCorrect: boolean;
}
export interface ListeningComprehensionData {
  sentence_index: number;
  question: string;
  options: ListeningOption[];
}

export interface DictationData {
  sentence_index: number;
}

export interface PronunciationPracticeData {
  target_text: string;
}

export interface RoleplayOption {
  text: string;
  isCorrect: boolean;
}
export interface RoleplayData {
  options: RoleplayOption[];
}

export interface DialogueCompletionOption {
  text: string;
  isCorrect: boolean;
}
export interface DialogueCompletionData {
  dialogue: string[];
  options: DialogueCompletionOption[];
}

export interface CulturalOption {
  text: string;
  isCorrect: boolean;
}
export interface CulturalContextData {
  fact: string;
  question: string;
  options: CulturalOption[];
}

// Conversation exercise data shapes
export interface PassageSentence {
  greek: string;
  english: string;
}

export interface ConversationLine {
  speaker: 'male' | 'female';
  text: string;
  translation: string;
  audioPath: string;
}

export interface ConversationCheckpointOption {
  text: string;
  isCorrect: boolean;
}

/** Multiple-choice checkpoint */
export interface McqCheckpoint {
  type: 'mcq';
  after_line_index: number;
  question: string;
  options: ConversationCheckpointOption[];
}

/** True/False checkpoint */
export interface TrueFalseCheckpoint {
  type: 'true_false';
  after_line_index: number;
  statement: string;
  is_true: boolean;
}

/** Translation checkpoint */
export interface TranslationCheckpoint {
  type: 'translation';
  after_line_index: number;
  greek_phrase: string;
  english_answer: string;
}

export type ConversationCheckpoint = McqCheckpoint | TrueFalseCheckpoint | TranslationCheckpoint;

export interface ConversationData {
  topic_description?: string;
  lines: ConversationLine[];
  checkpoints: ConversationCheckpoint[];
}

// ---------------------------------------------------------------------------
// User
// ---------------------------------------------------------------------------

export interface UserProgress {
  currentBookId: string;
  completedChapterIds: string[];
  xp: number;
}

export interface VocabularyListItem {
  wordId: string;
  learnedAt: Timestamp;
}

export interface User {
  email: string;
  displayName: string;
  status: UserStatus;
  createdAt: Timestamp;
  lastActive: Timestamp;
  progress: UserProgress;
  vocabularyList: VocabularyListItem[];
}

// ---------------------------------------------------------------------------
// Book & Chapter
// ---------------------------------------------------------------------------

export interface Book {
  id: string;
  title: string;
  description: string;
  order: number;
  isActive: boolean;
}

export interface GrammarExample {
  greek: string;
  english: string;
  note?: string | null;
}

export interface GrammarNote {
  heading: string;
  explanation: string;
  examples: GrammarExample[];
  imageUrl?: string;
  audioUrl?: string;
  grammar_table?: string | null;
}

export interface VocabularyItem {
  greek: string;
  english: string;
  audioUrl?: string;
}

export interface Exercise {
  type: ExerciseType;
  prompt: string;
  imageUrl?: string;
  audioUrl?: string;
  data?: Record<string, unknown>;
}

export interface Chapter {
  id: string;
  curriculumChapterId: string;
  topic: string;
  bookId: string;
  title: string;
  order: number;
  summary: string;
  length?: 'short' | 'medium' | 'long';
  introduction?: string;
  /** Reading passage as an array of {greek, english} sentence objects. */
  passage?: PassageSentence[];
  /** Legacy plain-text passage field (may be present on older chapters). */
  passage_text?: string;
  passageAudioUrl?: string;
  sentenceAudioUrls?: string[];
  coverImageUrl?: string;
  languageSkill?: string;
  grammarNotes: GrammarNote[];
  /** Pre-generated Markdown grammar reference (grammar tables, key vocabulary, tips).
   *  Shared across all students. Only shown after the chapter is completed. */
  grammarSummary?: string;
  vocabulary: VocabularyItem[];
  exercises: Exercise[];
}

// ---------------------------------------------------------------------------
// Exercise Attempts
// ---------------------------------------------------------------------------

export interface AttemptPayload {
  text?: string;
  selectedOption?: string;
  extra?: Record<string, unknown>;
}

export interface EvaluationResult {
  score: number;
  feedback: string;
  isCorrect: boolean;
}

export interface ExerciseAttempt {
  userId: string;
  chapterId: string;
  exerciseId: string;
  type: ExerciseType;
  submittedAt: Timestamp;
  payload: AttemptPayload;
  status: AttemptStatus;
  evaluation: EvaluationResult | null;
}
