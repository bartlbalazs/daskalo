import { TestBed } from '@angular/core/testing';
import { PassageComprehensionComponent } from './passage-comprehension.component';
import { Exercise, PassageComprehensionData, PassageSentence } from '../../../core/models/firestore.models';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeExercise(): Exercise {
  return {
    type: 'passage_comprehension',
    prompt: 'Answer the questions about the passage.',
    data: {
      questions: [
        {
          question: 'What did the dog do?',
          options: [
            { text: 'Ran', isCorrect: true },
            { text: 'Slept', isCorrect: false },
          ],
        },
      ],
    } as unknown as Record<string, unknown>,
  };
}

function createComponent(exercise: Exercise) {
  const fixture = TestBed.createComponent(PassageComprehensionComponent);
  fixture.componentInstance.exercise = exercise;
  fixture.componentInstance.ngOnChanges();
  fixture.detectChanges();
  return fixture;
}

// ---------------------------------------------------------------------------
// FE-08 — ngOnChanges must not mutate Firestore-owned input objects
// ---------------------------------------------------------------------------

describe('PassageComprehensionComponent — FE-08 no in-place mutation', () => {
  it('does not mutate the original exercise.data options array or its element order', () => {
    const exercise = makeExercise();
    const data = exercise.data as unknown as PassageComprehensionData;
    const originalOptionsRef = data.questions[0].options;
    const originalFirstOptionText = originalOptionsRef[0].text;
    const originalSecondOptionText = originalOptionsRef[1].text;

    createComponent(exercise);

    // Same array reference, same element order — the component must shuffle
    // into a local copy, never mutate the Firestore-owned input in place.
    expect(data.questions[0].options).toBe(originalOptionsRef);
    expect(data.questions[0].options[0].text).toBe(originalFirstOptionText);
    expect(data.questions[0].options[1].text).toBe(originalSecondOptionText);
  });
});

// ---------------------------------------------------------------------------
// FE-08 — ngOnChanges must not reset state on a redundant re-emission
// ---------------------------------------------------------------------------

describe('PassageComprehensionComponent — FE-08 stable identity on redundant re-emission', () => {
  it('keeps the selected answer when ngOnChanges fires again with structurally-new but identical content', () => {
    const exercise = makeExercise();
    const fixture = createComponent(exercise);
    const comp = fixture.componentInstance;

    comp.select(0, 0);
    expect(comp.qState(0).selected).toBe(0);

    // Simulate a redundant Firestore listener re-emission: a brand new object
    // reference (as docData() always produces) but with identical content —
    // e.g. an unrelated field changed elsewhere in the parent chapter doc.
    const redundantExercise: Exercise = JSON.parse(JSON.stringify(exercise));
    comp.exercise = redundantExercise;
    comp.ngOnChanges();

    expect(comp.qState(0).selected).toBe(0);
    expect(comp.submitted()).toBe(false);
  });

  it('resets the selected answer when the exercise genuinely changes', () => {
    const exercise = makeExercise();
    const fixture = createComponent(exercise);
    const comp = fixture.componentInstance;

    comp.select(0, 0);
    expect(comp.qState(0).selected).toBe(0);

    const newExercise: Exercise = {
      type: 'passage_comprehension',
      prompt: 'Answer the questions about the passage.',
      data: {
        questions: [
          {
            question: 'A completely different question?',
            options: [
              { text: 'Yes', isCorrect: true },
              { text: 'No', isCorrect: false },
            ],
          },
        ],
      } as unknown as Record<string, unknown>,
    };
    comp.exercise = newExercise;
    comp.ngOnChanges();

    expect(comp.qState(0).selected).toBeNull();
  });

  it('preserves revealed sentence translations across a redundant re-emission', () => {
    const exercise = makeExercise();
    const fixture = createComponent(exercise);
    const comp = fixture.componentInstance;

    fixture.componentRef.setInput('passage', [{ greek: 'Ο σκύλος τρέχει.', english: 'The dog runs.' }]);
    fixture.detectChanges();
    comp.toggleSentence(0);
    expect(comp.revealed().has(0)).toBe(true);

    const redundantExercise: Exercise = JSON.parse(JSON.stringify(exercise));
    comp.exercise = redundantExercise;
    comp.ngOnChanges();

    expect(comp.revealed().has(0)).toBe(true);
  });
});

describe('PassageComprehensionComponent — passage rendering', () => {
  it('renders structured passage sentences sentence-by-sentence', () => {
    const fixture = createComponent(makeExercise());
    const passage: PassageSentence[] = [
      { greek: 'Ο σκύλος τρέχει.', english: 'The dog runs.' },
      { greek: 'Η γάτα κοιμάται.', english: 'The cat sleeps.' },
    ];

    fixture.componentRef.setInput('passage', passage);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Ο σκύλος τρέχει.');
    expect(text).toContain('Η γάτα κοιμάται.');
    expect(text).toContain('Click any sentence to reveal its translation.');
  });

  it('splits legacy passage_text into sentence entries when structured passage is missing', () => {
    const fixture = createComponent(makeExercise());

    fixture.componentRef.setInput('passage', []);
    fixture.componentRef.setInput('passageText', 'Ο σκύλος τρέχει. Η γάτα κοιμάται.');
    fixture.detectChanges();

    expect(fixture.componentInstance.displayPassage()).toEqual([
      { greek: 'Ο σκύλος τρέχει.', english: '' },
      { greek: 'Η γάτα κοιμάται.', english: '' },
    ]);

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Ο σκύλος τρέχει.');
    expect(text).toContain('Η γάτα κοιμάται.');
  });
});
