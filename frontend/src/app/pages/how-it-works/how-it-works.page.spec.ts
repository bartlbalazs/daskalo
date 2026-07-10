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

  it('renders the hero and four compact cards', () => {
    const { fixture } = setup();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('How It Works');
    expect(text).toContain('Start learning');
    expect(text).toContain('Follow the Course Map');
    expect(text).toContain('Learn inside a lesson');
    expect(text).toContain('Practice and review');
    expect(text).toContain('Choose your curriculum');
  });
});
