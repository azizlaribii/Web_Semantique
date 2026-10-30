
import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MedicalApi } from './medical.api';
import { NlpAnalyseComponent } from '../medicament/nlp-analyse.component';

@Component({
  selector: 'app-medical-ia',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NlpAnalyseComponent
  ],
  template: `
    <section class="tab-content ia-view">

      <!-- En-tête du module -->
      <div class="ia-module-header">
        <div
          class="ia-module-badge"
          style="background:#e0f2fe;color:#0369a1"
        >
          🩺 IA
        </div>

        <div>
          <h2 class="ia-module-title">
            Assistant IA — Service médical
          </h2>

          <p class="ia-module-desc">
            Consultations, opérations et ordonnances :
            posez votre question en français.
          </p>
        </div>
      </div>

      <div class="ia-layout">

        <!-- Zone de question -->
        <div class="ia-panel glass-panel">

          <textarea
            class="input-glass ia-textarea"
            rows="3"
            [(ngModel)]="question"
            placeholder="Ex : Quelles sont les consultations ?"
            (keydown.enter)="$event.preventDefault(); ask()"
          ></textarea>

          <button
            type="button"
            class="btn-primary ask-btn"
            (click)="ask()"
            [disabled]="loading() || !question.trim()"
          >
            @if (loading()) {
              <span class="spinner-dot-sm"></span>
              <span>Analyse...</span>
            } @else {
              <span>🩺 Interroger l'ontologie</span>
            }
          </button>

          <div class="suggestions-box">
            <span class="sugg-title">
              Suggestions médicales
            </span>

            <div class="sugg-pills">
              @for (p of prompts; track p) {
                <button
                  type="button"
                  class="sugg-pill"
                  (click)="ask(p)"
                >
                  {{ p }}
                </button>
              }
            </div>
          </div>

        </div>

        <!-- Zone des résultats -->
        <div class="ia-results-panel glass-panel">

          @if (loading()) {

            <div class="state-box">
              <span class="spinner-dot"></span>
              <p>
                Interrogation de l'ontologie médicale...
              </p>
            </div>

          } @else if (error()) {

            <div class="alert alert-error">
              ⚠️ {{ error() }}
            </div>

          } @else {

            @if (result(); as r) {

              <div class="result-details">

                <div class="response-header">
                  <span class="badge badge-emerald">
                    ✓ Réponse IA
                  </span>

                  <span class="res-count">
                    {{ r.count || 0 }} résultat(s)
                  </span>
                </div>

                <div class="ia-human-response">
                  <b>{{ r.intention }}</b>
                  —
                  {{ r.explication }}
                </div>

                <!-- Analyse NLP -->
                <app-nlp-analyse
                  [nlp]="r.nlp"
                ></app-nlp-analyse>

                <!-- Requête SPARQL -->
                <div class="sparql-preview-box">

                  <div class="sparql-code-bar">
                    <span class="sparql-code-tag">
                      SPARQL généré
                    </span>
                  </div>

                  <pre class="sparql-code"><code>{{ r.sparql }}</code></pre>

                </div>

                <!-- Tableau des résultats -->
                @if (r.donnees?.length) {

                  <div class="ia-data-table-wrap">

                    <h4>
                      Résultats extraits de l'ontologie :
                    </h4>

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
                            @for (c of columns(r.donnees); track c) {
                              <td>{{ row[c] ?? '—' }}</td>
                            }
                          </tr>
                        }
                      </tbody>

                    </table>

                  </div>

                } @else {

                  <p class="ia-empty-hint">
                    Aucun résultat enregistré pour cette question.
                  </p>

                }

              </div>

            } @else {

              <div class="state-box empty ia-empty-state">

                <span class="ia-empty-icon">
                  🩺
                </span>

                <p class="ia-empty-title">
                  Interrogez l'ontologie du Service médical
                </p>

                <p class="ia-empty-hint">
                  Consultations, opérations, ordonnances…
                </p>

              </div>

            }

          }

        </div>

      </div>

    </section>
  `,
  styles: [`
    :host {
      display: block;
    }

    .ia-layout {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
      align-items: start;
    }

    .ia-module-header {
      display: flex;
      gap: 14px;
      align-items: center;
      margin-bottom: 18px;
    }

    .ia-module-title {
      margin: 0 0 5px;
    }

    .ia-module-desc {
      margin: 0;
      color: var(--text-dim);
    }

    .ia-panel,
    .ia-results-panel {
      padding: 18px;
      min-width: 0;
    }

    .ia-textarea {
      width: 100%;
      box-sizing: border-box;
      resize: vertical;
    }

    .ask-btn {
      width: 100%;
      margin: 12px 0;
    }

    .suggestions-box {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .sugg-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .sugg-pill {
      padding: 7px 11px;
      border: 1px solid #bae6fd;
      border-radius: 18px;
      background: #f0f9ff;
      color: #075985;
      cursor: pointer;
    }

    .sugg-pill:hover {
      background: #0284c7;
      color: white;
    }

    .response-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }

    .sparql-code {
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .ia-data-table-wrap {
      overflow: auto;
    }

    .onto-table {
      width: 100%;
    }

    @media (max-width: 900px) {
      .ia-layout {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class MedicalIaComponent {

  private api = inject(MedicalApi);

  question = '';

  loading = signal(false);
  error = signal('');
  result = signal<any>(null);

  prompts = [
    'Quelles sont les consultations ?',
    'Afficher les opérations médicales.',
    'Quelles sont les ordonnances ?',
    'Combien de consultations existe-t-il ?',
    'Combien d’opérations sont enregistrées ?',
    'Liste des ordonnances.'
  ];

  private labels: Record<string, string> = {
    element: 'Élément',
    type: 'Type',
    nombre: 'Nombre',
    dateConsultation: 'Date de consultation',
    dateOrdonnance: 'Date ordonnance',
    tarif: 'Tarif (TND)',
    patient: 'Patient',
    medecin: 'Médecin'
  };

  ask(p?: string): void {

    const q = (p ?? this.question).trim();

    if (!q || this.loading()) {
      return;
    }

    this.question = q;
    this.loading.set(true);
    this.error.set('');
    this.result.set(null);

    this.api.ask(q).subscribe({

      next: (r: any) => {
        this.result.set(r);
        this.loading.set(false);
      },

      error: (e: any) => {
        this.error.set(
          e.error?.error || 'Erreur IA médicale.'
        );

        this.loading.set(false);
      }

    });
  }

  columns(rows: any[]): string[] {
    return rows?.length
      ? Object.keys(rows[0])
      : [];
  }

  label(k: string): string {
    return this.labels[k] || k;
  }

}
