import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

interface HowItWorksCard {
  icon: string;
  title: string;
  body: string;
  link?: { label: string; route: string };
}

@Component({
  selector: 'app-how-it-works',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="px-4 sm:px-6 py-8 sm:py-10 max-w-5xl mx-auto">
      <section class="relative overflow-hidden rounded-3xl bg-greek-700 text-white shadow-xl mb-6 sm:mb-8">
        <div class="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-white/10"></div>
        <div class="absolute right-10 bottom-8 h-20 w-20 rounded-full bg-gold-400/20"></div>
        <div class="relative px-6 py-8 sm:px-10 sm:py-12">
          <p class="text-xs font-semibold uppercase tracking-[0.25em] text-greek-200 mb-3">Welcome to Daskalo</p>
          <h1 class="font-serif text-3xl sm:text-5xl font-semibold leading-tight mb-4">How It Works</h1>
          <p class="text-greek-100 text-base sm:text-lg max-w-2xl leading-relaxed mb-6">
            Follow the course, learn through short lessons, and review what you have unlocked. This is just a quick map before you start.
          </p>
          <div class="flex flex-col sm:flex-row gap-3">
            <a routerLink="/chapters" class="inline-flex items-center justify-center rounded-xl bg-white px-5 py-3 text-sm font-semibold text-greek-800 hover:bg-greek-50 transition-colors">
              Start learning
            </a>
            <a routerLink="/curriculum" class="inline-flex items-center justify-center rounded-xl border border-white/30 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10 transition-colors">
              Choose your curriculum
            </a>
          </div>
        </div>
      </section>

      @if (markSeenError()) {
        <p class="mb-5 rounded-xl border border-gold-400/40 bg-gold-400/10 px-4 py-3 text-sm text-surface-700">
          We could not save that you have seen this page yet. You can still keep learning.
        </p>
      }

      <section class="grid gap-4 sm:grid-cols-2">
        @for (card of cards; track card.title) {
          <article class="rounded-2xl border border-greek-100 bg-white p-5 shadow-sm">
            <div class="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-greek-50 text-xl" aria-hidden="true">{{ card.icon }}</div>
            <h2 class="font-serif text-xl font-semibold text-greek-900 mb-2">{{ card.title }}</h2>
            <p class="text-sm leading-6 text-surface-600">{{ card.body }}</p>
            @if (card.link) {
              <a [routerLink]="card.link.route" class="mt-4 inline-flex text-sm font-semibold text-greek-700 hover:text-greek-900">
                {{ card.link.label }}
              </a>
            }
          </article>
        }
      </section>
    </div>
  `,
})
export class HowItWorksPage implements OnInit {
  private readonly authService = inject(AuthService);
  readonly markSeenError = signal(false);

  readonly cards: HowItWorksCard[] = [
    {
      icon: '1',
      title: 'Follow the Course Map',
      body: 'Lessons are arranged in order. Use the left map or Course page to continue from the next lesson.',
    },
    {
      icon: '2',
      title: 'Learn inside a lesson',
      body: 'Each lesson includes a short story, vocabulary, grammar notes, audio, and exercises.',
    },
    {
      icon: '3',
      title: 'Practice and review',
      body: 'Practice sets reinforce lessons. Grammar Book and Vocabulary help you review what you have learned.',
    },
    {
      icon: '4',
      title: 'Choose your curriculum',
      body: 'The Curriculum page lets you choose among alternative versions when more than one lesson variant is available.',
      link: { label: 'Open Curriculum', route: '/curriculum' },
    },
  ];

  async ngOnInit(): Promise<void> {
    try {
      await this.authService.markOnboardingSeen('howItWorks');
    } catch {
      this.markSeenError.set(true);
    }
  }
}
