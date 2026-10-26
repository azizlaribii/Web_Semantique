import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { User, AuthResponse, RegisterPayload } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly TOKEN_KEY = 'onto_token';
  private readonly USER_KEY  = 'onto_user';

  // Reactive state via signals
  private _currentUser = signal<User | null>(this._loadUser());
  readonly currentUser  = this._currentUser.asReadonly();
  readonly isLoggedIn   = computed(() => !!this._currentUser());

  constructor(private http: HttpClient, private router: Router) {}

  // ── Register ──────────────────────────────────────────
  register(payload: RegisterPayload): Observable<any> {
    return this.http.post<any>('/api/auth/register', payload).pipe(
      catchError(err => throwError(() => err.error?.error || 'Erreur lors de l\'inscription.'))
    );
  }

  // ── Login ─────────────────────────────────────────────
  login(email: string, motDePasse: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>('/api/auth/login', { email, motDePasse }).pipe(
      tap(res => {
        if (res.success) {
          this._saveSession(res.token, res.user);
        }
      }),
      catchError(err => throwError(() => err.error?.error || 'Email ou mot de passe incorrect.'))
    );
  }

  // ── Logout ────────────────────────────────────────────
  logout(): void {
    const token = this.getToken();
    this.http.post('/api/auth/logout', {}, {
      headers: { Authorization: `Bearer ${token}` }
    }).subscribe({ error: () => {} });
    this._clearSession();
    this.router.navigate(['/login']);
  }

  // ── Verify token (used on app boot) ──────────────────
  verifyToken(): Observable<any> {
    const token = this.getToken();
    return this.http.post<any>('/api/auth/verify', { token }).pipe(
      tap(res => {
        if (res.valid && res.user) {
          this._currentUser.set(res.user);
          this._saveUser(res.user);
        }
      }),
      catchError(err => {
        this._clearSession();
        return throwError(() => err);
      })
    );
  }

  // ── Helpers ───────────────────────────────────────────
  getToken(): string {
    return localStorage.getItem(this.TOKEN_KEY) || '';
  }

  private _saveSession(token: string, user: User): void {
    localStorage.setItem(this.TOKEN_KEY, token);
    this._saveUser(user);
    this._currentUser.set(user);
  }

  private _saveUser(user: User): void {
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  }

  private _clearSession(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    this._currentUser.set(null);
  }

  private _loadUser(): User | null {
    try {
      const raw = localStorage.getItem(this.USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  }
}
