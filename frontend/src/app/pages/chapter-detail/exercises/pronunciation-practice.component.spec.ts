import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { PronunciationPracticeComponent } from './pronunciation-practice.component';
import { Exercise } from '../../../core/models/firestore.models';

// ---------------------------------------------------------------------------
// Test exercise fixture
// ---------------------------------------------------------------------------

const EXERCISE: Exercise = {
  type: 'pronunciation_practice',
  prompt: '',
  data: { target_text: 'Καλημέρα' },
};

const EXERCISE_WITH_AUDIO: Exercise = {
  type: 'pronunciation_practice',
  prompt: '',
  audioUrl: 'https://example.com/audio.mp3',
  data: { target_text: 'Καλημέρα' },
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PronunciationPracticeComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [PronunciationPracticeComponent],
    });
  });

  function createComponent(exercise = EXERCISE) {
    const fixture = TestBed.createComponent(PronunciationPracticeComponent);
    fixture.componentInstance.exercise = exercise;
    fixture.detectChanges();
    return fixture;
  }

  // -------------------------------------------------------------------------
  // Creation
  // -------------------------------------------------------------------------

  it('creates the component', () => {
    const fixture = createComponent();
    expect(fixture.componentInstance).toBeTruthy();
  });

  // -------------------------------------------------------------------------
  // Target text displayed
  // -------------------------------------------------------------------------

  it('displays the target Greek text', () => {
    const fixture = createComponent();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Καλημέρα');
  });

  // -------------------------------------------------------------------------
  // targetText() helper
  // -------------------------------------------------------------------------

  it('targetText() returns the target_text from exercise data', () => {
    const fixture = createComponent();
    expect(fixture.componentInstance.targetText()).toBe('Καλημέρα');
  });

  it('targetText() returns empty string when data is missing', () => {
    const fixture = createComponent({ type: 'pronunciation_practice', prompt: '' });
    expect(fixture.componentInstance.targetText()).toBe('');
  });

  // -------------------------------------------------------------------------
  // Initial state
  // -------------------------------------------------------------------------

  it('starts in idle recording state', () => {
    const fixture = createComponent();
    expect(fixture.componentInstance.recordingState()).toBe('idle');
  });

  it('has no evaluation result initially', () => {
    const fixture = createComponent();
    expect(fixture.componentInstance.evaluation()).toBeNull();
  });

  // -------------------------------------------------------------------------
  // setEvaluation() — displays feedback card and emits answered
  // -------------------------------------------------------------------------

  it('setEvaluation() stores the result and emits answered', () => {
    const fixture = createComponent();
    const comp = fixture.componentInstance;

    const answeredValues: boolean[] = [];
    comp.answered.subscribe((v: boolean) => answeredValues.push(v));

    comp.setEvaluation({ score: 75, feedback: 'Good effort!', isCorrect: true });
    fixture.detectChanges();

    expect(comp.evaluation()?.score).toBe(75);
    expect(answeredValues).toEqual([true]);
  });

  it('renders the feedback card after setEvaluation() is called in submitted state', () => {
    const fixture = createComponent();
    const comp = fixture.componentInstance;

    // Simulate the submitted state so the evaluation block is visible
    comp.recordingState.set('submitted');
    comp.setEvaluation({ score: 60, feedback: 'Keep practising!', isCorrect: false });
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('60/100');
    expect(compiled.textContent).toContain('Keep practising!');
  });

  // -------------------------------------------------------------------------
  // submit() — emits base64 via submitted$
  // -------------------------------------------------------------------------

  it('submit() emits base64 audio string via submitted$', async () => {
    const fixture = createComponent();
    const comp = fixture.componentInstance;

    const emittedValues: string[] = [];
    comp.submitted$.subscribe((v: string) => emittedValues.push(v));

    // Inject a fake recorded blob so submit() has something to work with
    const fakeBlob = new Blob(['fake-audio'], { type: 'audio/webm' });
    comp['chunks'] = [fakeBlob];
    comp.recordingState.set('recorded');

    comp.submit();

    // FileReader is async — wait for it to complete
    await new Promise<void>((resolve) => {
      const interval = setInterval(() => {
        if (emittedValues.length > 0) {
          clearInterval(interval);
          resolve();
        }
      }, 10);
    });

    expect(emittedValues.length).toBe(1);
    // Must be a valid base64 string (no data URL prefix)
    expect(emittedValues[0]).not.toContain('data:');
    expect(emittedValues[0].length).toBeGreaterThan(0);
    expect(comp.recordingState()).toBe('submitted');
  });

  // -------------------------------------------------------------------------
  // resetRecording()
  // -------------------------------------------------------------------------

  it('resetRecording() returns to idle state and clears chunks', () => {
    const fixture = createComponent();
    const comp = fixture.componentInstance;

    comp['chunks'] = [new Blob(['x'])];
    comp.recordingState.set('recorded');
    comp.elapsed.set(10);

    comp.resetRecording();

    expect(comp.recordingState()).toBe('idle');
    expect(comp.elapsed()).toBe(0);
    expect(comp.recordedUrl()).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Cleanup on destroy
  // -------------------------------------------------------------------------

  it('ngOnDestroy does not throw', () => {
    const fixture = createComponent();
    expect(() => fixture.componentInstance.ngOnDestroy()).not.toThrow();
  });
});
