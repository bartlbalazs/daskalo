import { Routes } from '@angular/router';
import { activeUserGuard } from './core/guards/active-user.guard';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    canActivate: [activeUserGuard],
    loadComponent: () => import('./pages/app-entry/app-entry.page').then((m) => m.AppEntryPage),
  },
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'pending',
    loadComponent: () => import('./pages/login/pending.page').then((m) => m.PendingPage),
  },
  {
    path: '',
    canActivate: [activeUserGuard],
    loadComponent: () => import('./layout/layout.component').then((m) => m.LayoutComponent),
    children: [
      {
        path: 'how-it-works',
        loadComponent: () =>
          import('./pages/how-it-works/how-it-works.page').then((m) => m.HowItWorksPage),
      },
      {
        path: 'chapters',
        loadComponent: () => import('./pages/chapters/chapters.page').then((m) => m.ChaptersPage),
      },
      {
        path: 'chapters/:id',
        loadComponent: () =>
          import('./pages/chapter-detail/chapter-detail.page').then((m) => m.ChapterDetailPage),
      },
      {
        path: 'grammar-book',
        loadComponent: () =>
          import('./pages/grammar-book/grammar-book.page').then((m) => m.GrammarBookPage),
      },
      {
        path: 'curriculum',
        loadComponent: () =>
          import('./pages/curriculum/curriculum.page').then((m) => m.CurriculumPage),
      },
      {
        path: 'vocabulary',
        loadComponent: () =>
          import('./pages/vocabulary/vocabulary.page').then((m) => m.VocabularyPage),
      },
      {
        path: 'practice/:id',
        loadComponent: () =>
          import('./pages/practice-detail/practice-detail.page').then((m) => m.PracticeDetailPage),
      },
    ],
  },
  {
    path: '**',
    redirectTo: 'chapters',
  },
];
