import { TestBed } from '@angular/core/testing';
import { Exercise } from '../../../core/models/firestore.models';
import { MultipleChoiceComponent } from './multiple-choice.component';

describe('MultipleChoiceComponent', () => {
  function makeFillBlank(id: string, options: string[]): Exercise {
    return {
      type: 'fill_in_the_blank',
      prompt: id,
      data: {
        sentence: 'Choose ___ now.',
        options: options.map((text, index) => ({ text, isCorrect: index === 0 })),
      },
    };
  }

  it('resets options and local answer state when Angular reuses the component for another exercise', () => {
    TestBed.configureTestingModule({});
    const fixture = TestBed.createComponent(MultipleChoiceComponent);

    const first = makeFillBlank('first', ['alpha', 'beta']);
    const second = makeFillBlank('second', ['gamma', 'delta']);

    fixture.componentRef.setInput('exercise', first);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component.select(0);

    fixture.componentRef.setInput('exercise', second);
    fixture.detectChanges();

    expect(component.options().map((option) => option.text).sort()).toEqual(['delta', 'gamma']);
    expect(component.selectedIndex()).toBeNull();
    expect(component.submitted()).toBe(false);
  });

  it('does not reshuffle or reset when Angular receives the same exercise content again', () => {
    TestBed.configureTestingModule({});
    const fixture = TestBed.createComponent(MultipleChoiceComponent);

    const first = makeFillBlank('first', ['alpha', 'beta']);
    const sameContent = makeFillBlank('first', ['alpha', 'beta']);

    fixture.componentRef.setInput('exercise', first);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    component.select(0);

    const optionsBefore = component.options();
    fixture.componentRef.setInput('exercise', sameContent);
    fixture.detectChanges();

    expect(component.options()).toBe(optionsBefore);
    expect(component.selectedIndex()).toBe(0);
  });
});
