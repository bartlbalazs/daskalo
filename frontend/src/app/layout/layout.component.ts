import { Component, inject, signal, OnInit, HostListener } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AsyncPipe } from '@angular/common';
import { Observable } from 'rxjs';
import { AuthService } from '../core/services/auth.service';
import { LessonService } from '../core/services/lesson.service';
import { Book, Chapter } from '../core/models/firestore.models';

interface SidebarBook extends Book {
  chapters$: Observable<Chapter[]>;
}

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, AsyncPipe],
  template: `
    <div class="min-h-screen flex flex-col bg-greek-50">

      <!-- ====== FIXED TOP HEADER ====== -->
      <header class="fixed top-0 left-0 right-0 h-14 bg-greek-700 text-white flex items-center gap-3 px-4 shadow-lg z-50">
        <!-- Sidebar toggle -->
        <button
          (click)="toggleSidebar()"
          class="p-2 rounded-lg hover:bg-greek-600 transition-colors shrink-0"
          [attr.aria-label]="sidebarOpen() ? 'Close sidebar' : 'Open sidebar'"
        >
          @if (sidebarOpen()) {
            <!-- X icon -->
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          } @else {
            <!-- Hamburger icon -->
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          }
        </button>

        <!-- Logo -->
        <a routerLink="/chapters" class="font-serif text-xl font-semibold tracking-wide shrink-0 hover:opacity-90 transition-opacity">
          Δάσκαλο
        </a>

        <div class="flex-1"></div>

        <!-- XP badge -->
        @if (authService.currentUser(); as user) {
          <div class="flex items-center gap-1.5 bg-greek-800 rounded-full px-3 py-1 text-sm">
            <svg class="w-3.5 h-3.5 text-gold-400" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
            </svg>
            <span class="font-semibold text-gold-400">{{ user.progress.xp }}</span>
            <span class="text-greek-300 font-normal">XP</span>
          </div>
        }

        <!-- User avatar + dropdown menu -->
        @if (authService.firebaseUser(); as fbUser) {
          <div class="relative">
            <button
              (click)="toggleUserMenu()"
              class="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-greek-600 transition-colors"
              aria-haspopup="true"
              [attr.aria-expanded]="userMenuOpen()"
            >
              @if (fbUser.photoURL) {
                <img
                  [src]="fbUser.photoURL"
                  [alt]="fbUser.displayName ?? 'User'"
                  class="w-8 h-8 rounded-full ring-2 ring-greek-400 object-cover"
                />
              } @else {
                <div class="w-8 h-8 rounded-full bg-greek-500 ring-2 ring-greek-400 flex items-center justify-center text-sm font-semibold">
                  {{ (fbUser.displayName ?? 'U')[0].toUpperCase() }}
                </div>
              }
              <span class="text-sm font-medium hidden sm:block">{{ firstName(fbUser.displayName) }}</span>
              <svg class="w-3.5 h-3.5 text-greek-300 hidden sm:block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
              </svg>
            </button>

            <!-- Dropdown -->
            @if (userMenuOpen()) {
              <div class="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-xl border border-surface-200 py-1 z-50 overflow-hidden">
                <div class="px-4 py-2.5 border-b border-surface-100">
                  <p class="text-sm font-semibold text-surface-800 truncate">{{ fbUser.displayName }}</p>
                  <p class="text-xs text-surface-400 truncate">{{ fbUser.email }}</p>
                </div>
                <button
                  (click)="signOut()"
                  class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                  </svg>
                  Sign out
                </button>
              </div>
            }
          </div>
        }
      </header>

      <!-- Horizontal nav links (desktop) injected just below brand -->
      <div class="fixed top-14 left-0 right-0 hidden md:flex items-center gap-1 bg-greek-600 px-4 h-10 z-40 shadow-sm">
        <a
          routerLink="/chapters"
          routerLinkActive="bg-greek-500 text-white font-semibold"
          [routerLinkActiveOptions]="{ exact: false }"
          class="flex items-center gap-1.5 px-3 py-1 rounded-md text-sm text-greek-100 hover:bg-greek-500 hover:text-white transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
          </svg>
          Course
        </a>
        <a
          routerLink="/grammar-book"
          routerLinkActive="bg-greek-500 text-white font-semibold"
          [routerLinkActiveOptions]="{ exact: true }"
          class="flex items-center gap-1.5 px-3 py-1 rounded-md text-sm text-greek-100 hover:bg-greek-500 hover:text-white transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
          </svg>
          Grammar Book
        </a>
        <a
          routerLink="/vocabulary"
          routerLinkActive="bg-greek-500 text-white font-semibold"
          [routerLinkActiveOptions]="{ exact: true }"
          class="flex items-center gap-1.5 px-3 py-1 rounded-md text-sm text-greek-100 hover:bg-greek-500 hover:text-white transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"/>
          </svg>
          Vocabulary
        </a>
      </div>

      <!-- ====== BODY (sidebar + content) — pushed down by fixed header ====== -->
      <div class="flex flex-1 pt-14 md:pt-24 overflow-hidden relative">

        <!-- Sidebar backdrop (mobile) -->
        @if (sidebarOpen()) {
          <div
            class="fixed inset-0 top-14 bg-black/40 z-30 lg:hidden"
            (click)="closeSidebar()"
          ></div>
        }

        <!-- ====== SIDEBAR ====== -->
        <aside
          class="fixed top-14 md:top-24 bottom-0 left-0 z-30 bg-white border-r border-greek-100 overflow-y-auto flex flex-col transition-all duration-250 ease-in-out shadow-lg"
          [style.width]="sidebarOpen() ? '16rem' : '0'"
          [style.min-width]="sidebarOpen() ? '16rem' : '0'"
        >
          <div class="w-64 flex flex-col flex-1">
            <!-- Sidebar header -->
            <div class="px-4 pt-5 pb-3 border-b border-greek-100 bg-greek-50">
              <p class="text-xs font-semibold uppercase tracking-widest text-greek-600">Course Map</p>
            </div>

            <!-- Nav -->
            <nav class="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
              @for (book of sidebarBooks; track book.id) {
                <div>
                  <!-- Book header -->
                  <div class="flex items-center gap-2 px-2 mb-2">
                    <div class="w-5 h-5 rounded bg-greek-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                      {{ book.order }}
                    </div>
                    <span class="text-xs font-bold uppercase tracking-widest text-greek-700">
                      Book {{ book.order }}
                    </span>
                  </div>
                  <p class="px-2 text-xs text-surface-400 mb-3 leading-snug">{{ book.title }}</p>

                  <!-- Chapters in this book -->
                  <ul class="space-y-0.5">
                    @for (chapter of book.chapters$ | async; track chapter.id) {
                      <li>
                        <a
                          [routerLink]="['/chapters', chapter.id]"
                          routerLinkActive="bg-greek-100 text-greek-800 font-semibold"
                          [routerLinkActiveOptions]="{ exact: true }"
                          class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-surface-600 hover:bg-greek-50 hover:text-greek-800 transition-colors group"
                          (click)="closeSidebarOnMobile()"
                        >
                          <!-- Status icon -->
                          @if (isCompleted(chapter.id)) {
                            <svg class="w-4 h-4 text-greek-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                            </svg>
                          } @else {
                            <span class="w-4 h-4 rounded-full border-2 border-surface-300 group-hover:border-greek-400 shrink-0 transition-colors"></span>
                          }
                          <span class="truncate">{{ chapter.order }}. {{ chapter.title }}</span>
                        </a>
                      </li>
                    }
                  </ul>
                </div>
              }

              @if (!booksLoaded) {
                <p class="px-2 text-xs text-surface-400">Loading course…</p>
              } @else if (sidebarBooks.length === 0) {
                <p class="px-2 text-xs text-surface-400">No books available.</p>
              }
            </nav>

            <!-- Sidebar footer links -->
            <div class="px-3 py-4 border-t border-greek-100 bg-greek-50 space-y-0.5">
              <a
                routerLink="/grammar-book"
                routerLinkActive="bg-greek-100 text-greek-800 font-semibold"
                [routerLinkActiveOptions]="{ exact: true }"
                class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-surface-600 hover:bg-greek-100 hover:text-greek-800 transition-colors"
                (click)="closeSidebarOnMobile()"
              >
                <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                </svg>
                <span>Grammar Book</span>
              </a>
              <a
                routerLink="/vocabulary"
                routerLinkActive="bg-greek-100 text-greek-800 font-semibold"
                [routerLinkActiveOptions]="{ exact: true }"
                class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-surface-600 hover:bg-greek-100 hover:text-greek-800 transition-colors"
                (click)="closeSidebarOnMobile()"
              >
                <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"/>
                </svg>
                <span>Vocabulary</span>
              </a>
            </div>
          </div>
        </aside>

        <!-- ====== MAIN CONTENT ====== -->
        <main
          class="flex-1 overflow-y-auto transition-all duration-250 ease-in-out"
          [style.margin-left]="sidebarOpen() && isDesktop() ? '16rem' : '0'"
        >
          <router-outlet />
        </main>
      </div>
    </div>
  `,
})
export class LayoutComponent implements OnInit {
  readonly authService = inject(AuthService);
  private readonly lessonService = inject(LessonService);

