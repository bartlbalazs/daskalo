import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * Protects routes that require a fully active (enabled) user.
 * Redirects to /login if not authenticated, or /pending if status is not 'active'.
 */
export const activeUserGuard: CanActivateFn = async () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  // Await the actual Firebase auth state through the AuthService
  // to ensure we stay within the correct injection context
  const fbUser = await authService.waitForAuthResolved();

  if (!fbUser) {
    return router.createUrlTree(['/login']);
  }

  // Ensure the firestore user document is loaded into the signal
  await authService.loadCurrentUser(fbUser.uid);

  if (!authService.isActive()) {
    return router.createUrlTree(['/pending']);
  }

  return true;
};
