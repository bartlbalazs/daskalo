import { Component, Input, Output, EventEmitter, HostListener } from '@angular/core';

@Component({
  selector: 'app-lightbox',
  standalone: true,
  template: `
    @if (imageUrl) {
      <div
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm cursor-zoom-out"
        (click)="close()"
      >
        <!-- Close button -->
        <button
          class="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors"
          aria-label="Close"
          (click)="close()"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>

        <!-- Full image -->
        <img
          [src]="imageUrl"
          alt=""
          class="max-h-[90vh] max-w-[90vw] object-contain rounded-lg shadow-2xl"
          (click)="$event.stopPropagation()"
        />
      </div>
    }
  `,
})
export class LightboxComponent {
  @Input() imageUrl: string | null = null;
  @Output() closed = new EventEmitter<void>();

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.imageUrl) this.close();
  }

  close(): void {
    this.closed.emit();
  }
}
