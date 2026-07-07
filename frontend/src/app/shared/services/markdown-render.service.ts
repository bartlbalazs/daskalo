import { Injectable, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

/**
 * Renders trusted Markdown content (chapter grammar notes, grammar tables,
 * the auto-generated grammar book summaries) to sanitized HTML.
 *
 * `marked` itself does NOT sanitize embedded raw HTML (it deliberately passes
 * it through), so any malformed/malicious HTML embedded in Gemini-generated
 * `grammarSummary` / `grammar_table` / `explanation` content would otherwise
 * be able to execute via `DomSanitizer.bypassSecurityTrustHtml()`. DOMPurify
 * strips dangerous markup (script tags, event handler attributes, javascript:
 * URIs in href/src, etc.) before we tell Angular to trust the result — this
 * is the sanitizer `marked`'s own docs recommend pairing it with.
 *
 * Both render methods are called directly from templates (`chapter-detail.page.ts`,
 * `grammar-book.page.ts`), which re-invoke them on every change-detection cycle
 * the host component runs — e.g. ~4x/s while a sibling audio player emits
 * `timeupdate` events. Without memoization, that reruns `marked.parse()` +
 * `DOMPurify.sanitize()` on unchanged content on every one of those cycles.
 * Caching by the raw markdown string avoids that: the curriculum content
 * rendered here comes from a finite, content-cli-authored dataset (not
 * unbounded user input), so an ever-growing cache with no eviction is a
 * non-issue in practice.
 */
@Injectable({ providedIn: 'root' })
export class MarkdownRenderService {
  private sanitizer = inject(DomSanitizer);

  private readonly blockCache = new Map<string, SafeHtml>();
  private readonly inlineCache = new Map<string, SafeHtml>();

  /** Render full (block-level) Markdown — headings, tables, lists, etc. */
  renderBlock(markdown: string | null | undefined): SafeHtml {
    if (!markdown) return '';
    const cached = this.blockCache.get(markdown);
    if (cached !== undefined) return cached;

    const rawHtml = marked.parse(markdown, { async: false }) as string;
    const safeHtml = this.sanitizer.bypassSecurityTrustHtml(DOMPurify.sanitize(rawHtml));
    this.blockCache.set(markdown, safeHtml);
    return safeHtml;
  }

  /** Render inline-only Markdown (bold, italic, code) without block wrapping. */
  renderInline(markdown: string | null | undefined): SafeHtml {
    if (!markdown) return '';
    const cached = this.inlineCache.get(markdown);
    if (cached !== undefined) return cached;

    const rawHtml = marked.parseInline(markdown, { async: false }) as string;
    const safeHtml = this.sanitizer.bypassSecurityTrustHtml(DOMPurify.sanitize(rawHtml));
    this.inlineCache.set(markdown, safeHtml);
    return safeHtml;
  }
}
