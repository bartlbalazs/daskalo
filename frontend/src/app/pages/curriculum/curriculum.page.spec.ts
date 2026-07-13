import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { vi } from 'vitest';
import { Chapter } from '../../core/models/firestore.models';
import { AuthService } from '../../core/services/auth.service';
import { LessonService } from '../../core/services/lesson.service';
import { CurriculumPage } from './curriculum.page';

describe('CurriculumPage', () => {
  function setup() {
    const lessonService = {
      getBooks: vi.fn().mockReturnValue(of([])),
      getAllChapters: vi.fn().mockReturnValue(of([])),
      setCurriculumSelection: vi.fn().mockResolvedValue(undefined),
    };
    const authService = {
      currentUser: signal(null),
    };

    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: LessonService, useValue: lessonService },
        { provide: AuthService, useValue: authService },
      ],
    });

    const fixture = TestBed.createComponent(CurriculumPage);
    return { fixture, component: fixture.componentInstance, lessonService };
  }

  it('shows only the clicked select button as active while a selection is pending', () => {
    const { component } = setup();
    const clicked = { id: 'newer', isSelectableAlternative: true } as Chapter;
    const other = { id: 'older', isSelectableAlternative: true } as Chapter;

    component.selectionPendingId.set(clicked.id);

    expect(component.isSelectButtonActive(clicked, 'selected')).toBe(true);
    expect(component.isSelectButtonActive(other, 'selected')).toBe(false);
    expect(component.canSelectVariant(clicked, 'selected')).toBe(false);
  });

  it('renders unavailable variants as inactive select buttons', () => {
    const { component } = setup();
    const unavailable = { id: 'archived', isSelectableAlternative: false } as Chapter;

    expect(component.isSelectButtonActive(unavailable, 'selected')).toBe(false);
    expect(component.canSelectVariant(unavailable, 'selected')).toBe(false);
  });

  it('sets and clears pending state around selection updates', async () => {
    const { component, lessonService } = setup();
    let resolveSelection!: () => void;
    lessonService.setCurriculumSelection.mockReturnValue(new Promise<void>((resolve) => {
      resolveSelection = resolve;
    }));

    const pending = component.select('b1_c1', 'variant-2');

    expect(component.selectionPendingId()).toBe('variant-2');
    resolveSelection();
    await pending;

    expect(component.selectionPendingId()).toBeNull();
    expect(component.selectionError()).toBeNull();
  });
});
