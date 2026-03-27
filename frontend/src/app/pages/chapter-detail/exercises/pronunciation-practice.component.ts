import { Component, Input, Output, EventEmitter, signal, OnDestroy } from '@angular/core';
import { Exercise, EvaluationResult, PronunciationPracticeData } from '../../../core/models/firestore.models';
import { AudioPlayerComponent } from './audio-player.component';
import { NgClass } from '@angular/common';

/** Maximum recording duration in seconds — stays within a single 15s STT billing increment. */
const MAX_RECORD_SECONDS = 14;

type RecordingState = 'idle' | 'requesting' | 'recording' | 'recorded' | 'submitted';

@Component({
  selector: 'app-pronunciation-practice',
  standalone: true,
  imports: [AudioPlayerComponent, NgClass],
  template: `
    <div class="space-y-5">

      <!-- Target text -->
      <div class="bg-greek-50 border border-greek-100 rounded-2xl px-6 py-5 text-center">
        <p class="text-xs font-semibold uppercase tracking-widest text-greek-400 mb-2">Pronounce this</p>
        <p class="font-serif text-3xl font-semibold text-greek-900 leading-snug">{{ targetText() }}</p>
      </div>

      <!-- Reference audio -->
      @if (exercise.audioUrl) {
        <div>
          <p class="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-2">Listen first</p>
          <app-audio-player [src]="exercise.audioUrl" />
        </div>
      }

      <!-- Recording controls -->
      @if (recordingState() !== 'submitted') {
        <div class="space-y-3">
          <p class="text-xs font-semibold uppercase tracking-widest text-surface-400">Your recording</p>

          <!-- Mic permission error -->
          @if (micError()) {
            <div class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {{ micError() }}
            </div>
          }

          <!-- Idle state -->
          @if (recordingState() === 'idle') {
            <button
              (click)="startRecording()"
              class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 border-greek-300 text-greek-700 font-semibold text-sm hover:bg-greek-50 transition-colors"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/>
              </svg>
              Tap to record
            </button>
          }

          <!-- Requesting mic permission -->
          @if (recordingState() === 'requesting') {
            <div class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-surface-100 text-surface-500 text-sm">
              <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Requesting microphone access…
            </div>
          }

          <!-- Recording in progress -->
          @if (recordingState() === 'recording') {
            <div class="space-y-3">
              <div class="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-50 border border-red-200">
                <span class="w-3 h-3 rounded-full bg-red-500 animate-pulse shrink-0"></span>
                <span class="text-sm font-semibold text-red-700 flex-1">Recording…</span>
                <span class="text-sm font-mono font-bold text-red-600">{{ elapsed() }}s / {{ MAX_RECORD_SECONDS }}s</span>
              </div>
              <button
                (click)="stopRecording()"
                class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-red-500 text-white font-semibold text-sm hover:bg-red-600 transition-colors"
              >
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clip-rule="evenodd"/>
                </svg>
                Stop
              </button>
            </div>
          }

          <!-- Recorded — playback + re-record + submit -->
          @if (recordingState() === 'recorded') {
            <div class="space-y-3">
              <!-- Playback -->
              <div>
                <p class="text-xs font-semibold uppercase tracking-widest text-surface-400 mb-2">Your recording</p>
                <audio
                  [src]="recordedUrl()!"
                  controls
                  class="w-full rounded-xl"
                ></audio>
              </div>
              <!-- Actions -->
              <div class="flex gap-2">
                <button
                  (click)="resetRecording()"
                  class="flex-1 px-4 py-2.5 rounded-xl border border-surface-200 text-surface-600 text-sm font-semibold hover:bg-surface-50 transition-colors"
                >
                  Re-record
                </button>
                <button
                  (click)="submit()"
                  class="flex-1 px-4 py-2.5 rounded-xl bg-greek-600 text-white text-sm font-semibold hover:bg-greek-700 transition-colors"
                >
                  Submit
                </button>
              </div>
            </div>
          }
        </div>
      }

      <!-- Evaluation feedback -->
      @if (recordingState() === 'submitted') {
        @if (!evaluation()) {
          <div class="flex items-center gap-3 bg-greek-50 border border-greek-200 rounded-xl px-4 py-3 text-sm text-greek-700">
            <svg class="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            Evaluating your pronunciation…
          </div>
        } @else {
          <div class="space-y-3">
            <!-- Score + feedback -->
            <div class="rounded-xl border p-4 text-sm"
              [ngClass]="evaluation()!.isCorrect ? 'border-emerald-300 bg-emerald-50' : 'border-amber-200 bg-amber-50'">
              <div class="flex items-center gap-2 mb-2">
                <span class="font-semibold"
                  [ngClass]="evaluation()!.isCorrect ? 'text-emerald-700' : 'text-amber-700'">
                  Score: {{ evaluation()!.score }}/100
                </span>
                @if (evaluation()!.isCorrect) {
                  <svg class="w-4 h-4 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                  </svg>
                }
              </div>
              <p [ngClass]="evaluation()!.isCorrect ? 'text-emerald-800' : 'text-amber-800'">
                {{ evaluation()!.feedback }}
              </p>
            </div>

            <!-- Try Again button — always shown after evaluation -->
            <button
              (click)="retry()"
              class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border-2 border-greek-300 text-greek-700 font-semibold text-sm hover:bg-greek-50 transition-colors"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              Try Again
            </button>
          </div>
        }
      }
    </div>
  `,
})
export class PronunciationPracticeComponent implements OnDestroy {
  @Input({ required: true }) exercise!: Exercise;
  @Input() chapterStoragePath = '';

