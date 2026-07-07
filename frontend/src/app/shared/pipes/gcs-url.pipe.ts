import { Pipe, PipeTransform, inject } from '@angular/core';
import { from, Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { GcsUrlResolverService } from '../services/gcs-url-resolver.service';

@Pipe({
  name: 'gcsUrl',
  standalone: true
})
export class GcsUrlPipe implements PipeTransform {
  private resolver = inject(GcsUrlResolverService);

  transform(gsUri: string | undefined | null): Observable<string> {
    if (!gsUri) return of('');
    return from(this.resolver.resolve(gsUri)).pipe(
      catchError(() => of(''))
    );
  }
}
