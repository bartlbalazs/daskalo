import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { vi } from 'vitest';
import { AppEntryPage } from './app-entry.page';
import { AuthService } from '../../core/services/auth.service';

describe('AppEntryPage', () => {
  it('routes unseen active users to How It Works', () => {
    const router = { navigateByUrl: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        { provide: Router, useValue: router },
        { provide: AuthService, useValue: { getActiveEntryPath: () => '/how-it-works' } },
      ],
    });

    TestBed.createComponent(AppEntryPage).componentInstance.ngOnInit();

    expect(router.navigateByUrl).toHaveBeenCalledWith('/how-it-works', { replaceUrl: true });
  });

  it('routes users who have seen onboarding to Course', () => {
    const router = { navigateByUrl: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        { provide: Router, useValue: router },
        { provide: AuthService, useValue: { getActiveEntryPath: () => '/chapters' } },
      ],
    });

    TestBed.createComponent(AppEntryPage).componentInstance.ngOnInit();

    expect(router.navigateByUrl).toHaveBeenCalledWith('/chapters', { replaceUrl: true });
  });
});
