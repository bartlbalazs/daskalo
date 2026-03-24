import { Component, inject } from '@angular/core';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  template: `
    <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-greek-900 via-greek-800 to-greek-600 px-4">

      <!-- Decorative background elements -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
        <div class="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-white/5 blur-3xl"></div>
        <div class="absolute -bottom-32 -right-32 w-[32rem] h-[32rem] rounded-full bg-white/5 blur-3xl"></div>
        <!-- Greek wave pattern (horizontal lines) -->
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

        <!-- Google sign-in button -->
        <button
          (click)="signIn()"
          class="w-full flex items-center justify-center gap-3 border border-surface-200 rounded-xl px-4 py-3 hover:bg-surface-50 hover:border-greek-300 active:bg-surface-100 transition-all font-medium text-surface-700 shadow-sm"
        >
          <!-- Google "G" SVG -->
          <svg class="w-5 h-5 shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          Sign in with Google
        </button>

        <p class="mt-6 text-xs text-surface-300">
          New users are reviewed before gaining access.
        </p>
      </div>
    </div>
  `,
})
export class LoginPage {
  private authService = inject(AuthService);

  async signIn(): Promise<void> {
    await this.authService.signInWithGoogle();
  }
}
