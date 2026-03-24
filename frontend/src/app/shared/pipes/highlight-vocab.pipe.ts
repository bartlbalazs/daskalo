import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { VocabularyItem } from '../../core/models/firestore.models';

/**
 * Highlights chapter vocabulary words inside a Greek text string.
 * Matched words get a dotted underline + a CSS tooltip showing the English translation.
 *
 * Usage:
 *   <span [innerHTML]="text | highlightVocab:vocabulary"></span>
 */
@Pipe({ name: 'highlightVocab', standalone: true, pure: true })
export class HighlightVocabPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer);

  transform(text: string | null | undefined, vocab: VocabularyItem[] | null | undefined): SafeHtml {
    if (!text) return '';
    if (!vocab || vocab.length === 0) return this.sanitizer.bypassSecurityTrustHtml(this._escape(text));

    // Sort longest first so "ο σκύλος" matches before "σκύλος"
    const sorted = [...vocab].sort((a, b) => b.greek.length - a.greek.length);

    // Escape the base text first to avoid XSS
    let result = this._escape(text);

    for (const item of sorted) {
      const escapedGreek = this._escape(item.greek);
      const escapedEnglish = this._escape(item.english);

      // Build a regex that matches the exact word(s); use Unicode letter boundaries
      // We strip leading/trailing articles for a slightly wider match surface but
      // also try the full form first (longer match wins because we sorted by length).
      const pattern = escapedGreek.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(?<![\\w\\u0370-\\u03FF\\u1F00-\\u1FFF])(${pattern})(?![\\w\\u0370-\\u03FF\\u1F00-\\u1FFF])`, 'gi');

      result = result.replace(regex, (match) =>
        `<span class="vocab-highlight" data-translation="${escapedEnglish}">${match}</span>`
      );
    }

    return this.sanitizer.bypassSecurityTrustHtml(result);
  }

  private _escape(s: string): string {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}
