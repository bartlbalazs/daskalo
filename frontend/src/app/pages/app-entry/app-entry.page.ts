import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-entry',
  standalone: true,
  template: `
    <div class="min-h-screen bg-greek-50 flex items-center justify-center px-6 text-center">
      <p class="text-sm text-greek-700">Opening your course...</p>
    </div>
  `,
})
export class AppEntryPage implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  ngOnInit(): void {
    this.router.navigateByUrl(this.authService.getActiveEntryPath(), { replaceUrl: true });
  }
}
