import { Component, EventEmitter, OnInit, Output, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdministratifApi } from './administratif.api';

/** Onglet « Gestion Administrative » : CRUD des rendez-vous + facturation/paiement en SPARQL Update. */
@Component({
  selector: 'app-administratif-crud',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
  <div class="kpis">
    @for (k of kpis(); track k.label) {
      <div class="kpi glass-panel"><span class="kpi-val">{{ k.value }}</span><span class="kpi-lbl">{{ k.label }}</span></div>
    }
  </div>

  <div class="crud-layout">
    <form class="glass-panel crud-form" (ngSubmit)="submit()" autocomplete="off">
      <h2>{{ editId() ? 'Modifier ' + editId() : 'Planifier un rendez-vous' }}</h2>
      <p class="crud-sub">Chaque action exécute une requête <b>SPARQL Update</b> et enregistre <code>ontologie_administratif.owl</code>.</p>

      <label class="field">Patient *
        <select class="input-glass" name="patient" [(ngModel)]="form.patient">
          @for (p of options().patients; track p.id) { <option [value]="p.id">{{ p.nom || p.id }}</option> }
        </select>
      </label>
      <label class="field">Médecin *
        <select class="input-glass" name="medecin" [(ngModel)]="form.medecin">
          @for (m of options().medecins; track m.id) { <option [value]="m.id">{{ m.nom || m.id }}</option> }
        </select>
      </label>
      <div class="row2">
        <label class="field">Date et heure *<input class="input-glass" type="datetime-local" name="date" [(ngModel)]="form.date" /></label>
        <label class="field">Durée (min)<input class="input-glass" type="number" min="5" step="5" name="duree" [(ngModel)]="form.duree" /></label>
      </div>
      <label class="field">Motif<input class="input-glass" name="motif" [(ngModel)]="form.motif" placeholder="Contrôle, suivi…" /></label>
      <label class="field">Statut
        <select class="input-glass" name="statut" [(ngModel)]="form.statut">
          @for (s of options().statuts; track s) { <option [value]="s">{{ s }}</option> }
        </select>
      </label>
      <div class="actions">
        <button type="submit" class="btn-primary" [disabled]="saving()">{{ editId() ? 'Enregistrer (DELETE / INSERT WHERE)' : 'Ajouter (INSERT DATA)' }}</button>
        @if (editId()) { <button type="button" class="btn-secondary" (click)="cancelEdit()">Annuler</button> }
      </div>
      @if (status().text) { <p class="status" [class.ok]="status().kind === 'ok'" [class.error]="status().kind === 'error'">{{ status().text }}</p> }
    </form>

    <div class="crud-right">
      <div class="glass-panel list-panel">
        <div class="head">
          <div><h2>Rendez-vous</h2><p class="crud-sub">{{ rdvs().length }} individus · les statuts « Annulé » / « Confirmé » sont inférés par règle.</p></div>
          <button type="button" class="btn-secondary btn-sm" (click)="askReset()">{{ armedReset() ? 'Confirmer ?' : 'Réinitialiser l\\'ontologie' }}</button>
        </div>
        @for (r of rdvs(); track r.id) {
          <div class="row" [class.flash]="highlight() === r.id" [class.editing]="editId() === r.id">
            <div class="main">
              <div class="name">{{ r.id }} · {{ r.pnom || r.patient }}
                <span class="badge" [ngClass]="'st-' + r.statut">{{ r.statut }}</span>
                @if (r.facture) { <span class="badge st-fac">{{ r.facture }}</span> }
              </div>
              <div class="meta">{{ r.date | date:'dd/MM/yyyy HH:mm' }} · {{ r.mnom || r.medecin }} · {{ r.motif || '—' }} · {{ r.duree }} min</div>
              @if (factureOf(r.facture); as f) {
                <div class="meta small">Total {{ f.total | number:'1.2-2' }} TND · payé {{ f.paye | number:'1.2-2' }} · remboursé {{ f.rembourse | number:'1.2-2' }} ·
                  <b>reste {{ f.reste | number:'1.2-2' }} TND</b> ({{ f.statut }})</div>
              }
              @if (billing() === r.id) {
                <div class="inline">
                  @if (!r.facture) {
                    <input class="input-glass" type="number" min="1" step="0.5" placeholder="Montant TND" [(ngModel)]="amount" [ngModelOptions]="{standalone: true}" />
                    <button type="button" class="mini" (click)="facturer(r)">Créer la facture</button>
                  } @else {
                    <input class="input-glass" type="number" min="1" step="0.5" placeholder="Montant TND" [(ngModel)]="amount" [ngModelOptions]="{standalone: true}" />
                    <select class="input-glass" [(ngModel)]="mode" [ngModelOptions]="{standalone: true}">
                      @for (m of options().modes; track m) { <option [value]="m">{{ m }}</option> }
                    </select>
                    <button type="button" class="mini" (click)="encaisser(r)">Encaisser</button>
                  }
                </div>
              }
            </div>
            <div class="actions-col">
              <button type="button" class="mini" (click)="startEdit(r)">Modifier</button>
              <button type="button" class="mini" (click)="toggleBilling(r)">{{ r.facture ? 'Paiement' : 'Facturer' }}</button>
              <button type="button" class="mini danger" [class.armed]="armedDelete() === r.id" (click)="askDelete(r)">
                {{ armedDelete() === r.id ? 'Confirmer ?' : 'Supprimer' }}</button>
            </div>
          </div>
        } @empty { <p class="muted">Chargement…</p> }
      </div>

      @if (lastSparql(); as sp) {
        <div class="glass-panel sparql-panel">
          <div class="sparql-bar">{{ sp.label }}</div>
          <pre class="sparql-pre"><code>{{ sp.query }}</code></pre>
        </div>
      }
    </div>
  </div>
  `,
  styles: [`
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .kpi { display: flex; flex-direction: column; gap: 2px; padding: 12px 16px; }
    .kpi-val { font-size: 1.35rem; font-weight: 700; color: var(--accent-purple); }
    .kpi-lbl { font-size: 0.74rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: .04em; }
    .crud-layout { display: grid; grid-template-columns: minmax(300px, 380px) 1fr; gap: 18px; align-items: start; }
    .crud-form, .list-panel { padding: 18px; display: flex; flex-direction: column; gap: 10px; }
    .crud-right { display: flex; flex-direction: column; gap: 16px; }
    .crud-sub { font-size: .8rem; color: var(--text-dim); margin: 0; }
    .field { display: flex; flex-direction: column; gap: 4px; font-size: .8rem; font-weight: 600; }
    .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
    .row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: #fff; }
    .row.editing { border-color: var(--accent-purple); } .row.flash { animation: flash 1.4s ease; }
    @keyframes flash { 0% { background: #ede9fe; } 100% { background: #fff; } }
    .main { display: flex; flex-direction: column; gap: 3px; flex: 1; min-width: 0; }
    .name { font-weight: 600; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .meta { font-size: .8rem; color: var(--text-muted); } .meta.small { font-size: .76rem; }
    .inline { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; } .inline input { max-width: 130px; }
    .actions-col { display: flex; flex-direction: column; gap: 6px; }
    .mini { font-size: .76rem; padding: 4px 10px; border-radius: 8px; border: 1px solid var(--border-subtle); background: #f8fafc; cursor: pointer; }
    .mini.danger { color: #be123c; } .mini.armed { background: #be123c; color: #fff; }
    .badge { font-size: .68rem; padding: 1px 8px; border-radius: 999px; border: 1px solid; }
    .st-Planifie { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
    .st-Confirme { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
    .st-Annule { background: #fff1f2; color: #be123c; border-color: #fecdd3; }
    .st-Termine { background: #f1f5f9; color: #475569; border-color: #cbd5e1; }
    .st-fac { background: #f5f3ff; color: #6d28d9; border-color: #ddd6fe; }
    .status { font-size: .82rem; margin: 0; } .status.ok { color: #047857; } .status.error { color: #be123c; }
    .muted { color: var(--text-dim); }
    .sparql-panel { overflow: hidden; } .sparql-bar { padding: 8px 14px; font-size: .78rem; font-weight: 700; background: #f5f3ff; }
    .sparql-pre { margin: 0; padding: 14px 16px; max-height: 320px; overflow: auto; background: #0f172a; color: #e2e8f0; font-size: .74rem; line-height: 1.55; }
    @media (max-width: 1000px) { .crud-layout { grid-template-columns: 1fr; } }
  `]
})
export class AdministratifCrudComponent implements OnInit {
  private api = inject(AdministratifApi);
  @Output() changed = new EventEmitter<void>();

  options = signal<any>({ patients: [], medecins: [], statuts: [], modes: [] });
  rdvs = signal<any[]>([]);
  factures = signal<any[]>([]);
  kpis = signal<{ label: string; value: string }[]>([]);
  saving = signal(false);
  status = signal<{ text: string; kind: 'ok' | 'error' | '' }>({ text: '', kind: '' });
  lastSparql = signal<{ label: string; query: string } | null>(null);
  editId = signal<string | null>(null);
  armedDelete = signal<string | null>(null);
  armedReset = signal(false);
  highlight = signal<string | null>(null);
  billing = signal<string | null>(null);
  amount: number | null = null;
  mode = 'Especes';
  form: any = this.emptyForm();

  ngOnInit(): void { this.refresh(); }

  emptyForm(): any { return { patient: '', medecin: '', date: '', duree: 20, motif: '', statut: 'Planifie' }; }

  refresh(): void {
    this.api.options().subscribe(o => {
      this.options.set(o);
      if (!this.form.patient && o.patients?.length) this.form.patient = o.patients[0].id;
      if (!this.form.medecin && o.medecins?.length) this.form.medecin = o.medecins[0].id;
    });
    this.api.rendezVous().subscribe(l => this.rdvs.set(l || []));
    this.api.factures().subscribe(l => this.factures.set(l || []));
    this.api.summary().subscribe(s => this.kpis.set([
      { label: 'Dossiers', value: String(s.dossiers) }, { label: 'Rendez-vous à venir', value: String(s.rdv_a_venir) },
      { label: 'Factures impayées', value: String(s.factures_impayees) },
      { label: 'Encaissé (TND)', value: s.encaisse_tnd.toFixed(2) }, { label: 'Reste à payer (TND)', value: s.reste_a_payer_tnd.toFixed(2) }]));
  }

  factureOf(id: string | null): any { return id ? this.factures().find(f => f.id === id) : null; }

  private ok(label: string, r: any, text: string): void {
    this.saving.set(false);
    this.lastSparql.set({ label, query: r.sparql_update });
    this.status.set({ text, kind: 'ok' });
    this.highlight.set(r.id); setTimeout(() => this.highlight.set(null), 1500);
    this.refresh(); this.changed.emit();
  }
  private fail(e: any): void { this.saving.set(false); this.status.set({ text: e.error?.error || 'Erreur serveur.', kind: 'error' }); }

  submit(): void {
    if (!this.form.patient || !this.form.medecin || !this.form.date) { this.status.set({ text: 'Patient, médecin et date sont obligatoires.', kind: 'error' }); return; }
    this.saving.set(true);
    const f = this.form, id = this.editId();
    const body = { patient: f.patient, medecin: f.medecin, date: f.date, duree: f.duree, motif: f.motif, statut: f.statut };
    if (id) {
      this.api.updateRdv(id, body).subscribe({ next: r => { this.ok(`UPDATE ${r.id} — DELETE / INSERT / WHERE`, r, `${r.id} modifié et enregistré.`); this.cancelEdit(); }, error: e => this.fail(e) });
    } else {
      this.api.createRdv(body).subscribe({ next: r => { this.ok(`CREATE ${r.id} — INSERT DATA`, r, `${r.id} ajouté et enregistré.`); this.form = { ...this.emptyForm(), patient: f.patient, medecin: f.medecin }; }, error: e => this.fail(e) });
    }
  }

  startEdit(r: any): void {
    this.editId.set(r.id);
    this.form = { patient: r.patient, medecin: r.medecin, date: (r.date || '').slice(0, 16), duree: +r.duree || 20, motif: r.motif || '', statut: r.statut };
    this.status.set({ text: '', kind: '' });
  }
  cancelEdit(): void { this.editId.set(null); this.form = { ...this.emptyForm(), patient: this.options().patients[0]?.id || '', medecin: this.options().medecins[0]?.id || '' }; }

  askDelete(r: any): void {
    if (this.armedDelete() !== r.id) { this.armedDelete.set(r.id); setTimeout(() => this.armedDelete.set(null), 3000); return; }
    this.armedDelete.set(null);
    this.api.deleteRdv(r.id).subscribe({ next: x => this.ok(`DELETE ${x.id} — DELETE WHERE`, x, `${x.id} supprimé.`), error: e => this.fail(e) });
  }

  toggleBilling(r: any): void { this.billing.set(this.billing() === r.id ? null : r.id); this.amount = null; }
  facturer(r: any): void {
    this.api.createFacture({ rdv: r.id, montant: this.amount }).subscribe({ next: x => { this.ok(`CREATE ${x.id} — INSERT DATA`, x, `Facture ${x.id} créée.`); this.billing.set(null); }, error: e => this.fail(e) });
  }
  encaisser(r: any): void {
    this.api.createPaiement({ facture: r.facture, montant: this.amount, mode: this.mode }).subscribe({ next: x => { this.ok(`CREATE ${x.id} — INSERT DATA`, x, `Paiement ${x.id} enregistré : la facture est reclassée par règle d'inférence.`); this.billing.set(null); }, error: e => this.fail(e) });
  }

  askReset(): void {
    if (!this.armedReset()) { this.armedReset.set(true); setTimeout(() => this.armedReset.set(false), 3000); return; }
    this.armedReset.set(false);
    this.api.reset().subscribe({ next: () => { this.status.set({ text: 'Ontologie restaurée.', kind: 'ok' }); this.lastSparql.set(null); this.refresh(); this.changed.emit(); }, error: e => this.fail(e) });
  }
}
