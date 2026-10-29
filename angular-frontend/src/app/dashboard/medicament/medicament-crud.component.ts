import { Component, EventEmitter, OnInit, Output, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

interface MedForm {
  nom: string; dosage: string; forme: string; voie: string; posologie: string;
  codeATC: string; prix: string; ordonnance: boolean;
  classes: string[]; moleculeId: string; moleculeNom: string; moleculeFormule: string;
  effets: string[]; conditions: string[]; maladiesTraitees: string[]; maladiesContreIndiquees: string[];
}

const NEW_MOL = '__new__';
const LIST_KEYS = ['classes', 'effets', 'conditions', 'maladiesTraitees', 'maladiesContreIndiquees'] as const;
const TEXT_KEYS = ['nom', 'dosage', 'forme', 'voie', 'posologie', 'codeATC', 'prix'] as const;

/**
 * Gestion des médicaments (CRUD). Chaque action appelle l'API Flask, qui exécute une requête
 * SPARQL Update (INSERT DATA / DELETE-INSERT WHERE / DELETE WHERE) puis enregistre l'ontologie OWL.
 */
@Component({
  selector: 'app-medicament-crud',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './medicament-crud.component.html',
  styleUrl: './medicament-crud.component.css'
})
export class MedicamentCrudComponent implements OnInit {
  private api = inject(ApiService);
  @Output() changed = new EventEmitter<void>();

  readonly NEW_MOL = NEW_MOL;
  readonly classLabels: Record<string, string> = {
    Antalgique: 'Antalgique', AntiInflammatoire: 'Anti-inflammatoire', Antibiotique: 'Antibiotique',
    Antidiabetique: 'Antidiabétique', Antihypertenseur: 'Antihypertenseur',
    AntiUlcereux: 'Anti-ulcéreux', Anticoagulant: 'Anticoagulant'
  };

  options = signal<any>({ classes: [], molecules: [], effets: [], conditions: [], maladies: [] });
  medicaments = signal<any[]>([]);
  loading = signal(false);
  saving = signal(false);
  status = signal<{ text: string; kind: 'ok' | 'error' | '' }>({ text: '', kind: '' });
  lastSparql = signal<{ label: string; query: string } | null>(null);
  editId = signal<string | null>(null);
  armedDelete = signal<string | null>(null);
  armedReset = signal(false);
  highlight = signal<string | null>(null);

  form: MedForm = this.emptyForm();
  private original: MedForm | null = null;

  ngOnInit(): void {
    this.refresh();
  }

  emptyForm(): MedForm {
    return {
      nom: '', dosage: '', forme: '', voie: 'Orale', posologie: '', codeATC: '', prix: '', ordonnance: false,
      classes: [], moleculeId: '', moleculeNom: '', moleculeFormule: '',
      effets: [], conditions: [], maladiesTraitees: [], maladiesContreIndiquees: []
    };
  }

  refresh(): void {
    this.loading.set(true);
    this.api.getMedicamentOptions().subscribe({
      next: (o) => {
        this.options.set(o);
        if (!this.form.moleculeId && o.molecules?.length) this.form.moleculeId = o.molecules[0].id;
      }
    });
    this.api.getMedicaments().subscribe({
      next: (list) => { this.medicaments.set(list || []); this.loading.set(false); },
      error: () => this.loading.set(false)
    });
  }

  // ── Cases à cocher ─────────────────────────────────────────────────────
  isChecked(key: typeof LIST_KEYS[number], id: string): boolean {
    return this.form[key].includes(id);
  }

  toggle(key: typeof LIST_KEYS[number], id: string, checked: boolean): void {
    const list = this.form[key].filter(x => x !== id);
    if (checked) list.push(id);
    this.form[key] = list;
  }

  // ── Création / modification ────────────────────────────────────────────
  private payload(): any {
    const f = this.form;
    const data: any = { ordonnance: f.ordonnance };
    TEXT_KEYS.forEach(k => data[k] = String(f[k] ?? '').trim());
    LIST_KEYS.forEach(k => data[k] = [...f[k]]);
    if (f.moleculeId === NEW_MOL) {
      data.moleculeNom = f.moleculeNom.trim();
      data.moleculeFormule = f.moleculeFormule.trim();
    } else {
      data.moleculeId = f.moleculeId;
    }
    return data;
  }

  /** En modification, n'envoie que les champs changés : la requête DELETE/INSERT reste courte. */
  private changedFields(data: any): any {
    const o = this.original!;
    const same = (a: any, b: any) => Array.isArray(a)
      ? JSON.stringify([...a].sort()) === JSON.stringify([...(b || [])].sort())
      : String(a ?? '') === String(b ?? '');
    const out: any = {};
    [...TEXT_KEYS, ...LIST_KEYS, 'ordonnance'].forEach(k => {
      if (!same(data[k], (o as any)[k])) out[k] = data[k];
    });
    if (this.form.moleculeId === NEW_MOL || this.form.moleculeId !== o.moleculeId) {
      ['moleculeId', 'moleculeNom', 'moleculeFormule'].forEach(k => { if (data[k] !== undefined) out[k] = data[k]; });
    }
    return out;
  }

  submit(): void {
    if (!this.form.nom.trim()) { this.setStatus('Le nom commercial est obligatoire.', 'error'); return; }
    if (!this.form.classes.length) { this.setStatus('Choisissez au moins une classe thérapeutique.', 'error'); return; }
    const editing = this.editId();
    let body = this.payload();
    if (editing) {
      body = this.changedFields(body);
      if (!Object.keys(body).length) { this.setStatus('Aucune modification à enregistrer.', ''); return; }
    }
    this.saving.set(true);
    this.setStatus(editing ? 'Modification en cours…' : 'Ajout en cours…', '');
    const call = editing ? this.api.updateMedicament(editing, body) : this.api.createMedicament(body);
    call.subscribe({
      next: (r) => {
        this.saving.set(false);
        this.lastSparql.set({ label: `Requête SPARQL Update exécutée — ${r.operation}`, query: r.sparql_update });
        this.setStatus(`${r.id} ${editing ? 'modifié' : 'ajouté'} et enregistré dans ontologie_medicament.owl.`, 'ok');
        this.cancelEdit(false);
        this.flash(r.id);
        this.afterChange();
      },
      error: (err) => {
        this.saving.set(false);
        this.setStatus(err.error?.error || 'Erreur lors de l\'enregistrement.', 'error');
      }
    });
  }

  startEdit(m: any): void {
    this.editId.set(m.id);
    this.form = {
      nom: m.nom || '', dosage: m.dosage || '', forme: m.forme || '', voie: m.voie || '',
      posologie: m.posologie || '', codeATC: m.codeATC || '', prix: m.prix || '', ordonnance: !!m.ordonnance,
      classes: [...(m.classes || [])],
      moleculeId: m.molecules?.[0]?.id || '', moleculeNom: '', moleculeFormule: '',
      effets: (m.effets || []).map((e: any) => e.id),
      conditions: (m.contreIndications || []).filter((c: any) => c.source === 'condition').map((c: any) => c.id),
      maladiesContreIndiquees: (m.contreIndications || []).filter((c: any) => c.source === 'maladie').map((c: any) => c.id),
      maladiesTraitees: [...(m.maladiesTraiteesIds || [])]
    };
    this.original = this.payload();
    this.setStatus('', '');
    document.getElementById('med-crud-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  cancelEdit(clearStatus = true): void {
    const mol = this.options().molecules?.[0]?.id || '';
    this.form = this.emptyForm();
    this.form.moleculeId = mol;
    this.editId.set(null);
    this.original = null;
    if (clearStatus) this.setStatus('', '');
  }

  // ── Suppression (confirmation en deux clics, sans boîte de dialogue) ───
  askDelete(m: any): void {
    if (this.armedDelete() !== m.id) {
      this.armedDelete.set(m.id);
      setTimeout(() => { if (this.armedDelete() === m.id) this.armedDelete.set(null); }, 4000);
      return;
    }
    this.armedDelete.set(null);
    this.api.deleteMedicament(m.id).subscribe({
      next: (r) => {
        this.lastSparql.set({ label: 'Requête SPARQL Update exécutée — DELETE', query: r.sparql_update });
        this.setStatus(`${m.id} supprimé (avec ses interactions et essais cliniques).`, 'ok');
        if (this.editId() === m.id) this.cancelEdit(false);
        this.afterChange();
      },
      error: (err) => this.setStatus(err.error?.error || 'Erreur lors de la suppression.', 'error')
    });
  }

  askReset(): void {
    if (!this.armedReset()) {
      this.armedReset.set(true);
      setTimeout(() => this.armedReset.set(false), 4000);
      return;
    }
    this.armedReset.set(false);
    this.api.resetMedicaments().subscribe({
      next: () => {
        this.lastSparql.set(null);
        this.cancelEdit(false);
        this.setStatus('Ontologie d\'origine restaurée.', 'ok');
        this.afterChange();
      },
      error: (err) => this.setStatus(err.error?.error || 'Erreur lors de la réinitialisation.', 'error')
    });
  }

  // ── Utilitaires ────────────────────────────────────────────────────────
  private afterChange(): void {
    this.refresh();
    this.changed.emit();
  }

  private flash(id: string): void {
    this.highlight.set(id);
    setTimeout(() => this.highlight.set(null), 2500);
  }

  private setStatus(text: string, kind: 'ok' | 'error' | ''): void {
    this.status.set({ text, kind });
  }

  classLabelOf = (c: string): string => this.classLabels[c] || c;

  isRisque(m: any): boolean {
    return (m.inferences || []).includes('MedicamentARisque');
  }

  effetsLabel(m: any): string {
    return (m.effets || []).map((e: any) => e.nom).join(', ') || '—';
  }
}
