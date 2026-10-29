import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.css'
})
export class NavbarComponent {
  auth = inject(AuthService);
  private api = inject(ApiService);
  private router = inject(Router);

  isReloading = signal(false);
  reloadMessage = signal('');

  user = this.auth.currentUser;

  get roleBadgeClass(): string {
    const role = this.user()?.role?.toLowerCase() || '';
    if (role.includes('medecin') || role.includes('cardio') || role.includes('radio')) return 'badge-cyan';
    if (role.includes('patient')) return 'badge-emerald';
    if (role.includes('stagiaire')) return 'badge-purple';
    return 'badge-amber';
  }

  get userInitial(): string {
    const u = this.user();
    if (!u) return '?';
    return (u.prenom ? u.prenom[0] : (u.nom ? u.nom[0] : '?')).toUpperCase();
  }


  onReload(): void {
    if (this.isReloading()) return;
    this.isReloading.set(true);
    this.reloadMessage.set('');

    this.api.reloadOntologie().subscribe({
      next: (res) => {
        this.isReloading.set(false);
        this.reloadMessage.set('✓ Ontologies rechargées');
        this.api.notifyOntologyChanged();
        setTimeout(() => this.reloadMessage.set(''), 3000);
      },
      error: () => {
        this.isReloading.set(false);
        this.reloadMessage.set('Erreur rechargement');
        setTimeout(() => this.reloadMessage.set(''), 3000);
      }
    });
  }

  onLogout(): void {
    this.auth.logout();
  }
}
