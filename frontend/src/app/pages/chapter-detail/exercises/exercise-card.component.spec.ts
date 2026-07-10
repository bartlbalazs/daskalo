import { SimpleChange } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Exercise } from '../../../core/models/firestore.models';
import { LessonService } from '../../../core/services/lesson.service';
import { ExerciseCardComponent } from './exercise-card.component';

describe('ExerciseCardComponent', () => {
  function makeExercise(prompt: string): Exercise {
    return {
      type: 'fill_in_the_blank',
      prompt,
      data: {
        sentence: 'Choose ___ now.',
        options: [{ text: 'one', isCorrect: true }],
      },
    };
  }

  function makeComponent(): ExerciseCardComponent {
    TestBed.configureTestingModule({ providers: [{ provide: LessonService, useValue: {} }] });
    return TestBed.runInInjectionContext(() => new ExerciseCardComponent());
  }

  it('resets answered state when reused for different exercise content', () => {
    const component = makeComponent();
    const first = makeExercise('first');
    const second = makeExercise('second');

    component.exercise = first;
    component.chapterId = 'chapter-1';
    component.ngOnChanges({ exercise: new SimpleChange(undefined, first, true), chapterId: new SimpleChange(undefined, 'chapter-1', true) });
    component.state.set('correct');

    component.exercise = second;
    component.ngOnChanges({ exercise: new SimpleChange(first, second, false) });

    expect(component.state()).toBe('unanswered');
  });

  it('keeps answered state when same exercise content is emitted again', () => {
    const component = makeComponent();
    const first = makeExercise('same');
    const sameContent = makeExercise('same');

    component.exercise = first;
    component.chapterId = 'chapter-1';
    component.ngOnChanges({ exercise: new SimpleChange(undefined, first, true), chapterId: new SimpleChange(undefined, 'chapter-1', true) });
    component.state.set('correct');

    component.exercise = sameContent;
    component.ngOnChanges({ exercise: new SimpleChange(first, sameContent, false) });

    expect(component.state()).toBe('correct');
  });
});
