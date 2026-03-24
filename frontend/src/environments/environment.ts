// src/environments/environment.ts — LOCAL DEVELOPMENT
// Points to the Firebase Local Emulator Suite.
// Never commit real credentials here; use environment.prod.ts for production values
// and keep that file gitignored (copy from environment.prod.ts.example).

export const environment = {
  production: false,
  useEmulators: true,
  evaluateAttemptUrl: 'http://localhost:8000/evaluate',
  completeChapterUrl: 'http://localhost:8000/complete-chapter',
  firebase: {
    apiKey: 'demo-api-key',
    authDomain: 'localhost',
    projectId: 'demo-daskalo',
    storageBucket: 'demo-daskalo.appspot.com',
    messagingSenderId: '',
    appId: '',
  },
};
