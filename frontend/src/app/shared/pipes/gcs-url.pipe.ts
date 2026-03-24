import { Pipe, PipeTransform, inject } from '@angular/core';
import { Storage, ref, getDownloadURL } from '@angular/fire/storage';
import { from, Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Pipe({
  name: 'gcsUrl',
  standalone: true
})
export class GcsUrlPipe implements PipeTransform {
  private storage = inject(Storage);

  transform(gsUri: string | undefined | null): Observable<string> {
    if (!gsUri) return of('');
    if (!gsUri.startsWith('gs://')) return of(gsUri);

    const storageRef = ref(this.storage, gsUri);
    return from(getDownloadURL(storageRef)).pipe(
      catchError(() => of(''))
    );
  }
}
