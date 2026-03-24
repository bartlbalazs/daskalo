import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-pending',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-greek-900 via-greek-800 to-greek-600 px-4">

      <!-- Decorative background -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
        <div class="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-white/5 blur-3xl"></div>
        <div class="absolute -bottom-32 -right-32 w-[32rem] h-[32rem] rounded-full bg-white/5 blur-3xl"></div>
      </div>

      <!-- Card -->
      <div class="relative bg-white rounded-2xl shadow-2xl p-10 w-full max-w-sm text-center">

        <!-- Icon -->
        <div class="flex items-center justify-center w-14 h-14 rounded-2xl bg-gold-500/10 mx-auto mb-5">
          <svg class="w-7 h-7 text-gold-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </div>

        <h2 class="font-serif text-2xl font-semibold text-surface-800 mb-2">Account Pending</h2>
        <p class="text-surface-500 text-sm leading-relaxed mb-6">
          Your account is awaiting activation. Please contact the administrator to get access to the course.
        </p>

        <div class="bg-greek-50 border border-greek-100 rounded-xl px-4 py-3 text-xs text-greek-700 leading-relaxed">
          Once your account is activated, you'll be able to start learning Modern Greek.
        </div>

        <a routerLink="/login" class="mt-6 inline-block text-sm text-surface-400 hover:text-greek-600 transition-colors">
          &larr; Back to sign in
        </a>
      </div>
    </div>
  `,
})
export class PendingPage {}
