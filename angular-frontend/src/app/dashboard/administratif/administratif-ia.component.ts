
import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdministratifApi } from './administratif.api';
import { NlpAnalyseComponent } from '../medicament/nlp-analyse.component';

/** Onglet « IA — Administratif » : question en français -> NLP -> SPARQL -> résultats. */
@Component({
  selector: 'app-administratif-ia',
  standalone: true,
  imports: [CommonModule, FormsModule, NlpAnalyseComponent],
  template: `
    <section class="tab-content ia-view">
      <div class="ia-module-header">
        <div class="ia-module-badge ia-badge-purple">🗂️ IA</div>
        <div>
          <h2 class="ia-module-title">Assistant IA — Service administratif</h2>
          <p class="ia-module-desc">
            Rendez-vous, dossiers, factures, paiements, remboursements et assurances :
            posez votre question en français.
          </p>
        </div>
      </div>

      <div class="ia-layout">
        <div class="ia-panel glass-panel">
          <textarea
            class="input-glass ia-textarea"
            rows="3"
            [(ngModel)]="question"
            placeholder="Ex : Quelles factures restent à payer ? / Rendez-vous de Sami ?"
            (keydown.enter)="$event.preventDefault(); ask()">
          </textarea>

          <button
            type="button"
            class="btn-primary-purple ask-btn"
            (click)="ask()"
            [disabled]="loading() || !question.trim()">

            @if (loading()) {
              <span class="spinner-dot-sm"></span>
              <span>Analyse...</span>
            } @else {
              <span>🗂️ Interroger l'Ontologie</span>
            }
          </button>

          <div class="suggestions-box">
            <span class="sugg-title">Suggestions Administratif</span>
            <div class="sugg-pills">
              @for (p of prompts; track p) {
                <button
                  type="button"
                  class="sugg-pill sugg-pill-purple"
                  (click)="ask(p)">
                  {{ p }}
                </button>
              }
            </div>
          </div>
        </div>

        <div class="ia-results-panel glass-panel">
          @if (loading()) {
            <div class="state-box">
              <span class="spinner-dot spinner-purple"></span>
              <p>Interrogation de l'ontologie administrative...</p>
            </div>
          } @else if (error()) {
            <div class="alert alert-error">
              <span>⚠️</span>
              <span>{{ error() }}</span>
            </div>
          } @else {
            @if (result(); as r) {
              <div class="result-details">
                <div class="response-header">
                  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                    <span class="badge badge-emerald">✓ Réponse IA</span>
                    <span class="badge badge-purple">Module Administratif</span>
                  </div>
                  <span class="res-count">{{ r.count || 0 }} résultat(s)</span>
                </div>

                <div class="ia-human-response">
                  <b>{{ r.intention }}</b> — {{ r.explication }}
                </div>

                <app-nlp-analyse [nlp]="r.nlp" />

                <div class="sparql-preview-box">
                  <div class="sparql-code-bar">
                    <span class="sparql-code-tag">SPARQL Généré</span>
                  </div>
                  <pre class="sparql-code sparql-code-purple"><code>{{ r.sparql }}</code></pre>
                </div>

                @if (r.donnees?.length > 0) {
                  <div class="ia-data-table-wrap">
                    <h4>Résultats extraits de l'ontologie :</h4>
                    <table class="onto-table">
                      <thead>
                        <tr>
                          @for (c of columns(r.donnees); track c) {
                            <th>{{ label(c) }}</th>
                          }
                        </tr>
                      </thead>
                      <tbody>
                        @for (row of r.donnees; track $index) {
                          <tr>
                            @for (c of columns(r.donnees); track c; let first = $first) {
                              <td
                                [class.col-name]="first"
                                [class.col-text]="!first">
                                {{ cell(c, row[c]) }}
                              </td>
                            }
                          </tr>
                        }
                      </tbody>
                    </table>
                  </div>
                } @else {
                  <p class="ia-empty-hint">
                    Aucun résultat : rien n'est enregistré dans l'ontologie pour cette question.
                  </p>
                }
              </div>
            } @else {
              <div class="state-box empty ia-empty-state">
                <span class="ia-empty-icon">🗂️</span>
                <p class="ia-empty-title">
                  Interrogez l'ontologie du Service administratif
                </p>
                <p class="ia-empty-hint">
                  Dossiers patients, rendez-vous, facturation, paiements, remboursements…
                </p>
              </div>
            }
          }
        </div>
      </div>
    </section>
  `,
 styleUrl: './administratif-ia.component.css'
})
export class AdministratifIaComponent {
  private api = inject(AdministratifApi);

  question = '';
  loading = signal(false);
  error = signal('');
  result = signal<any>(null);

  prompts = [
    'Quels sont les rendez-vous de Sami ?',
    'Agenda du docteur Fatima',
    'Rendez-vous annulés',
    'Quelles factures restent à payer ?',
    'Quelle est la facture la plus chère ?',
    'Qui a payé par carte ?',
    'Qu\'a remboursé la CNAM ?',
    'Patients sans assurance',
    'Dans quelle salle est Amina ?',
    'Quel médecin a le plus de rendez-vous ?',
    'Chiffre d\'affaires',
    'Rendez-vous de Smai'
  ];

  private labels: Record<string, string> = {
    rendez_vous: 'Rendez-vous',
    patient: 'Patient',
    medecin: 'Médecin',
    date: 'Date',
    motif: 'Motif',
    statut: 'Statut',
    facture: 'Facture',
    total: 'Total (TND)',
    paye: 'Payé (TND)',
    rembourse: 'Remboursé (TND)',
    reste: 'Reste (TND)',
    paiement: 'Paiement',
    montant: 'Montant (TND)',
    mode: 'Mode',
    remboursement: 'Remboursement',
    assurance: 'Assurance',
    taux_couverture: 'Taux de couverture',
    dossier: 'Dossier',
    salle: 'Salle',
    ouverture: 'Ouverture',
    total_facture: 'Total facturé (TND)',
    total_encaisse: 'Total encaissé (TND)',
    nb_rendez_vous: 'Nb rendez-vous'
  };

  ask(prompt?: string): void {
    const q = prompt || this.question;

    if (!q.trim()) return;

    this.question = q;
    this.loading.set(true);
    this.error.set('');
    this.result.set(null);

    this.api.ask(q).subscribe({
      next: (r) => {
        this.loading.set(false);
        this.result.set(r);
      },
      error: (e) => {
        this.loading.set(false);
        this.error.set(e.error?.error || 'Erreur IA Administratif.');
      }
    });
  }

  columns(rows: any[]): string[] {
    return rows?.length ? Object.keys(rows[0]) : [];
  }

  label(c: string): string {
    return this.labels[c] || c;
  }

  cell(c: string, v: any): string {
    if (v === null || v === undefined || v === '') return '—';

    return c === 'taux_couverture' && !isNaN(+v)
      ? `${Math.round(+v * 100)} %`
      : String(v).replace(/_/g, ' ');
  }
}
