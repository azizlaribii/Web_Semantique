import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent {
  email      = '';
  password   = '';
  showPwd    = false;
  loading    = signal(false);
  errorMsg   = signal('');

  constructor(private auth: AuthService, private router: Router) {
    // If already logged in, redirect to dashboard
    if (this.auth.isLoggedIn()) {
      this.router.navigate(['/dashboard']);
    }
  }

  onSubmit(): void {
    if (!this.email || !this.password) {
      this.errorMsg.set('Veuillez remplir tous les champs.');
      return;
    }
    this.loading.set(true);
    this.errorMsg.set('');

    this.auth.login(this.email, this.password).subscribe({
      next: () => {
        this.loading.set(false);
        this.router.navigate(['/dashboard']);
      },
      error: (msg: string) => {
        this.loading.set(false);
        this.errorMsg.set(msg);
      }
    });
  }

  togglePwd(): void {
    this.showPwd = !this.showPwd;
  }
}
