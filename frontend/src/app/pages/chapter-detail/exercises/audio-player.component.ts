import {
  Component, OnDestroy, signal, inject, input, effect
} from '@angular/core';
import { Storage, ref, getDownloadURL } from '@angular/fire/storage';

@Component({
  selector: 'app-audio-player',
  standalone: true,
  template: `
    <div class="flex items-center gap-3 bg-greek-50 border border-greek-100 rounded-xl px-4 py-3">
      <!-- Play / Pause button -->
      <button
        (click)="toggle()"
        [disabled]="loading()"
        class="w-9 h-9 rounded-full bg-greek-600 text-white flex items-center justify-center shrink-0 hover:bg-greek-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        [attr.aria-label]="playing() ? 'Pause' : 'Play'"
      >
        @if (loading()) {
          <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
          </svg>
        } @else if (playing()) {
          <!-- Pause icon -->
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
        } @else {
          <!-- Play icon -->
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
          </svg>
        }
      </button>

      <!-- Progress bar / scrubber -->
      <div class="flex-1">
        <div class="relative h-4 flex items-center group">
          <!-- Track background -->
          <div class="absolute inset-x-0 h-1.5 bg-greek-200 rounded-full overflow-hidden pointer-events-none">
            <div
              class="h-full bg-greek-600 rounded-full"
              [style.width]="progressPercent() + '%'"
            ></div>
          </div>
          <!-- Thumb dot -->
          <div
            class="absolute w-3 h-3 bg-greek-600 rounded-full shadow pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity -translate-x-1/2"
            [style.left]="progressPercent() + '%'"
          ></div>
          <!-- Native range input (invisible, sits on top for interaction) -->
          <input
            type="range"
            min="0"
            max="100"
            step="0.1"
            [value]="progressPercent()"
            (input)="onSeek($event)"
            [disabled]="loading() || duration() === 0"
            class="absolute inset-0 w-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            aria-label="Seek"
          />
        </div>
        <div class="flex justify-between mt-1">
          <span class="text-xs text-greek-500">{{ formatTime(currentTime()) }}</span>
          <span class="text-xs text-greek-400">{{ formatTime(duration()) }}</span>
        </div>
      </div>

      <!-- Replay button -->
      <button
        (click)="replay()"
        class="w-7 h-7 rounded-full text-greek-400 flex items-center justify-center hover:text-greek-600 hover:bg-greek-100 transition-colors"
        title="Replay"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
      </button>
    </div>
  `,
})
export class AudioPlayerComponent implements OnDestroy {
  /** A gs:// URI or plain HTTP URL. Required, but declared as optional to avoid
   *  NG0950 (required input read before binding in constructor effect). The
   *  effect guards against undefined/empty values so no audio loads until a
   *  real URL is provided by the parent. */
  src = input<string>();

  private storage = inject(Storage);

  loading = signal(true);
  playing = signal(false);
  currentTime = signal(0);
  duration = signal(0);
  progressPercent = signal(0);

  private audio: HTMLAudioElement | null = null;

  // Generation counter: if src changes while a getDownloadURL() promise is in
  // flight, the stale promise resolution will see a mismatched generation and
  // discard its result rather than overwriting the new audio.
  private generation = 0;

  constructor() {
    effect(() => {
      const src = this.src();
      // Guard: do nothing until Angular has bound a real URL.
      if (!src) return;
      this._loadSrc(src);
    }, { allowSignalWrites: true });
  }

  ngOnDestroy(): void {
    this._destroyAudio();
  }

  toggle(): void {
    if (!this.audio) return;
    if (this.playing()) {
      this.audio.pause();
    } else {
      this.audio.play();
    }
  }

  onSeek(event: Event): void {
    if (!this.audio || !this.duration()) return;
    const percent = Number((event.target as HTMLInputElement).value);
    const targetTime = (percent / 100) * this.duration();
    this.audio.currentTime = targetTime;
    this.currentTime.set(targetTime);
    this.progressPercent.set(percent);
  }

  replay(): void {
    if (!this.audio) return;
    this.audio.currentTime = 0;
    this.audio.play();
  }

  formatTime(seconds: number): string {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  private async _loadSrc(src: string): Promise<void> {
    // Tear down any existing audio immediately so the old chapter stops.
    this._destroyAudio();

    // Reset state for the new source.
    this.loading.set(true);
    this.currentTime.set(0);
    this.duration.set(0);
    this.progressPercent.set(0);
    this.playing.set(false);

    // Capture this load's generation so a stale promise can't overwrite a
    // newer one if src changes again before this resolves.
    const gen = ++this.generation;

    try {
      const url = src.startsWith('gs://')
        ? await getDownloadURL(ref(this.storage, src))
        : src;

      // If src changed while we were awaiting, discard this result.
      if (gen !== this.generation) return;

      this._initAudio(url);
    } catch {
      if (gen !== this.generation) return;
      this.loading.set(false);
    }
  }

  private _initAudio(url: string): void {
    this.audio = new Audio(url);
    this.audio.preload = 'metadata';

    this.audio.addEventListener('loadedmetadata', () => {
      if (!this.audio) return;
      this.duration.set(this.audio.duration);
      this.loading.set(false);
    });
    this.audio.addEventListener('play', () => this.playing.set(true));
    this.audio.addEventListener('pause', () => this.playing.set(false));
    this.audio.addEventListener('ended', () => {
      this.playing.set(false);
      this.currentTime.set(0);
      this.progressPercent.set(0);
    });
    this.audio.addEventListener('timeupdate', () => {
      if (!this.audio) return;
      const t = this.audio.currentTime;
      const d = this.audio.duration || 1;
      this.currentTime.set(t);
      this.progressPercent.set((t / d) * 100);
    });
  }

  private _destroyAudio(): void {
    if (this.audio) {
      // Null this.audio BEFORE clearing src so that any async error/other events
      // fired by src='' see a null reference and bail out via their guards,
      // rather than writing stale signal values (e.g. error.set(true)) that
      // would permanently hide the player after navigation.
      const dying = this.audio;
      this.audio = null;
      dying.pause();
      dying.src = '';
    }
  }
}
