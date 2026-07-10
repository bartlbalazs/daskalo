import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { LayoutComponent } from './layout.component';
import { AuthService } from '../core/services/auth.service';
import { LessonService } from '../core/services/lesson.service';

describe('LayoutComponent navigation', () => {
  it('renders How It Works as the last static item in desktop nav and sidebar footer', () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            currentUser: () => ({ progress: { xp: 0, completedChapterIds: [], completedPracticeSetIds: [] } }),
            firebaseUser: () => null,
            signOut: async () => undefined,
          },
        },
        { provide: LessonService, useValue: { getBooks: () => of([]), getSelectedChaptersByBook: () => of([]) } },
      ],
    });

    const fixture = TestBed.createComponent(LayoutComponent);
    fixture.detectChanges();

    const links = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('a'));
    const desktopLinks = links.filter((link) => link.closest('.fixed.top-14'));
    const footerLinks = links.filter((link) => link.closest('.border-t.border-greek-100'));

    expect(desktopLinks.at(-1)?.textContent).toContain('How It Works');
    expect(footerLinks.at(-1)?.textContent).toContain('How It Works');
  });
});
