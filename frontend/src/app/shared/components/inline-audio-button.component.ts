import { Component, OnDestroy, signal, inject, input, effect } from '@angular/core';
import { Storage, ref, getDownloadURL } from '@angular/fire/storage';

/**
 * A small circular play/pause button for inline audio playback.
 * Accepts a gs:// URI or a plain HTTP URL via the `src` input.
 * Resolves Firebase Storage gs:// URIs automatically.
 *
 * Usage:
 *   <app-inline-audio-button [src]="example.audioUrl" />
 */
@Component({
  selector: 'app-inline-audio-button',
  standalone: true,
  template: `
    <button
      (click)="toggle()"
      [disabled]="loading()"
      class="shrink-0 w-9 h-9 rounded-full bg-greek-100 text-greek-600 flex items-center justify-center hover:bg-greek-600 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      [attr.aria-label]="playing() ? 'Pause' : 'Play example'"
      title="Play example"
    >
      @if (loading()) {
        <!-- Spinner -->
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
  `,
})
export class InlineAudioButtonComponent implements OnDestroy {
  private storage = inject(Storage);

  src = input.required<string>();

  loading = signal(false);
  playing = signal(false);

  private audio: HTMLAudioElement | null = null;
  private resolvedUrl: string | null = null;
  private srcGeneration = 0;

  constructor() {
    effect(() => {
      const newSrc = this.src();
      this.srcGeneration++;
      this.resolvedUrl = null;
      this.stopAudio();
      if (newSrc) {
        this.resolveUrl(newSrc, this.srcGeneration);
      }
    });
  }

  ngOnDestroy(): void {
    this.stopAudio();
  }

  toggle(): void {
    if (this.playing()) {
      this.pauseAudio();
    } else {
      this.playAudio();
    }
  }

  private playAudio(): void {
    if (this.resolvedUrl) {
      this.startPlayback(this.resolvedUrl);
      return;
    }
    const url = this.src();
    if (!url) return;
    this.loading.set(true);
    this.resolveUrl(url, this.srcGeneration).then(() => {
      if (this.resolvedUrl) {
        this.startPlayback(this.resolvedUrl);
      }
    });
  }

  private async resolveUrl(url: string, generation: number): Promise<void> {
    if (!url.startsWith('gs://')) {
      this.resolvedUrl = url;
      this.loading.set(false);
      return;
    }
    try {
      const resolved = await getDownloadURL(ref(this.storage, url));
      if (generation === this.srcGeneration) {
        this.resolvedUrl = resolved;
      }
    } catch {
      if (generation === this.srcGeneration) {
        this.loading.set(false);
      }
    }
  }

  private startPlayback(url: string): void {
    this.stopAudio();
    this.loading.set(false);
    const audio = new Audio(url);
    this.audio = audio;
    audio.onplay = () => this.playing.set(true);
    audio.onpause = () => this.playing.set(false);
    audio.onended = () => this.playing.set(false);
    audio.onerror = () => {
      this.loading.set(false);
      this.playing.set(false);
    };
    audio.play().catch(() => {
      this.loading.set(false);
      this.playing.set(false);
    });
  }

  private pauseAudio(): void {
    this.audio?.pause();
  }

  private stopAudio(): void {
    if (this.audio) {
      this.audio.pause();
      this.audio.src = '';
      this.audio.onplay = null;
      this.audio.onpause = null;
      this.audio.onended = null;
      this.audio.onerror = null;
      this.audio = null;
    }
    this.playing.set(false);
    this.loading.set(false);
  }
}
