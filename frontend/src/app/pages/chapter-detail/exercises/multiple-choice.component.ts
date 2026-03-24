import { Component, Input, Output, EventEmitter, signal } from '@angular/core';
import {
  Exercise,
  FillInTheBlankData,
  OddOneOutData,
  RoleplayData,
  CulturalContextData,
} from '../../../core/models/firestore.models';

export type McOption = { text: string; isCorrect: boolean };

@Component({
  selector: 'app-multiple-choice',
  standalone: true,
  template: `
    <!-- fill_in_the_blank: show sentence with blank highlighted -->
    @if (exercise.type === 'fill_in_the_blank') {
      @let d = asFitb(exercise.data);
      <p class="text-base text-surface-700 mb-4 leading-relaxed">
        @for (part of sentenceParts(d.sentence); track $index) {
          @if (part === '___') {
            <span class="inline-block bg-greek-100 border-b-2 border-greek-500 px-3 py-0.5 mx-1 rounded font-semibold text-greek-700 min-w-[5rem] text-center">
              {{ selectedText() ?? '___' }}
            </span>
          } @else {
            <span>{{ part }}</span>
          }
        }
      </p>
    }

    <!-- cultural_context: show fact first -->
    @if (exercise.type === 'cultural_context') {
      @let d = asCultural(exercise.data);
      <div class="bg-greek-50 border border-greek-100 rounded-xl p-4 mb-4 text-sm text-greek-800 leading-relaxed">
        <span class="font-semibold text-greek-600 mr-1">Did you know?</span>{{ d.fact }}
      </div>
      <p class="text-base font-medium text-surface-700 mb-4">{{ d.question }}</p>
    }

    <!-- Options -->
    <div class="space-y-2.5">
      @for (opt of options(); track $index) {
        <button
          (click)="select($index)"
          [disabled]="submitted()"
          class="w-full text-left px-4 py-3 rounded-xl border text-sm transition-all duration-150 flex items-center gap-3"
          [class]="optionClass($index)"
        >
          <!-- Letter badge -->
          <span class="w-6 h-6 rounded-full border text-xs font-semibold flex items-center justify-center shrink-0"
            [class]="badgeClass($index)">
            {{ optionLetter($index) }}
          </span>
          <span class="flex-1">{{ opt.text }}</span>
          <!-- Result icon -->
          @if (submitted()) {
            @if (selectedIndex() === $index && opt.isCorrect) {
              <svg class="w-4 h-4 text-emerald-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
              </svg>
            } @else if (selectedIndex() === $index && !opt.isCorrect) {
              <svg class="w-4 h-4 text-red-400 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
              </svg>
            } @else if (opt.isCorrect) {
              <svg class="w-4 h-4 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
            }
          }
        </button>
      }
    </div>
  `,
})
export class MultipleChoiceComponent {
  @Input({ required: true }) exercise!: Exercise;
  @Output() answered = new EventEmitter<boolean>();

  selectedIndex = signal<number | null>(null);
  submitted = signal(false);

  get selectedText(): () => string | null {
    return () => {
      const i = this.selectedIndex();
      return i !== null ? this.options()[i]?.text ?? null : null;
    };
  }

  options(): McOption[] {
    const d = this.exercise.data as Record<string, unknown>;
    if (!d) return [];
    switch (this.exercise.type) {
      case 'fill_in_the_blank':
        return (d['options'] as McOption[]) ?? [];
      case 'odd_one_out': {
        const odd = d as unknown as OddOneOutData;
        return odd.words.map((w, i) => ({ text: w, isCorrect: i === odd.correct_index }));
      }
      case 'roleplay_choice':
        return (d['options'] as McOption[]) ?? [];
      case 'cultural_context':
        return (d['options'] as McOption[]) ?? [];
      default:
        return [];
    }
  }

  select(index: number): void {
    if (this.submitted()) return;
    this.selectedIndex.set(index);
  }

  submit(): void {
    if (this.selectedIndex() === null || this.submitted()) return;
    this.submitted.set(true);
    const correct = this.options()[this.selectedIndex()!]?.isCorrect ?? false;
    this.answered.emit(correct);
  }

  isCorrect(): boolean {
    if (!this.submitted() || this.selectedIndex() === null) return false;
    return this.options()[this.selectedIndex()!]?.isCorrect ?? false;
  }

  optionClass(index: number): string {
    if (!this.submitted()) {
      return this.selectedIndex() === index
        ? 'border-greek-500 bg-greek-50 text-greek-800'
        : 'border-surface-200 bg-white text-surface-700 hover:border-greek-300 hover:bg-greek-50/50';
    }
    const opt = this.options()[index];
    if (opt.isCorrect) return 'border-emerald-300 bg-emerald-50 text-emerald-800';
    if (this.selectedIndex() === index) return 'border-red-300 bg-red-50 text-red-800';
    return 'border-surface-100 bg-surface-50 text-surface-400';
  }

  badgeClass(index: number): string {
    if (!this.submitted()) {
      return this.selectedIndex() === index
        ? 'border-greek-500 bg-greek-500 text-white'
        : 'border-surface-300 text-surface-500';
    }
    const opt = this.options()[index];
    if (opt.isCorrect) return 'border-emerald-400 bg-emerald-400 text-white';
    if (this.selectedIndex() === index) return 'border-red-400 bg-red-400 text-white';
    return 'border-surface-200 text-surface-300';
  }

  optionLetter(index: number): string {
    return String.fromCharCode(65 + index); // A, B, C, D
  }

  sentenceParts(sentence: string): string[] {
    return sentence.split('___').reduce((acc: string[], part, i, arr) => {
      acc.push(part);
      if (i < arr.length - 1) acc.push('___');
      return acc;
    }, []);
  }

  asFitb(data: Record<string, unknown> | undefined): FillInTheBlankData {
    return data as unknown as FillInTheBlankData;
  }

  asCultural(data: Record<string, unknown> | undefined): CulturalContextData {
    return data as unknown as CulturalContextData;
  }
}