  /** Emits base64-encoded audio string when the student submits. */
  @Output() submitted$ = new EventEmitter<string>();
  @Output() answered = new EventEmitter<boolean>();
  /** Emits when the student clicks Try Again — parent should reset its state. */
  @Output() retried = new EventEmitter<void>();

  readonly MAX_RECORD_SECONDS = MAX_RECORD_SECONDS;

  recordingState = signal<RecordingState>('idle');
  elapsed = signal(0);
  micError = signal<string | null>(null);
  evaluation = signal<EvaluationResult | null>(null);
  recordedUrl = signal<string | null>(null);

  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private timerInterval: ReturnType<typeof setInterval> | null = null;
  private autoStopTimeout: ReturnType<typeof setTimeout> | null = null;
  private stream: MediaStream | null = null;

  targetText(): string {
    const data = this.exercise.data as unknown as PronunciationPracticeData;
    return data?.target_text ?? '';
  }

  async startRecording(): Promise<void> {
    this.micError.set(null);
    this.recordingState.set('requesting');

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: { ideal: 16000 }, channelCount: 1 },
      });
    } catch {
      this.micError.set('Microphone access denied. Please allow microphone access in your browser settings and try again.');
      this.recordingState.set('idle');
      return;
    }

    this.stream = stream;
    this.chunks = [];

    // Pick the best available MIME type — prefer low-bitrate opus
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
      ? 'audio/ogg;codecs=opus'
      : 'audio/webm';

    this.mediaRecorder = new MediaRecorder(stream, { mimeType });
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.mediaRecorder.onstop = () => this._onRecordingStopped(mimeType);

    this.mediaRecorder.start(100); // collect chunks every 100ms
    this.recordingState.set('recording');
    this.elapsed.set(0);

    // Elapsed timer
    this.timerInterval = setInterval(() => {
      this.elapsed.update(v => v + 1);
    }, 1000);

    // Auto-stop at MAX_RECORD_SECONDS
    this.autoStopTimeout = setTimeout(() => this.stopRecording(), MAX_RECORD_SECONDS * 1000);
  }

  stopRecording(): void {
    this._clearTimers();
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    // Stop all mic tracks to release the microphone indicator in the browser
    this.stream?.getTracks().forEach(t => t.stop());
    this.stream = null;
  }

  resetRecording(): void {
    // Revoke the old object URL to free memory
    if (this.recordedUrl()) {
      URL.revokeObjectURL(this.recordedUrl()!);
    }
    this.chunks = [];
    this.recordedUrl.set(null);
    this.recordingState.set('idle');
    this.elapsed.set(0);
  }

  submit(): void {
    if (this.recordingState() !== 'recorded' || !this.chunks.length) return;

    const mimeType = this.mediaRecorder?.mimeType ?? 'audio/webm';
    const blob = new Blob(this.chunks, { type: mimeType });

    // Convert to base64 and emit
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = (reader.result as string).split(',')[1]; // strip data URL prefix
      this.recordingState.set('submitted');
      this.submitted$.emit(base64);
    };
    reader.readAsDataURL(blob);
  }

  setEvaluation(result: EvaluationResult): void {
    this.evaluation.set(result);
    this.answered.emit(result.isCorrect);
  }

  /** Reset to idle so the student can record again after seeing feedback. */
  retry(): void {
    if (this.recordedUrl()) {
      URL.revokeObjectURL(this.recordedUrl()!);
    }
    this.chunks = [];
    this.recordedUrl.set(null);
    this.evaluation.set(null);
    this.micError.set(null);
    this.elapsed.set(0);
    this.recordingState.set('idle');
    this.retried.emit();
  }

  ngOnDestroy(): void {
    this._clearTimers();
    this.stopRecording();
    if (this.recordedUrl()) {
      URL.revokeObjectURL(this.recordedUrl()!);
    }
  }

  private _onRecordingStopped(mimeType: string): void {
    const blob = new Blob(this.chunks, { type: mimeType });
    const url = URL.createObjectURL(blob);
    this.recordedUrl.set(url);
    this.recordingState.set('recorded');
  }

  private _clearTimers(): void {
    if (this.timerInterval) { clearInterval(this.timerInterval); this.timerInterval = null; }
    if (this.autoStopTimeout) { clearTimeout(this.autoStopTimeout); this.autoStopTimeout = null; }
  }
}
