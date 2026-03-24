import { Component, inject, signal, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Firestore, doc, docData } from '@angular/fire/firestore';
import { AsyncPipe } from '@angular/common';
import { Observable, map, of, switchMap } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { User } from '../../core/models/firestore.models';
import { marked } from 'marked';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

@Component({
  selector: 'app-grammar-book',
  standalone: true,
  imports: [RouterLink, AsyncPipe],
  template: `
    <div class="px-6 py-8 max-w-3xl mx-auto">

      <!-- Header -->
      <div class="mb-8">
        <nav class="flex items-center gap-1.5 text-sm text-surface-400 mb-6">
          <a routerLink="/chapters" class="hover:text-greek-600 transition-colors">Course</a>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
          <span class="text-surface-600">Grammar Book</span>
        </nav>

        <div class="flex items-center gap-3 mb-2">
          <div class="w-9 h-9 rounded-lg bg-greek-600 flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
            </svg>
          </div>
          <h1 class="font-serif text-3xl font-semibold text-greek-900">My Grammar Book</h1>
        </div>
        <p class="text-surface-500 text-sm leading-relaxed">
          Your personal grammar reference, built automatically as you complete chapters.
        </p>
      </div>

      <hr class="border-surface-200 mb-8">

      @if (grammarBook$ | async; as content) {
        @if (content) {
          <!-- Rendered grammar book -->
          <div class="prose prose-sm max-w-none grammar-book-content"
            [innerHTML]="renderMarkdown(content)">
          </div>
        } @else {
          <!-- Empty state -->
          <div class="flex flex-col items-center justify-center py-16 text-center">
            <div class="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mb-4">
              <svg class="w-8 h-8 text-surface-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
              </svg>
            </div>
            <h2 class="font-serif text-lg font-semibold text-surface-700 mb-2">Your grammar book is empty</h2>
            <p class="text-surface-400 text-sm max-w-sm">
              Complete chapters to automatically build your personal grammar reference.
            </p>
            <a routerLink="/chapters"
              class="mt-6 px-5 py-2.5 rounded-xl bg-greek-600 text-white text-sm font-semibold hover:bg-greek-700 transition-colors">
              Go to Chapters
            </a>
          </div>
        }
      } @else {
        <!-- Loading skeleton -->
        <div class="animate-pulse space-y-4">
          <div class="h-6 bg-surface-200 rounded w-1/3 mb-2"></div>
          <div class="h-4 bg-surface-100 rounded w-full"></div>
          <div class="h-4 bg-surface-100 rounded w-5/6"></div>
          <div class="h-4 bg-surface-100 rounded w-4/6"></div>
          <div class="mt-6 h-6 bg-surface-200 rounded w-1/4"></div>
          <div class="h-4 bg-surface-100 rounded w-full"></div>
          <div class="h-4 bg-surface-100 rounded w-3/4"></div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host ::ng-deep .grammar-book-content h1,
    :host ::ng-deep .grammar-book-content h2,
    :host ::ng-deep .grammar-book-content h3 {
      font-family: var(--font-serif, Georgia, serif);
      color: #1a1060;
      margin-top: 1.5rem;
      margin-bottom: 0.5rem;
    }
    :host ::ng-deep .grammar-book-content h2 {
      font-size: 1.125rem;
      font-weight: 600;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 0.25rem;
    }
    :host ::ng-deep .grammar-book-content h3 {
      font-size: 0.9375rem;
      font-weight: 600;
      color: #3d3093;
    }
    :host ::ng-deep .grammar-book-content p {
      color: #4a5568;
      line-height: 1.7;
      margin-bottom: 0.75rem;
      font-size: 0.875rem;
    }
    :host ::ng-deep .grammar-book-content table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8125rem;
      margin: 0.75rem 0;
      overflow-x: auto;
      display: block;
    }
    :host ::ng-deep .grammar-book-content th,
    :host ::ng-deep .grammar-book-content td {
      border: 1px solid #e2e8f0;
      padding: 0.375rem 0.75rem;
      text-align: left;
    }
    :host ::ng-deep .grammar-book-content th {
      background-color: #f8f7f4;
      font-weight: 600;
      color: #3d3093;
    }
    :host ::ng-deep .grammar-book-content tr:nth-child(even) td {
      background-color: #faf9f7;
    }
    :host ::ng-deep .grammar-book-content ul,
    :host ::ng-deep .grammar-book-content ol {
      padding-left: 1.25rem;
      margin-bottom: 0.75rem;
      font-size: 0.875rem;
      color: #4a5568;
    }
    :host ::ng-deep .grammar-book-content li {
      margin-bottom: 0.25rem;
    }
    :host ::ng-deep .grammar-book-content strong {
      color: #1a1060;
      font-weight: 600;
    }
    :host ::ng-deep .grammar-book-content em {
      color: #3d3093;
    }
    :host ::ng-deep .grammar-book-content hr {
      border-color: #e2e8f0;
      margin: 1.5rem 0;
    }
    :host ::ng-deep .grammar-book-content blockquote {
      border-left: 3px solid #3d3093;
      padding-left: 1rem;
      color: #718096;
      font-style: italic;
      margin: 0.75rem 0;
    }
  `],
})
export class GrammarBookPage {
  private firestore = inject(Firestore);
  private authService = inject(AuthService);
  private sanitizer = inject(DomSanitizer);

  grammarBook$: Observable<string | null> = new Observable(observer => {
    const uid = this.authService.firebaseUser()?.uid;
    if (!uid) {
      observer.next(null);
      observer.complete();
      return;
    }
    const ref = doc(this.firestore, 'users', uid);
    const sub = (docData(ref) as Observable<User>)
      .pipe(map(u => u?.grammar_book ?? null))
      .subscribe(observer);
    return () => sub.unsubscribe();
  });

  renderMarkdown(md: string): SafeHtml {
    const html = marked.parse(md, { async: false }) as string;
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }
}
