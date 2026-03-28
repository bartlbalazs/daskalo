import { Injectable, inject, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import {
  Auth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  user,
  User as FirebaseUser
} from '@angular/fire/auth';
import {
  Firestore,
  doc,
  getDoc,
  setDoc,
  serverTimestamp,
} from '@angular/fire/firestore';
import { toSignal } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { User } from '../models/firestore.models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private auth = inject(Auth);
  private firestore = inject(Firestore);
  private router = inject(Router);

  /** Raw Firebase Auth user as a signal (null when logged out). */
  readonly firebaseUser = toSignal(user(this.auth), { initialValue: null });

  /** The Firestore user document for the currently logged-in user. */
  readonly currentUser = signal<User | null>(null);

  /** True only when the Firestore user status === 'active'. */
  readonly isActive = computed(() => this.currentUser()?.status === 'active');

  async waitForAuthResolved(): Promise<FirebaseUser | null> {
    return firstValueFrom(user(this.auth));
  }

  /** Sign in with Google via a popup. Creates a Firestore user doc on first sign-in. */
  async signInWithGoogle(): Promise<void> {
    const credential = await signInWithPopup(this.auth, new GoogleAuthProvider());
    await this._ensureUserDocument(credential.user);
    await this._loadUserDocument(credential.user.uid);

    if (this.isActive()) {
      this.router.navigate(['/chapters']);
    } else {
      this.router.navigate(['/pending']);
    }
  }

  async signOut(): Promise<void> {
    await signOut(this.auth);
    this.currentUser.set(null);
    this.router.navigate(['/login']);
  }

  async loadCurrentUser(uid?: string): Promise<void> {
    const userId = uid || this.firebaseUser()?.uid;
    if (userId) {
      await this._loadUserDocument(userId);
    }
  }

  private async _loadUserDocument(uid: string): Promise<void> {
    const ref = doc(this.firestore, 'users', uid);
    const snap = await getDoc(ref);
    if (snap.exists()) {
      this.currentUser.set(snap.data() as User);
    }
  }

  private async _ensureUserDocument(fbUser: { uid: string; email: string | null; displayName: string | null }): Promise<void> {
    const ref = doc(this.firestore, 'users', fbUser.uid);
    const snap = await getDoc(ref);
    if (!snap.exists()) {
      // New users start as 'pending' — an admin must activate them.
      await setDoc(ref, {
        email: fbUser.email ?? '',
        displayName: fbUser.displayName ?? fbUser.email ?? '',
        status: 'pending',
        createdAt: serverTimestamp(),
        lastActive: serverTimestamp(),
        progress: {
          currentPhaseId: '',
          completedChapterIds: [],
          xp: 0,
        },
        vocabularyList: [],
      });
    }
  }
}
