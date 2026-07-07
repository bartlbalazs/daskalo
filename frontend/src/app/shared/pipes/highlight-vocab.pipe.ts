import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { VocabularyItem } from '../../core/models/firestore.models';

interface MatchSpan {
  start: number;
  end: number;
  englishEscaped: string;
}

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
    // Escape the base text once up front to avoid XSS.
    const escapedText = this._escape(text);
    if (!vocab || vocab.length === 0) return this.sanitizer.bypassSecurityTrustHtml(escapedText);

    // Sort longest first so "ο σκύλος" matches before "σκύλος" when they overlap.
    const sorted = [...vocab].sort((a, b) => b.greek.length - a.greek.length);

    // Pass 1: find every candidate match against the ORIGINAL escaped text
    // only — never against previously-transformed HTML. This guarantees a
    // shorter vocab entry can't accidentally match inside a <span> already
    // inserted for a longer entry (e.g. inside its data-translation="..."
    // attribute, which can legitimately contain Greek text for bilingual
    // glosses like "coffee (καφές)").
    const candidates: MatchSpan[] = [];
    for (const item of sorted) {
      const escapedGreek = this._escape(item.greek);
      const escapedEnglish = this._escape(item.english);

      const pattern = escapedGreek.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(?<![\\w\\u0370-\\u03FF\\u1F00-\\u1FFF])(${pattern})(?![\\w\\u0370-\\u03FF\\u1F00-\\u1FFF])`, 'gi');

      let match: RegExpExecArray | null;
      while ((match = regex.exec(escapedText)) !== null) {
        candidates.push({
          start: match.index,
          end: match.index + match[0].length,
          englishEscaped: escapedEnglish,
        });
        if (match[0].length === 0) regex.lastIndex++; // defensive: avoid an infinite loop
      }
    }

    // Pass 2: resolve overlaps — longer matches win (ties broken by earliest
    // start), matching the original "longest vocab entry wins" intent.
    candidates.sort((a, b) => (b.end - b.start) - (a.end - a.start) || a.start - b.start);
    const accepted: MatchSpan[] = [];
    for (const candidate of candidates) {
      const overlapsAccepted = accepted.some(a => candidate.start < a.end && candidate.end > a.start);
      if (!overlapsAccepted) accepted.push(candidate);
    }
    accepted.sort((a, b) => a.start - b.start);

    // Pass 3: build the final HTML in a single pass over the original escaped
    // text using only the accepted, non-overlapping spans.
    let result = '';
    let cursor = 0;
    for (const span of accepted) {
      result += escapedText.slice(cursor, span.start);
      result += `<span class="vocab-highlight" data-translation="${span.englishEscaped}">${escapedText.slice(span.start, span.end)}</span>`;
      cursor = span.end;
    }
    result += escapedText.slice(cursor);

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
