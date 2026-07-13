import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { HowItWorksPage } from './how-it-works.page';
import { AuthService } from '../../core/services/auth.service';

describe('HowItWorksPage', () => {
  function setup() {
    const authService = { markOnboardingSeen: vi.fn().mockResolvedValue(undefined) };

    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: authService }],
    });

    const fixture = TestBed.createComponent(HowItWorksPage);
    return { fixture, authService };
  }

  it('calls markOnboardingSeen on page load', async () => {
    const { fixture, authService } = setup();

    await fixture.componentInstance.ngOnInit();

    expect(authService.markOnboardingSeen).toHaveBeenCalledWith('howItWorks');
  });

  it('renders the expanded course guide sections', () => {
    const { fixture } = setup();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Greek that connects.');
    expect(text).toContain('Start learning');
    expect(text).toContain('View curriculum');
    expect(text).toContain('The big progression');
    expect(text).toContain('Fixed learning goals');
    expect(text).toContain('AI-assisted, curriculum-guided');
    expect(text).toContain('Inside a lesson');
    expect(text).toContain('Story passage');
    expect(text).toContain('Vocabulary');
    expect(text).toContain('A short routine');
    expect(text).toContain('Completed chapters become your reference.');
    expect(text).toContain('Lesson variants');
  });
});
