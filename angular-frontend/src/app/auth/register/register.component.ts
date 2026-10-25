import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { RegisterPayload } from '../../core/models/user.model';

interface RoleOption {
  value: string;
  label: string;
  icon: string;
  desc: string;
  badgeColor: string;
  isDoctor?: boolean;
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './register.component.html',
  styleUrl: './register.component.css'
})
export class RegisterComponent {
  // Form fields
  nom = '';
  prenom = '';
  email = '';
  motDePasse = '';
  
  // Optional clinical fields
  age = '';
  cin = '';
  telephone = '';
  adresse = '';
  groupeSanguin = '';
  specialite = '';

  // UI state
  selectedRole = signal<string>('Patient');
  showPwd = false;
  showClinicalFields = signal<boolean>(false);
  loading = signal<boolean>(false);
  errorMsg = signal<string>('');
  success = signal<boolean>(false);
  successMsg = signal<string>('');
  pwdStrength = signal<number>(0);

  roles: RoleOption[] = [
    { value: 'Patient',            label: 'Patient',             icon: '🩺', desc: 'Dossier de soins & suivi',       badgeColor: 'emerald' },
    { value: 'MedecinGeneraliste', label: 'Médecin Généraliste', icon: '👨‍⚕️', desc: 'Pratique médicale globale',     badgeColor: 'cyan', isDoctor: true },
    { value: 'Cardiologue',        label: 'Cardiologue',         icon: '❤️', desc: 'Soins cardiovasculaires',       badgeColor: 'rose', isDoctor: true },
    { value: 'Radiologue',         label: 'Radiologue',          icon: '🩻', desc: 'Imagerie médicale & radios',    badgeColor: 'cyan', isDoctor: true },
    { value: 'MedecinSpecialiste', label: 'Médecin Spécialiste', icon: '🔬', desc: 'Expertises cliniques avancées', badgeColor: 'purple', isDoctor: true },
    { value: 'Stagiaire',          label: 'Stagiaire',           icon: '🎓', desc: 'Étudiant & médecin résident',   badgeColor: 'amber' },
    { value: 'StuffMedical',       label: 'Staff Médical',       icon: '🏥', desc: 'Équipe hospitalière',          badgeColor: 'purple' },
  ];

  bloodGroups = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'];

  // Current selected role object
  currentRole = computed(() => 
    this.roles.find(r => r.value === this.selectedRole()) || this.roles[0]
  );

  isDoctor = computed(() => this.currentRole().isDoctor ?? false);

  // Live generated URI in the ontology
  computedUri = computed(() => {
    const role = this.selectedRole();
    const p = this.prenom.trim();
    const n = this.nom.trim();
    const namePart = (p || n) ? `${p}_${n}`.replace(/[^a-zA-Z0-9_]/g, '_').replace(/^_+|_+$/g, '') : 'Nouvel_Individu';
    
    let prefix = 'Ind_';
    if (role.toLowerCase().includes('medecin') || role.toLowerCase().includes('cardio') || role.toLowerCase().includes('radio')) {
      prefix = 'Dr_';
    } else if (role.toLowerCase().includes('patient')) {
      prefix = 'Pat_';
    } else if (role.toLowerCase().includes('stagiaire')) {
      prefix = 'Stag_';
    }
    return `http://example.org/ontologie-medicale#${prefix}${namePart}`;
  });

  // Live generated Turtle RDF snippet
  liveRdfSnippet = computed(() => {
    const uri = this.computedUri();
    const id = uri.split('#')[1];
    const role = this.selectedRole();
    const fullName = `${this.prenom} ${this.nom}`.trim() || 'Nom Prénom';
    const emailVal = this.email.trim() || 'email@hopital.fr';

    let ttl = `:${id} rdf:type :${role} , owl:NamedIndividual ;\n`;
    ttl += `    rdfs:label "${fullName}" ;\n`;
    ttl += `    :email "${emailVal}" ;\n`;
    ttl += `    :motDePasse "$2b$12$..."`;
    if (this.cin.trim()) ttl += ` ;\n    :numeroCIN "${this.cin.trim()}"`;
    if (this.telephone.trim()) ttl += ` ;\n    :telephone "${this.telephone.trim()}"`;
    if (this.specialite.trim()) ttl += ` ;\n    :specialite "${this.specialite.trim()}"`;
    ttl += ` .`;
    return ttl;
  });

  constructor(private auth: AuthService, private router: Router) {
    if (this.auth.isLoggedIn()) {
      this.router.navigate(['/dashboard']);
    }
  }

  selectRole(val: string): void {
    this.selectedRole.set(val);
  }

  togglePwd(): void {
    this.showPwd = !this.showPwd;
  }

  toggleClinical(): void {
    this.showClinicalFields.update(v => !v);
  }

  checkPwdStrength(val: string): void {
    let score = 0;
    if (val.length >= 6) score++;
    if (val.length >= 9) score++;
    if (/[A-Z]/.test(val) && /[0-9]/.test(val)) score++;
    if (/[^A-Za-z0-9]/.test(val)) score++;
    this.pwdStrength.set(score);
  }

  get pwdStrengthLabel(): string {
    const s = this.pwdStrength();
    if (!this.motDePasse) return '';
    if (s <= 1) return 'Faible (min. 6 car.)';
    if (s <= 2) return 'Moyen';
    if (s === 3) return 'Bon';
    return 'Très sécurisé (Bcrypt)';
  }

  get pwdStrengthClass(): string {
    const s = this.pwdStrength();
    if (s <= 1) return 'weak';
    if (s <= 2) return 'fair';
    if (s === 3) return 'good';
    return 'strong';
  }

  onSubmit(): void {
    if (!this.nom.trim() || !this.prenom.trim() || !this.email.trim() || !this.motDePasse) {
      this.errorMsg.set('Veuillez remplir votre Prénom, Nom, Email et Mot de passe.');
      return;
    }
    if (this.motDePasse.length < 6) {
      this.errorMsg.set('Le mot de passe doit comporter au moins 6 caractères.');
      return;
    }

    this.loading.set(true);
    this.errorMsg.set('');

    const payload: RegisterPayload = {
      nom: this.nom.trim(),
      prenom: this.prenom.trim(),
      email: this.email.trim().toLowerCase(),
      motDePasse: this.motDePasse,
      role: this.selectedRole(),
      age: this.age,
      cin: this.cin,
      telephone: this.telephone,
      adresse: this.adresse,
      groupeSanguin: this.groupeSanguin,
      specialite: this.specialite,
    };

    this.auth.register(payload).subscribe({
      next: (res: any) => {
        this.loading.set(false);
        this.success.set(true);
        this.successMsg.set(
          `Félicitations ${this.prenom} ! Votre profil ${this.selectedRole()} a été créé et intégré dans l'ontologie médicale.`
        );
      },
      error: (msg: string) => {
        this.loading.set(false);
        this.errorMsg.set(msg);
      }
    });
  }
}
