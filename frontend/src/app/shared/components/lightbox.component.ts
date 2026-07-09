import {
  Component, Input, Output, EventEmitter, HostListener, OnChanges, SimpleChanges,
  ElementRef, ViewChild
} from '@angular/core';

@Component({
  selector: 'app-lightbox',
  standalone: true,
  template: `
    @if (imageUrl) {
      <!-- Backdrop is a decorative click-outside-to-close target; keyboard/AT
           users close via Escape (onEscape() below) or the Close button.
           (keydown) below also implements the focus-trap Tab handling. -->
      <div
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm cursor-zoom-out"
        role="dialog"
        aria-modal="true"
        aria-label="Image viewer"
        (click)="close()"
        (keydown)="onDialogKeydown($event)"
      >
        <!-- Close button -->
        <button
          #closeButton
          class="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors"
          aria-label="Close"
          (click)="close()"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>

        <!-- Full image — click only stops the backdrop's close-on-click from
             firing; not a keyboard-operable control itself, so no keyboard
             equivalent is needed here. -->
        <!-- eslint-disable-next-line @angular-eslint/template/click-events-have-key-events, @angular-eslint/template/interactive-supports-focus -->
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
export class LightboxComponent implements OnChanges {
  @Input() imageUrl: string | null = null;
  @Output() closed = new EventEmitter<void>();

  @ViewChild('closeButton') private closeButtonRef?: ElementRef<HTMLButtonElement>;

  /** Element that had focus before the lightbox opened, so it can be restored on close. */
  private previouslyFocusedElement: HTMLElement | null = null;

  ngOnChanges(changes: SimpleChanges): void {
    const change = changes['imageUrl'];
    if (!change) return;

    const wasOpen = !!change.previousValue;
    const isOpen = !!change.currentValue;

    if (!wasOpen && isOpen) {
      // Just opened — remember what had focus, then move focus into the
      // dialog (onto the Close button, its only focusable descendant).
      this.previouslyFocusedElement = document.activeElement as HTMLElement;
      // Defer to the next tick: the @if just became true this same
      // change-detection cycle, so #closeButton isn't in the DOM yet.
      setTimeout(() => this.closeButtonRef?.nativeElement.focus());
    } else if (wasOpen && !isOpen) {
      // Just closed — restore focus to whatever opened it.
      this.previouslyFocusedElement?.focus();
      this.previouslyFocusedElement = null;
    }
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.imageUrl) this.close();
  }

  /** Minimal focus trap: this dialog has exactly one focusable descendant
   *  (the Close button), so Tab (with or without Shift) should just keep
   *  focus there instead of escaping to the page behind the lightbox. */
  onDialogKeydown(event: KeyboardEvent): void {
    if (event.key === 'Tab') {
      event.preventDefault();
      this.closeButtonRef?.nativeElement.focus();
    }
  }

  close(): void {
    this.closed.emit();
  }
}
