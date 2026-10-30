import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

/**
 * Affiche les étapes du pipeline NLP du module Médicament :
 * tokens et lemmes (spaCy) -> entités -> texte délexicalisé -> intention (scikit-learn) -> paramètres.
 */
@Component({
  selector: 'app-nlp-analyse',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (nlp) {
      <div class="nlp-panel">
        <div class="nlp-head">
          <span class="nlp-title">Analyse NLP</span>
          <span class="nlp-sub">spaCy + scikit-learn, sans LLM</span>
        </div>

        <div class="nlp-row">
          <span class="nlp-label">1 · Tokens et lemmes</span>
          <div class="nlp-tokens">
            @for (t of tokens(); track $index) {
              <span class="nlp-token" [title]="'POS : ' + t.pos">
                <b>{{ t.texte }}</b><small>{{ t.lemme }} · {{ t.pos }}</small>
              </span>
            }
          </div>
        </div>

        <div class="nlp-row">
          <span class="nlp-label">2 · Entités de l'ontologie</span>
          <div class="nlp-chips">
            @for (e of nlp.entites; track $index) {
              <span class="nlp-chip" [ngClass]="'t-' + e.type" [title]="e.ids.join(', ')">
                {{ typeLabel(e.type) }} : <b>{{ e.texte }}</b> → {{ e.ids.join(', ') }}
                @if (e.corrige) { <em class="nlp-fix">faute corrigée</em> }
              </span>
            } @empty {
              <span class="nlp-chip t-none">Aucune entité</span>
            }
          </div>
        </div>

        <div class="nlp-row">
          <span class="nlp-label">3 · Texte délexicalisé</span>
          <code class="nlp-masked">{{ nlp.texte_masque }}</code>
        </div>

        <div class="nlp-row">
          <span class="nlp-label">4 · Intention</span>
          @for (i of nlp.intentions.slice(0, 3); track i.intention) {
            <div class="nlp-intent" [class.chosen]="i.intention === nlp.intention_retenue?.intention">
              <span class="nlp-intent-name">{{ i.intention }}{{ i.intention === nlp.intention_retenue?.intention ? ' ✓' : '' }}</span>
              <span class="nlp-bar"><span [style.width.%]="i.confiance * 100"></span></span>
              <span class="nlp-pct">{{ i.confiance * 100 | number:'1.0-0' }} %</span>
            </div>
          }
        </div>

        <div class="nlp-row">
          <span class="nlp-label">5 · Paramètres</span>
          <div class="nlp-chips">
            @for (s of slots(); track s) { <span class="nlp-chip t-slot">{{ s }}</span> }
            @empty { <span class="nlp-chip t-none">Aucun</span> }
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .nlp-panel { display: flex; flex-direction: column; gap: 12px; padding: 16px 18px; margin: 4px 0 18px;
      border-radius: var(--radius-md); background: #f8fafc; border: 1px solid #ddd6fe; }
    .nlp-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
    .nlp-title { font-weight: 700; font-size: 0.95rem; color: var(--accent-purple); }
    .nlp-sub { font-size: 0.78rem; color: var(--text-dim); }
    .nlp-row { display: flex; flex-direction: column; gap: 6px; }
    .nlp-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: var(--text-dim); }
    .nlp-tokens, .nlp-chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .nlp-token { display: inline-flex; flex-direction: column; align-items: center; padding: 3px 8px; line-height: 1.25;
      border-radius: var(--radius-sm); background: #fff; border: 1px solid var(--border-subtle); }
    .nlp-token b { font-size: 0.82rem; font-weight: 600; color: var(--text-main); }
    .nlp-token small { font-family: var(--font-mono); font-size: 0.64rem; color: var(--text-dim); }
    .nlp-chip { font-size: 0.78rem; padding: 3px 10px; border-radius: var(--radius-full); border: 1px solid; }
    .t-MEDICAMENT { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
    .t-MOLECULE { background: #ecfeff; color: #0e7490; border-color: #a5f3fc; }
    .t-MALADIE { background: #fff1f2; color: #be123c; border-color: #fecdd3; }
    .t-CONDITION { background: #f5f3ff; color: #6d28d9; border-color: #ddd6fe; }
    .t-EFFET, .t-FAMILLE_EFFET { background: #fff7ed; color: #c2410c; border-color: #fed7aa; }
    .t-CLASSE { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
    .t-slot { background: #f1f5f9; color: var(--text-muted); border-color: var(--border-subtle); }
    .t-none { background: #f8fafc; color: var(--text-dim); border-color: var(--border-subtle); }
    .nlp-fix { font-style: normal; font-size: 0.68rem; margin-left: 6px; padding: 0 6px; border-radius: 6px;
      background: #fef3c7; color: #b45309; }
    .nlp-masked { font-family: var(--font-mono); font-size: 0.8rem; color: var(--accent-purple); word-break: break-word; }
    .nlp-intent { display: grid; grid-template-columns: minmax(150px, 1fr) 2fr 48px; align-items: center; gap: 10px;
      font-family: var(--font-mono); font-size: 0.76rem; color: var(--text-dim); }
    .nlp-intent.chosen { color: var(--accent-purple); font-weight: 700; }
    .nlp-bar { height: 6px; border-radius: 999px; background: #e2e8f0; overflow: hidden; }
    .nlp-bar span { display: block; height: 100%; background: #94a3b8; border-radius: 999px; }
    .nlp-intent.chosen .nlp-bar span { background: var(--accent-purple); }
    .nlp-pct { text-align: right; }
    @media (max-width: 560px) { .nlp-intent { grid-template-columns: 1fr 1fr 40px; } }
  `]
})
export class NlpAnalyseComponent {
  @Input() nlp: any;

  private static TYPES: Record<string, string> = {
    MEDICAMENT: 'Médicament', MOLECULE: 'Molécule', MALADIE: 'Maladie', CONDITION: 'Condition',
    EFFET: 'Effet', FAMILLE_EFFET: "Famille d'effet", CLASSE: 'Classe',
    PATIENT: 'Patient', MEDECIN: 'Médecin', STATUT: 'Statut', MODE: 'Mode de paiement', ASSURANCE: 'Assurance'
  };

  typeLabel(t: string): string {
    return NlpAnalyseComponent.TYPES[t] || t;
  }

  tokens(): any[] {
    return (this.nlp?.tokens || []).filter((t: any) => t.pos !== 'PUNCT');
  }

  slots(): string[] {
    const s = this.nlp?.slots || {};
    const out: string[] = [];
    if (s.negation) out.push('Négation');
    if (s.grave) out.push('Gravité');
    if (s.superlatif) out.push('Superlatif');
    if (s.libre) out.push('Vente libre');
    if (s.ordre) out.push(s.ordre === 'ASC' ? 'Tri croissant' : 'Tri décroissant');
    return out;
  }
}
