import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-greek-900 via-greek-800 to-greek-600 px-4">

      <!-- Decorative background elements -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
        <div class="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-white/5 blur-3xl"></div>
        <div class="absolute -bottom-32 -right-32 w-[32rem] h-[32rem] rounded-full bg-white/5 blur-3xl"></div>
        <div class="absolute bottom-0 left-0 right-0 h-32 opacity-10"
          style="background-image: repeating-linear-gradient(0deg, transparent, transparent 6px, rgba(255,255,255,0.3) 6px, rgba(255,255,255,0.3) 7px);">
        </div>
      </div>

      <!-- Card -->
      <div class="relative bg-white rounded-2xl shadow-2xl p-10 w-full max-w-sm text-center">

        <!-- Brand mark -->
        <div class="flex items-center justify-center w-14 h-14 rounded-2xl bg-greek-600 mx-auto mb-5 shadow-lg">
          <span class="text-white font-serif font-bold text-2xl leading-none">Δ</span>
        </div>

        <h1 class="font-serif text-3xl font-semibold text-greek-900 mb-1">Δάσκαλο</h1>
        <p class="text-surface-400 text-sm mb-8">Learn Modern Greek — the real way.</p>

        <!-- Tab toggle -->
        <div class="flex rounded-xl bg-surface-50 p-1 mb-6 gap-1">
          <button
            (click)="mode.set('signin')"
            [class]="mode() === 'signin'
              ? 'flex-1 py-2 rounded-lg text-sm font-medium bg-white shadow-sm text-greek-800 transition-all'
              : 'flex-1 py-2 rounded-lg text-sm font-medium text-surface-400 transition-all hover:text-surface-600'"
          >Sign In</button>
          <button
            (click)="mode.set('signup')"
            [class]="mode() === 'signup'
              ? 'flex-1 py-2 rounded-lg text-sm font-medium bg-white shadow-sm text-greek-800 transition-all'
              : 'flex-1 py-2 rounded-lg text-sm font-medium text-surface-400 transition-all hover:text-surface-600'"
          >Sign Up</button>
        </div>

        <!-- Form -->
        <form (ngSubmit)="submit()" #f="ngForm" class="flex flex-col gap-3 text-left">
          <div>
            <label class="block text-xs font-medium text-surface-500 mb-1" for="email">Email</label>
            <input
              id="email"
              type="email"
              name="email"
              [(ngModel)]="email"
              required
              autocomplete="email"
              placeholder="you@example.com"
              class="w-full border border-surface-200 rounded-xl px-4 py-2.5 text-sm text-surface-800 placeholder-surface-300 focus:outline-none focus:ring-2 focus:ring-greek-400 focus:border-transparent transition"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-surface-500 mb-1" for="password">Password</label>
            <input
              id="password"
              type="password"
              name="password"
              [(ngModel)]="password"
              required
              autocomplete="current-password"
              placeholder="••••••••"
              class="w-full border border-surface-200 rounded-xl px-4 py-2.5 text-sm text-surface-800 placeholder-surface-300 focus:outline-none focus:ring-2 focus:ring-greek-400 focus:border-transparent transition"
            />
          </div>

          <!-- Error message -->
          @if (error()) {
            <p class="text-red-500 text-xs mt-1">{{ error() }}</p>
          }

          <button
            type="submit"
            [disabled]="loading()"
            class="w-full mt-2 bg-greek-600 hover:bg-greek-700 active:bg-greek-800 disabled:opacity-50 text-white font-medium rounded-xl px-4 py-3 transition-all shadow-sm"
          >
            {{ loading() ? 'Please wait…' : (mode() === 'signin' ? 'Sign In' : 'Create Account') }}
          </button>
        </form>

        <p class="mt-6 text-xs text-surface-300">
          New users are reviewed before gaining access.
        </p>
      </div>
    </div>
  `,
})
export class LoginPage {
  private authService = inject(AuthService);

  mode = signal<'signin' | 'signup'>('signin');
  email = '';
  password = '';
  loading = signal(false);
  error = signal('');

  async submit(): Promise<void> {
    this.error.set('');
    this.loading.set(true);
    try {
      if (this.mode() === 'signin') {
        await this.authService.signIn(this.email, this.password);
      } else {
        await this.authService.signUp(this.email, this.password);
      }
    } catch (err: unknown) {
      this.error.set(this.friendlyError(err));
    } finally {
      this.loading.set(false);
    }
  }

  private friendlyError(err: unknown): string {
    const code = (err as { code?: string })?.code ?? '';
    const messages: Record<string, string> = {
      'auth/invalid-email': 'Invalid email address.',
      'auth/user-not-found': 'No account found with this email.',
      'auth/wrong-password': 'Incorrect password.',
      'auth/invalid-credential': 'Incorrect email or password.',
      'auth/email-already-in-use': 'An account with this email already exists.',
      'auth/weak-password': 'Password must be at least 6 characters.',
      'auth/too-many-requests': 'Too many attempts. Please try again later.',
      'auth/network-request-failed': 'Network error. Check your connection.',
    };
    return messages[code] ?? `Something went wrong (${code || 'unknown'}). Please try again.`;
  }
}