  sidebarOpen = signal(this.getInitialSidebarState());
  isDesktop = signal(window.innerWidth >= 1024);
  userMenuOpen = signal(false);

  sidebarBooks: SidebarBook[] = [];
  booksLoaded = false;

  ngOnInit(): void {
    this.lessonService.getBooks().subscribe((books) => {
      this.sidebarBooks = books.map((book) => ({
        ...book,
        chapters$: this.lessonService.getChaptersByBook(book.id),
      }));
      this.booksLoaded = true;
    });

    window.addEventListener('resize', () => {
      const desktop = window.innerWidth >= 1024;
      this.isDesktop.set(desktop);
      if (desktop && !this.sidebarOpen()) {
        // Re-open on desktop if it was closed due to resize
      }
    });
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('[aria-haspopup]')) {
      this.userMenuOpen.set(false);
    }
  }

  private getInitialSidebarState(): boolean {
    // Open by default on desktop, closed on mobile
    return typeof window !== 'undefined' && window.innerWidth >= 1024;
  }

  toggleSidebar(): void {
    this.sidebarOpen.update((v) => !v);
  }

  closeSidebar(): void {
    this.sidebarOpen.set(false);
  }

  closeSidebarOnMobile(): void {
    if (!this.isDesktop()) {
      this.sidebarOpen.set(false);
    }
  }

  toggleUserMenu(): void {
    this.userMenuOpen.update((v) => !v);
  }

  firstName(displayName: string | null | undefined): string {
    if (!displayName) return '';
    return displayName.split(' ')[0];
  }

  isCompleted(chapterId: string): boolean {
    const completedIds = this.authService.currentUser()?.progress?.completedChapterIds ?? [];
    return completedIds.includes(chapterId);
  }

  async signOut(): Promise<void> {
    this.userMenuOpen.set(false);
    await this.authService.signOut();
  }
}
