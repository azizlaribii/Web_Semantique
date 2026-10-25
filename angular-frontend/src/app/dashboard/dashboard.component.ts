import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../core/services/auth.service';
import { ApiService } from '../core/services/api.service';
import { Personne, User } from '../core/models/user.model';
import { NavbarComponent } from '../shared/navbar/navbar.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, NavbarComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  auth = inject(AuthService);
  private api = inject(ApiService);

  currentUser = this.auth.currentUser;

  // Active tab
  activeTab = signal<'personnes' | 'ia-personnes' | 'ia-maladies' | 'ia-medicaments' | 'maladies' | 'sparql' | 'profil'>('personnes');

  // Personnes state
  personnes = signal<Personne[]>([]);
  loadingPersonnes = signal(false);
  personneSearch = signal('');
  selectedRoleFilter = signal('ALL');

  // Stats
  totalTriplets = signal(0);

  // ── IA PERSONNES ────────────────────────────────────────────────────────
  iaPersonneQuestion = '';
  iaPersonneLoading = signal(false);
  iaPersonneResult = signal<any>(null);
  iaPersonneError = signal('');
  iaPersonnePrompts = [
    'Donne-moi les sous-classes de Personne',
    'Donne-moi le médecin Aziz Laribi',
    'Quelles sont les sous-classes de Medecin ?',
    'Quelles sont les classes de l\'ontologie ?',
    'Qui a pour spécialité Cardiologie ?',
    'Quelles sont les Object Properties ?',
    'Quelles sont les Data Properties ?',
    'Quels sont tous les individus ?',
    'Donne-moi la liste des patients.',
    'Qui est Dr Karim ?',
    'Quels sont les cardiologues ?',
    'Médecins avec plus de 40 ans.',
  ];

  // ── IA MALADIES ─────────────────────────────────────────────────────────
  iaMaladieQuestion = '';
  iaMaladieLoading = signal(false);
  iaMaladieResult = signal<any>(null);
  iaMaladieError = signal('');
  iaMaladiePrompts = [
    'Quelles sont les maladies contagieuses ?',
    'Quels sont les symptômes de la grippe ?',
    'Quels patients ont le diabète ?',
    'Quelles maladies sont chroniques ?',
    'Quelle est la gravité de l\'hypertension ?',
    'Quels médicaments traitent l\'angine ?',
    'C\'est quoi le diabète ?',
  ];

  // ── IA MÉDICAMENTS ───────────────────────────────────────────────────────
  iaMedicamentQuestion = '';
  iaMedicamentLoading = signal(false);
  iaMedicamentResult = signal<any>(null);
  iaMedicamentError = signal('');
  iaMedicamentPrompts = [
    'Donne-moi la liste de tous les médicaments.',
    'Quels sont les antibiotiques disponibles ?',
    'Quel est le dosage du paracétamol ?',
    'Quels médicaments traitent le diabète ?',
    'Quels antalgiques sont disponibles ?',
    'Quels sont les anti-inflammatoires ?',
    'Médicaments avec code ATC disponibles.',
  ];

  // SPARQL state
  sparqlQuery = `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?individu ?nom ?prenom ?role
WHERE {
  ?individu rdf:type ?role ;
            med:nom ?nom ;
            med:prenom ?prenom .
  FILTER (?role != <http://www.w3.org/2002/07/owl#NamedIndividual>)
}
LIMIT 20`;
  sparqlLoading = signal(false);
  sparqlResult = signal<any>(null);
  sparqlError = signal('');

  // Maladies & Médicaments catalog
  maladies = signal<any[]>([]);
  medicaments = signal<any[]>([]);
  loadingCatalog = signal(false);

  // Filtered Personnes
  filteredPersonnes = computed(() => {
    const q = this.personneSearch().toLowerCase().trim();
    const roleFilter = this.selectedRoleFilter();

    return this.personnes().filter(p => {
      const typeStr = (p.types || []).join(' ').toLowerCase();
      let matchesRole = true;
      if (roleFilter !== 'ALL') {
        matchesRole = typeStr.includes(roleFilter.toLowerCase());
      }
      if (!matchesRole) return false;
      if (!q) return true;

      const searchHaystack = [
        p.nom || '', p.prenom || '', p.cin || '',
        p.telephone || '', p.specialite || '', p.adresse || '', typeStr
      ].join(' ').toLowerCase();

      return searchHaystack.includes(q);
    });
  });

  // Role Counts
  countMedecins = computed(() =>
    this.personnes().filter(p => (p.types || []).some(t =>
      t.toLowerCase().includes('medecin') || t.toLowerCase().includes('cardio') || t.toLowerCase().includes('radio')
    )).length
  );

  countPatients = computed(() =>
    this.personnes().filter(p => (p.types || []).some(t => t.toLowerCase().includes('patient'))).length
  );

  countStagiaires = computed(() =>
    this.personnes().filter(p => (p.types || []).some(t => t.toLowerCase().includes('stagiaire'))).length
  );

  ngOnInit(): void {
    this.loadPersonnes();
    this.loadSummary();
    this.loadCatalog();
  }

  setTab(tab: 'personnes' | 'ia-personnes' | 'ia-maladies' | 'ia-medicaments' | 'maladies' | 'sparql' | 'profil'): void {
    this.activeTab.set(tab);
  }

  loadPersonnes(): void {
    this.loadingPersonnes.set(true);
    this.api.getPersonnes().subscribe({
      next: (list) => { this.personnes.set(list || []); this.loadingPersonnes.set(false); },
      error: () => this.loadingPersonnes.set(false)
    });
  }

  loadSummary(): void {
    this.api.getSummary().subscribe({
      next: (res) => { if (res?.total_triplets) this.totalTriplets.set(res.total_triplets); },
      error: () => {}
    });
  }

  loadCatalog(): void {
    this.loadingCatalog.set(true);
    this.api.getMaladies().subscribe({ next: (data) => this.maladies.set(data || []), error: () => {} });
    this.api.getMedicaments().subscribe({
      next: (data) => { this.medicaments.set(data || []); this.loadingCatalog.set(false); },
      error: () => this.loadingCatalog.set(false)
    });
  }

  // ── IA Handlers ────────────────────────────────────────────────────────

  onAskPersonnes(prompt?: string): void {
    const question = prompt || this.iaPersonneQuestion;
    if (!question.trim()) return;
    this.iaPersonneQuestion = question;
    this.iaPersonneLoading.set(true);
    this.iaPersonneError.set('');
    this.iaPersonneResult.set(null);

    this.api.askIA(question, 'personnes').subscribe({
      next: (res) => { this.iaPersonneLoading.set(false); this.iaPersonneResult.set(res); },
      error: (err) => {
        this.iaPersonneLoading.set(false);
        this.iaPersonneError.set(err.error?.error || 'Erreur IA Personnes.');
      }
    });
  }

  onAskMaladies(prompt?: string): void {
    const question = prompt || this.iaMaladieQuestion;
    if (!question.trim()) return;
    this.iaMaladieQuestion = question;
    this.iaMaladieLoading.set(true);
    this.iaMaladieError.set('');
    this.iaMaladieResult.set(null);

    this.api.askIA(question, 'maladie').subscribe({
      next: (res) => { this.iaMaladieLoading.set(false); this.iaMaladieResult.set(res); },
      error: (err) => {
        this.iaMaladieLoading.set(false);
        this.iaMaladieError.set(err.error?.error || 'Erreur IA Maladies.');
      }
    });
  }

  onAskMedicaments(prompt?: string): void {
    const question = prompt || this.iaMedicamentQuestion;
    if (!question.trim()) return;
    this.iaMedicamentQuestion = question;
    this.iaMedicamentLoading.set(true);
    this.iaMedicamentError.set('');
    this.iaMedicamentResult.set(null);

    this.api.askIA(question, 'medicament').subscribe({
      next: (res) => { this.iaMedicamentLoading.set(false); this.iaMedicamentResult.set(res); },
      error: (err) => {
        this.iaMedicamentLoading.set(false);
        this.iaMedicamentError.set(err.error?.error || 'Erreur IA Médicaments.');
      }
    });
  }

  onExecuteSparql(): void {
    if (!this.sparqlQuery.trim()) return;
    this.sparqlLoading.set(true);
    this.sparqlError.set('');
    this.sparqlResult.set(null);

    this.api.runSparql(this.sparqlQuery).subscribe({
      next: (res) => { this.sparqlLoading.set(false); this.sparqlResult.set(res); },
      error: (err) => {
        this.sparqlLoading.set(false);
        this.sparqlError.set(err.error?.error || 'Erreur d\'exécution SPARQL.');
      }
    });
  }

  getPrimaryType(p: Personne): string {
    const types = p.types || [];
    const valid = types.filter(t => t !== 'NamedIndividual' && t !== 'Thing');
    return valid.length > 0 ? valid[0] : 'Personne';
  }

  getTypeBadgeClass(p: Personne): string {
    const t = this.getPrimaryType(p).toLowerCase();
    if (t.includes('medecin') || t.includes('cardio') || t.includes('radio')) return 'badge-cyan';
    if (t.includes('patient')) return 'badge-emerald';
    if (t.includes('stagiaire')) return 'badge-purple';
    return 'badge-amber';
  }

  // ── Helpers pour affichage Sous-classes & Classes ────────────────────────
  subclassSearch = signal('');
  classSearch = signal('');
  classCategoryFilter = signal('ALL');
  copiedFeedback = signal(false);

  copyText(text: string): void {
    if (!text) return;
    navigator.clipboard.writeText(text);
    this.copiedFeedback.set(true);
    setTimeout(() => this.copiedFeedback.set(false), 2000);
  }

  getDirectSubclasses(items: any[]): any[] {
    if (!items) return [];
    const q = this.subclassSearch().toLowerCase().trim();
    return items.filter(item => {
      const isDirect = item.estDirecte === 'Oui';
      const matchesSearch = !q || (item.nom || '').toLowerCase().includes(q) || (item.parent || '').toLowerCase().includes(q);
      return isDirect && matchesSearch;
    });
  }

  getDescendantSubclasses(items: any[]): any[] {
    if (!items) return [];
    const q = this.subclassSearch().toLowerCase().trim();
    return items.filter(item => {
      const isDirect = item.estDirecte === 'Oui';
      const matchesSearch = !q || (item.nom || '').toLowerCase().includes(q) || (item.parent || '').toLowerCase().includes(q);
      return !isDirect && matchesSearch;
    });
  }

  getAllSubclassesFiltered(items: any[]): any[] {
    if (!items) return [];
    const q = this.subclassSearch().toLowerCase().trim();
    if (!q) return items;
    return items.filter(item =>
      (item.nom || '').toLowerCase().includes(q) ||
      (item.parent || '').toLowerCase().includes(q) ||
      (item.label || '').toLowerCase().includes(q) ||
      (item.description || '').toLowerCase().includes(q)
    );
  }

  getFilteredClasses(items: any[]): any[] {
    if (!items) return [];
    const q = this.classSearch().toLowerCase().trim();
    const cat = this.classCategoryFilter();

    return items.filter(item => {
      const nom = (item.nom || item.classe || '').toLowerCase();
      const parent = (item.parent || '').toLowerCase();
      const desc = (item.description || item.label || '').toLowerCase();

      let matchCat = true;
      if (cat === 'PERSONNES') {
        matchCat = nom.includes('medecin') || nom.includes('patient') || nom.includes('stagiaire') || nom.includes('role') || nom.includes('stuff') || parent.includes('personne') || parent.includes('role');
      } else if (cat === 'SOINS') {
        matchCat = nom.includes('maladie') || nom.includes('symptome') || nom.includes('operation') || nom.includes('consultation') || nom.includes('grippe') || nom.includes('angine');
      } else if (cat === 'MEDICAMENTS') {
        matchCat = nom.includes('medicament') || nom.includes('antibiotique') || nom.includes('antalgique') || nom.includes('molecule') || nom.includes('paracetamol');
      } else if (cat === 'SERVICES') {
        matchCat = nom.includes('service') || nom.includes('dossier') || nom.includes('factur') || nom.includes('ordonnance');
      }

      const matchQ = !q || nom.includes(q) || parent.includes(q) || desc.includes(q);
      return matchCat && matchQ;
    });
  }
}
