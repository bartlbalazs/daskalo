import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

interface HowItWorksCard {
  eyebrow?: string;
  title: string;
  body: string;
}

interface LessonPart {
  title: string;
  body: string;
}

@Component({
  selector: 'app-how-it-works',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="px-4 sm:px-6 py-8 sm:py-10 max-w-6xl mx-auto">
      <section class="relative overflow-hidden rounded-[2rem] bg-greek-800 text-white shadow-xl mb-8 sm:mb-10">
        <div class="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/10"></div>
        <div class="absolute left-8 bottom-8 h-28 w-28 rounded-full bg-gold-400/15"></div>
        <div class="absolute right-20 bottom-16 h-16 w-16 rounded-full border border-white/20"></div>
        <div class="relative grid gap-8 px-6 py-9 sm:px-10 sm:py-12 lg:grid-cols-[1.25fr_0.75fr] lg:items-end">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.28em] text-gold-300 mb-3">Welcome to Daskalo</p>
            <h1 class="font-serif text-4xl sm:text-6xl font-semibold leading-tight mb-5">Greek that connects.</h1>
            <p class="text-greek-50 text-base sm:text-xl max-w-3xl leading-relaxed mb-6">
              Daskalo is built for adults who want Greek to make sense. You learn through structured chapters, clear grammar, useful vocabulary, listening, and practice connected to one lesson story.
            </p>
            <div class="flex flex-col sm:flex-row gap-3">
              <a routerLink="/chapters" class="inline-flex items-center justify-center rounded-xl bg-white px-5 py-3 text-sm font-semibold text-greek-800 hover:bg-greek-50 transition-colors">
              Start learning
              </a>
              <a routerLink="/curriculum" class="inline-flex items-center justify-center rounded-xl border border-white/30 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10 transition-colors">
                View curriculum
              </a>
            </div>
          </div>

          <div class="rounded-3xl border border-white/15 bg-white/10 p-5 backdrop-blur-sm">
            <p class="text-xs font-semibold uppercase tracking-[0.22em] text-greek-100 mb-4">The idea</p>
            <div class="space-y-4">
              @for (step of promiseSteps; track step.title) {
                <div class="flex gap-3">
                  <div class="mt-1 h-2.5 w-2.5 rounded-full bg-gold-300 shrink-0"></div>
                  <div>
                    <h2 class="font-semibold text-white text-sm">{{ step.title }}</h2>
                    <p class="text-sm leading-6 text-greek-100">{{ step.body }}</p>
                  </div>
                </div>
              }
            </div>
          </div>
        </div>
      </section>

      @if (markSeenError()) {
        <p class="mb-6 rounded-xl border border-gold-400/40 bg-gold-400/10 px-4 py-3 text-sm text-surface-700">
          We could not save that you have seen this page yet. You can still keep learning.
        </p>
      }

      <section class="mb-8 grid gap-4 lg:grid-cols-3">
        @for (item of curriculumModel; track item.title) {
          <article class="rounded-3xl border border-greek-100 bg-white p-6 shadow-sm">
            <p class="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-greek-500">{{ item.eyebrow }}</p>
            <h2 class="font-serif text-2xl font-semibold text-greek-900 mb-3">{{ item.title }}</h2>
            <p class="text-sm leading-6 text-surface-600">{{ item.body }}</p>
          </article>
        }
      </section>

      <section class="mb-8 rounded-[2rem] border border-greek-100 bg-greek-50 p-6 sm:p-8">
        <div class="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.2em] text-greek-600 mb-3">AI-assisted, curriculum-guided</p>
            <h2 class="font-serif text-3xl font-semibold text-greek-900 mb-4">The curriculum decides the path.</h2>
            <p class="text-sm sm:text-base leading-7 text-surface-700">
              AI helps create variety, examples, audio, exercises, and lesson stories. It does not decide what you need to learn next. Each chapter starts from a fixed learning goal, CEFR level, target grammar, and required vocabulary.
            </p>
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            @for (step of generationSteps; track step.title) {
              <article class="rounded-2xl bg-white p-5 shadow-sm border border-greek-100">
                <h3 class="font-semibold text-greek-900 mb-2">{{ step.title }}</h3>
                <p class="text-sm leading-6 text-surface-600">{{ step.body }}</p>
              </article>
            }
          </div>
        </div>
      </section>

      <section class="mb-8 rounded-[2rem] bg-white border border-surface-200 p-6 sm:p-8 shadow-sm">
        <div class="max-w-3xl mb-7">
          <p class="text-xs font-bold uppercase tracking-[0.2em] text-greek-600 mb-3">Inside a lesson</p>
          <h2 class="font-serif text-3xl font-semibold text-greek-900 mb-3">One story, many ways to learn it.</h2>
          <p class="text-sm sm:text-base leading-7 text-surface-700">
            Grammar and vocabulary are not isolated lists. They come from the chapter passage, so you meet new forms in context before practicing them.
          </p>
        </div>

        <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          @for (part of lessonParts; track part.title) {
            <article class="rounded-2xl border border-surface-200 bg-surface-50 p-5">
              <h3 class="font-semibold text-surface-900 mb-2">{{ part.title }}</h3>
              <p class="text-sm leading-6 text-surface-600">{{ part.body }}</p>
            </article>
          }
        </div>
      </section>

      <section class="mb-8 grid gap-6 lg:grid-cols-[1fr_0.9fr]">
        <article class="rounded-[2rem] bg-greek-700 p-6 sm:p-8 text-white shadow-sm">
          <p class="text-xs font-bold uppercase tracking-[0.2em] text-gold-300 mb-3">Vocabulary</p>
          <h2 class="font-serif text-3xl font-semibold mb-4">Build a word list that belongs to you.</h2>
          <div class="space-y-4">
            @for (item of vocabularyGuidance; track item.title) {
              <div class="rounded-2xl bg-white/10 p-4 border border-white/10">
                <h3 class="font-semibold mb-1">{{ item.title }}</h3>
                <p class="text-sm leading-6 text-greek-100">{{ item.body }}</p>
              </div>
            }
          </div>
        </article>

        <article class="rounded-[2rem] border border-gold-300/60 bg-gold-50 p-6 sm:p-8">
          <p class="text-xs font-bold uppercase tracking-[0.2em] text-greek-700 mb-3">A short routine</p>
          <h2 class="font-serif text-3xl font-semibold text-greek-900 mb-5">Use each chapter in five moves.</h2>
          <ol class="space-y-3">
            @for (step of studyRoutine; track step; let i = $index) {
              <li class="flex gap-3 text-sm leading-6 text-surface-700">
                <span class="flex h-7 w-7 items-center justify-center rounded-full bg-greek-700 text-xs font-bold text-white shrink-0">{{ i + 1 }}</span>
                <span>{{ step }}</span>
              </li>
            }
          </ol>
        </article>
      </section>

      <section class="mb-8 rounded-[2rem] border border-greek-100 bg-white p-6 sm:p-8 shadow-sm">
        <div class="grid gap-6 lg:grid-cols-2">
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.2em] text-greek-600 mb-3">Review</p>
            <h2 class="font-serif text-3xl font-semibold text-greek-900 mb-4">Completed chapters become your reference.</h2>
            <p class="text-sm sm:text-base leading-7 text-surface-700">
              Complete the exercises to save the chapter as finished and unlock its review material. After a chapter is complete, its grammar summary becomes part of your Grammar Book, so your completed lessons turn into a growing reference.
            </p>
          </div>
          <div class="rounded-3xl bg-surface-900 p-6 text-white">
            <h3 class="font-serif text-2xl font-semibold mb-3">Lesson variants</h3>
            <p class="text-sm leading-7 text-surface-200">
              Over time, a curriculum chapter may have more than one version. These versions are different routes through the same checkpoint: they teach the same core goal through different topics or stories.
            </p>
          </div>
        </div>
      </section>

      <section class="rounded-[2rem] bg-gradient-to-br from-greek-700 to-greek-900 p-6 sm:p-8 text-white shadow-xl">
        <div class="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.2em] text-gold-300 mb-3">Where to go next</p>
            <h2 class="font-serif text-3xl font-semibold mb-2">Start with the next chapter, or inspect the map.</h2>
            <p class="text-sm leading-6 text-greek-100 max-w-2xl">You can begin learning immediately from the chapter list, or open the curriculum to see how the course is structured.</p>
          </div>
          <div class="flex flex-col sm:flex-row gap-3 shrink-0">
            <a routerLink="/chapters" class="inline-flex items-center justify-center rounded-xl bg-white px-5 py-3 text-sm font-semibold text-greek-800 hover:bg-greek-50 transition-colors">
              Start learning
            </a>
            <a routerLink="/curriculum" class="inline-flex items-center justify-center rounded-xl border border-white/30 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10 transition-colors">
              View curriculum
            </a>
          </div>
        </div>
      </section>
    </div>
  `,
})
export class HowItWorksPage implements OnInit {
  private readonly authService = inject(AuthService);
  readonly markSeenError = signal(false);

  readonly promiseSteps: HowItWorksCard[] = [
    {
      title: 'Structured progression',
      body: 'Books and chapters move from the basics toward more complex Greek in a deliberate order.',
    },
    {
      title: 'Context first',
      body: 'Each chapter starts from a passage, then vocabulary, grammar, audio, and exercises connect back to it.',
    },
    {
      title: 'Review that grows',
      body: 'Completed lessons feed your Grammar Book, vocabulary review, and future practice.',
    },
  ];

  readonly curriculumModel: HowItWorksCard[] = [
    {
      eyebrow: 'Books',
      title: 'The big progression',
      body: 'Books group chapters by level and purpose. The first book, The Absolute Basics, starts with the alphabet, stress marks, core verbs, and your first usable sentences.',
    },
    {
      eyebrow: 'Chapters',
      title: 'Fixed learning goals',
      body: 'Every chapter has a curriculum slot: a skill focus, CEFR level, target grammar, and required vocabulary. This is the backbone of the course.',
    },
    {
      eyebrow: 'Variants',
      title: 'Different routes',
      body: 'Sometimes the same curriculum chapter has alternative versions. Pick the story that interests you; it still teaches the same core checkpoint.',
    },
  ];

  readonly generationSteps: LessonPart[] = [
    {
      title: '1. Start from the curriculum',
      body: 'The chapter goal, level, grammar, and vocabulary are selected first.',
    },
    {
      title: '2. Build the lesson package',
      body: 'Daskalo creates a passage, grammar notes, vocabulary, exercises, images, and audio around that goal.',
    },
    {
      title: '3. Check level and quality',
      body: 'The result is reviewed against the target level, grammar focus, cultural fit, and exercise quality.',
    },
    {
      title: '4. Learn the finished chapter',
      body: 'You see the final lesson as a connected story, not as random drills.',
    },
  ];

  readonly lessonParts: LessonPart[] = [
    {
      title: 'Story passage',
      body: 'Read the Greek passage sentence by sentence, with translations where available.',
    },
    {
      title: 'Audio',
      body: 'Listen to the full passage first, then use sentence-level audio to slow down and repeat difficult lines.',
    },
    {
      title: 'Vocabulary',
      body: 'Study words chosen from the chapter story and the curriculum vocabulary target.',
    },
    {
      title: 'Grammar notes',
      body: 'Use clear explanations and examples tied to the forms you saw in the passage.',
    },
    {
      title: 'Exercises',
      body: 'Check comprehension, word order, listening, writing, and practical use depending on the chapter.',
    },
    {
      title: 'Completion',
      body: 'Finish the exercises to save progress and add the chapter to your review material.',
    },
  ];

  readonly vocabularyGuidance: LessonPart[] = [
    {
      title: 'Chapter vocabulary',
      body: 'These words are part of the lesson, not a random list. They support the passage and target grammar.',
    },
    {
      title: 'Favorites',
      body: 'Bookmark words that feel useful, difficult, or personally important so you can return to them later.',
    },
    {
      title: 'Own words',
      body: 'Add words you personally want to remember and keep them beside the course vocabulary.',
    },
  ];

  readonly studyRoutine = [
    'Listen once to the full passage.',
    'Read the passage sentence by sentence.',
    'Check vocabulary and grammar notes.',
    'Do the exercises.',
    'Favorite useful words and review them later.',
  ];

  async ngOnInit(): Promise<void> {
    try {
      await this.authService.markOnboardingSeen('howItWorks');
    } catch {
      this.markSeenError.set(true);
    }
  }
}
