import { TestBed } from '@angular/core/testing';
import { SecurityContext } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { MarkdownRenderService } from './markdown-render.service';

describe('MarkdownRenderService', () => {
  function sanitize(value: ReturnType<MarkdownRenderService['renderBlock']>): string | null {
    return TestBed.inject(DomSanitizer).sanitize(SecurityContext.HTML, value);
  }

  it('renders pipe tables with escaped newline sequences as HTML tables', () => {
    TestBed.configureTestingModule({});
    const service = TestBed.inject(MarkdownRenderService);

    const html = sanitize(service.renderBlock("| Letter | Name |\\n|---|---|\\n| Α α | άλφα |"));

    expect(html).toContain('<table>');
    expect(html).toContain('<td>Α α</td>');
  });

  it('leaves escaped newline sequences untouched in inline markdown', () => {
    TestBed.configureTestingModule({});
    const service = TestBed.inject(MarkdownRenderService);

    const html = sanitize(service.renderInline('Press Enter\\nthen continue.'));

    expect(html).toContain('Enter\\nthen');
  });
});
