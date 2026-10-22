/**
 * OntoSanté — Module Médicament (Front-end)
 * Architecture : Front-end -> IA Médicament -> SPARQL -> RDFLib -> ontologie_medicament.owl
 * Utilise API_BASE, escapeHtml et triggerArchitectureAnimation définis dans app.js.
 */

let allMedicamentsData = [];
let visMedicamentNetwork = null;

const MED_CLASS_STYLE = {
    Antalgique:        { icon: '💊', color: '#38bdf8', label: 'Antalgique' },
    AntiInflammatoire: { icon: '🔥', color: '#f59e0b', label: 'Anti-inflammatoire' },
    Antibiotique:      { icon: '🦠', color: '#a855f7', label: 'Antibiotique' },
    Antidiabetique:    { icon: '🩸', color: '#06b6d4', label: 'Antidiabétique' },
    Antihypertenseur:  { icon: '❤️', color: '#f43f5e', label: 'Antihypertenseur' },
    AntiUlcereux:      { icon: '🫃', color: '#10b981', label: 'Anti-ulcéreux' },
    Anticoagulant:     { icon: '🩹', color: '#ef4444', label: 'Anticoagulant' }
};
const MED_GRAVITE = {
    '1': { label: 'Légère',  color: '#22c55e' },
    '2': { label: 'Modérée', color: '#f59e0b' },
    '3': { label: 'Grave',   color: '#ef4444' }
};
const MED_RISQUE_COLOR = { Eleve: '#ef4444', Modere: '#f59e0b', Faible: '#22c55e' };
const MED_RISQUE_LABEL = { Eleve: 'Élevé', Modere: 'Modéré', Faible: 'Faible' };
const MED_GROUP_COLORS = {
    medicament: { bg: '#86efac', border: '#22c55e', shape: 'box' },
    molecule:   { bg: '#67e8f9', border: '#06b6d4', shape: 'ellipse' },
    effet:      { bg: '#fdba74', border: '#f97316', shape: 'box' },
    maladie:    { bg: '#fca5a5', border: '#ef4444', shape: 'box' },
    condition:  { bg: '#d8b4fe', border: '#a855f7', shape: 'box' },
    autre:      { bg: '#a5b4fc', border: '#6366f1', shape: 'box' }
};

document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('tab-medicaments')) return;

    loadMedicaments();

    // Filtres
    document.querySelectorAll('.med-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.med-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderMedicaments(btn.dataset.medfilter);
        });
    });

    // Formulaire IA
    document.getElementById('med-ia-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const q = document.getElementById('med-ia-input').value.trim();
        if (q) askIAMedicament(q);
    });

    // Exemples rapides
    document.querySelectorAll('.med-chip').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const q = btn.dataset.medq;
            document.getElementById('med-ia-input').value = q;
            askIAMedicament(q);
        });
    });

    // Copier SPARQL
    const copyBtn = document.getElementById('med-btn-copy-sparql');
    copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(document.getElementById('med-ia-sparql-code').textContent);
        copyBtn.textContent = 'Copié !';
        setTimeout(() => copyBtn.textContent = 'Copier', 2000);
    });

    // Graphe : créé à la première ouverture de l'onglet (un conteneur caché a une taille nulle)
    document.getElementById('btn-reset-graph-med').addEventListener('click', () => {
        if (visMedicamentNetwork) visMedicamentNetwork.fit();
    });
    const navBtn = document.querySelector('.nav-tab[data-tab="tab-medicaments"]');
    if (navBtn) {
        navBtn.addEventListener('click', () => {
            setTimeout(() => {
                if (!visMedicamentNetwork) setupMedicamentGraph();
                else { visMedicamentNetwork.redraw(); visMedicamentNetwork.fit(); }
            }, 150);
        });
    }
});

// ----------------------------------------------------------------------
// Fiches médicaments
// ----------------------------------------------------------------------
async function loadMedicaments() {
    const grid = document.getElementById('medicaments-grid');
    try {
        const res = await fetch(`${API_BASE}/api/medicaments`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        allMedicamentsData = await res.json();
        if (!allMedicamentsData.length) throw new Error('vide');
        document.getElementById('med-count-all').textContent = allMedicamentsData.length;
        renderMedicaments('ALL');
    } catch (err) {
        grid.innerHTML = `<div class="error-msg">⚠️ Module Médicament indisponible. Lancez d'abord <code>python medicament_owlready2.py</code> puis redémarrez le serveur.</div>`;
    }
}

function renderMedicaments(filter) {
    const grid = document.getElementById('medicaments-grid');
    let data = allMedicamentsData;
    if (filter === 'SANS_ORDONNANCE') data = data.filter(m => !m.ordonnance);
    else if (filter === 'MedicamentARisque') data = data.filter(m => m.inferences.includes('MedicamentARisque'));
    else if (filter !== 'ALL') data = data.filter(m => m.classes.includes(filter));

    grid.innerHTML = data.length
        ? data.map(buildMedicamentCard).join('')
        : '<p class="placeholder-text">Aucun médicament trouvé pour ce filtre.</p>';
}

function chips(items, fallback = 'Aucun') {
    return items.length ? items.join('') : `<span class="chip-tag empty">${fallback}</span>`;
}

function buildMedicamentCard(m) {
    const main = MED_CLASS_STYLE[m.classes[0]] || { icon: '💊', color: '#22c55e' };
    const mol = m.molecules[0] || {};
    const risque = m.inferences.includes('MedicamentARisque');

    const classes = m.classes.map(c => {
        const st = MED_CLASS_STYLE[c] || { color: '#94a3b8', label: c };
        return `<span class="type-badge" style="background:${st.color}22;color:${st.color};border:1px solid ${st.color}55">${st.label}</span>`;
    }).join('');

    const traite = m.maladiesTraitees.map(t => `<span class="chip-tag chip-green">${escapeHtml(t)}</span>`);

    const effets = m.effets.map(e => {
        const g = MED_GRAVITE[e.gravite] || MED_GRAVITE['1'];
        return `<span class="chip-tag" style="background:${g.color}1f;color:${g.color};border-color:${g.color}55"
                      title="${escapeHtml(e.type.replace('Effet', 'Effet '))} · ${escapeHtml(e.frequence)} · gravité ${g.label}">
                    ${e.gravite === '3' ? '● ' : ''}${escapeHtml(e.nom)}</span>`;
    });

    const ci = m.contreIndications.map(c =>
        `<span class="chip-tag chip-red" title="${c.source === 'maladie' ? 'Maladie (module Maladie)' : 'Condition clinique'}">
            ${c.source === 'maladie' ? '🦠 ' : ''}${escapeHtml(c.label)}</span>`);

    const inter = m.interactions.map(i => {
        const col = MED_RISQUE_COLOR[i.risque] || '#94a3b8';
        return `<span class="chip-tag" style="background:${col}1f;color:${col};border-color:${col}55"
                      title="${escapeHtml(i.description)}">↔ ${escapeHtml(i.avec)} · ${MED_RISQUE_LABEL[i.risque] || i.risque}</span>`;
    });

    const essais = m.essais.map(e =>
        `<div class="med-essai">
            <span class="med-essai-taux">${parseFloat(e.efficacite).toFixed(1)} %</span>
            <span>Phase ${e.phase} · ${e.patients} patients · ${e.annee}<br><small>${escapeHtml(e.objectif)}</small></span>
        </div>`).join('');

    return `
    <div class="person-card med-card" style="border-left-color:${main.color}">
        <div class="person-card-header">
            <div class="person-avatar" style="background:${main.color}22">${main.icon}</div>
            <div class="person-info">
                <h3>${escapeHtml(m.nom)} <span class="med-dosage">${escapeHtml(m.dosage)}</span></h3>
                <div class="person-types">
                    ${classes}
                    <span class="type-badge ${m.ordonnance ? 'med-badge-ordo' : 'med-badge-libre'}">${m.ordonnance ? '📝 Ordonnance' : '🔓 Libre'}</span>
                    ${risque ? '<span class="type-badge med-badge-risque" title="Inféré par HermiT : peut provoquer un effet grave">🧠 À risque</span>' : ''}
                </div>
            </div>
        </div>
        <div class="person-attrs">
            <div class="attr-row"><span class="attr-label">Molécule :</span><span class="attr-val">${escapeHtml(mol.nom || '-')} <small class="med-formule">${escapeHtml(mol.formule || '')}</small></span></div>
            <div class="attr-row"><span class="attr-label">Forme :</span><span class="attr-val">${escapeHtml(m.forme)} (${escapeHtml(m.voie)})</span></div>
            <div class="attr-row"><span class="attr-label">Code ATC :</span><span class="attr-val">${escapeHtml(m.codeATC)}</span></div>
            <div class="attr-row"><span class="attr-label">Prix :</span><span class="attr-val">${m.prix ? parseFloat(m.prix).toFixed(2) + ' TND' : '-'}</span></div>
            <div class="attr-row med-poso"><span class="attr-label">Posologie :</span><span class="attr-val">${escapeHtml(m.posologie)}</span></div>
        </div>
        <div class="med-section"><span class="med-section-title">🩺 Traite</span><div class="chips-row">${chips(traite)}</div></div>
        <div class="med-section"><span class="med-section-title">⚠️ Effets secondaires</span><div class="chips-row">${chips(effets)}</div></div>
        <div class="med-section"><span class="med-section-title">🚫 Contre-indications</span><div class="chips-row">${chips(ci, 'Aucune enregistrée')}</div></div>
        <div class="med-section"><span class="med-section-title">🔄 Interactions</span><div class="chips-row">${chips(inter, 'Aucune enregistrée')}</div></div>
        <div class="med-section"><span class="med-section-title">📊 Données cliniques</span>${essais || '<div class="chips-row"><span class="chip-tag empty">Aucun essai</span></div>'}</div>
    </div>`;
}

// ----------------------------------------------------------------------
// Graphe Vis.js
// ----------------------------------------------------------------------
async function setupMedicamentGraph() {
    try {
        const container = document.getElementById('network-graph-med');
        if (!container || !window.vis) return;
        const res = await fetch(`${API_BASE}/api/graph-medicament`);
        if (!res.ok) return;
        const graphData = await res.json();

        const nodes = new vis.DataSet(graphData.nodes.map(n => {
            const c = MED_GROUP_COLORS[n.group] || MED_GROUP_COLORS.autre;
            return {
                id: n.id, label: n.label, shape: c.shape, borderWidth: 2,
                color: { background: c.bg, border: c.border },
                font: { size: n.group === 'medicament' ? 15 : 12, color: '#0f172a', face: 'Outfit' }
            };
        }));
        const edges = new vis.DataSet(graphData.edges.map((e, i) => ({
            id: i, from: e.from, to: e.to, label: e.label,
            arrows: e.label === 'interagitAvec' ? 'to, from' : 'to',
            dashes: e.label === 'interagitAvec' || e.label.startsWith('estContreIndique'),
            font: { size: 9, color: '#94a3b8', face: 'JetBrains Mono', strokeWidth: 0 },
            color: { color: e.label.startsWith('estContreIndique') ? '#ef4444' : (e.label === 'interagitAvec' ? '#f59e0b' : '#475569') }
        })));

        visMedicamentNetwork = new vis.Network(container, { nodes, edges }, {
            physics: { stabilization: { iterations: 200 }, barnesHut: { gravitationalConstant: -4000, springLength: 140 } },
            interaction: { hover: true, zoomView: true },
            edges: { smooth: { type: 'continuous' } }
        });
    } catch (err) {
        console.warn('Graphe Médicament indisponible :', err);
    }
}

// ----------------------------------------------------------------------
// Assistant IA — Module Médicament
// ----------------------------------------------------------------------
async function askIAMedicament(question) {
    const statusEl = document.getElementById('med-response-status');
    const intentEl = document.getElementById('med-ia-intention');
    const explEl   = document.getElementById('med-ia-explanation');
    const sparqlEl = document.getElementById('med-ia-sparql-code');
    const tableEl  = document.getElementById('med-ia-table-container');
    const jsonEl   = document.getElementById('med-ia-json-raw');

    statusEl.textContent = 'IA & SPARQL en cours...';
    statusEl.className = 'status-pill status-processing';
    intentEl.textContent = 'Analyse de la question...';
    explEl.textContent = '';
    sparqlEl.textContent = '# Génération SPARQL en cours...';
    tableEl.innerHTML = '<div class="loader-container"><div class="spinner"></div><p>Interrogation de l\'ontologie...</p></div>';
    if (typeof triggerArchitectureAnimation === 'function') triggerArchitectureAnimation();

    try {
        const res = await fetch(`${API_BASE}/api/ia-medicament/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);

        const bindings = data.data?.results?.bindings || [];
        const vars = data.data?.head?.vars || [];

        intentEl.textContent = `Intention détectée : ${data.intention}`;
        explEl.textContent = data.explication || '';
        sparqlEl.textContent = data.sparql || '';
        jsonEl.textContent = JSON.stringify(data.data, null, 2);
        renderMedicamentIATable(vars, bindings, tableEl, data.data?.error);

        statusEl.textContent = `Terminé (${bindings.length} résultat${bindings.length > 1 ? 's' : ''})`;
        statusEl.className = 'status-pill status-ready';
    } catch (err) {
        statusEl.textContent = 'Erreur';
        statusEl.className = 'status-pill';
        intentEl.textContent = 'Erreur';
        explEl.textContent = err.message;
        tableEl.innerHTML = `<p class="placeholder-text" style="color:#ef4444">⚠️ ${escapeHtml(err.message)}</p>`;
    }
}

function renderMedicamentIATable(vars, bindings, container, error) {
    if (error) {
        container.innerHTML = `<p class="placeholder-text" style="color:#ef4444">⚠️ Erreur SPARQL : ${escapeHtml(error)}</p>`;
        return;
    }
    if (!bindings.length) {
        container.innerHTML = '<p class="placeholder-text">Aucun résultat : rien n\'est enregistré dans l\'ontologie pour cette question.</p>';
        return;
    }

    const LABELS = {
        medicament: 'Médicament', medicament1: 'Médicament 1', medicament2: 'Médicament 2',
        autreMedicament: 'Interagit avec', niveauRisque: 'Risque', description: 'Description',
        contreIndication: 'Contre-indication', type: 'Type', condition: 'Condition',
        effet: 'Effet secondaire', effetGrave: 'Effet grave', famille: 'Famille', frequence: 'Fréquence', gravite: 'Gravité',
        molecule: 'Molécule', formuleBrute: 'Formule brute', masseMolaire: 'Masse molaire (g/mol)',
        maladie: 'Maladie', codeCIM: 'Code CIM-10', classe: 'Classe', posologie: 'Posologie',
        dosage: 'Dosage', forme: 'Forme', prixTND: 'Prix (TND)', ordonnance: 'Ordonnance', codeATC: 'Code ATC',
        essai: 'Essai', phase: 'Phase', nombrePatients: 'Patients', tauxEfficacite: 'Efficacité (%)',
        annee: 'Année', objectif: 'Objectif', nombre: 'Nombre', propriete: 'Propriété', valeur: 'Valeur'
    };

    let html = '<table><thead><tr>';
    vars.forEach(v => { html += `<th>${LABELS[v] || v}</th>`; });
    html += '</tr></thead><tbody>';

    bindings.forEach(row => {
        html += '<tr>';
        vars.forEach(v => {
            const val = row[v]?.value ?? '';
            let display = escapeHtml(val.startsWith('http') ? val.split('#').pop() : val);
            if (v === 'gravite' && MED_GRAVITE[val]) {
                const g = MED_GRAVITE[val];
                display = `<span style="color:${g.color};font-weight:600">● ${g.label}</span>`;
            } else if (v === 'niveauRisque' && MED_RISQUE_COLOR[val]) {
                display = `<span style="color:${MED_RISQUE_COLOR[val]};font-weight:600">● ${MED_RISQUE_LABEL[val]}</span>`;
            } else if (v === 'ordonnance') {
                display = val === 'true' ? '📝 Oui' : '🔓 Non';
            } else if (v === 'prixTND' && val) {
                display = `${parseFloat(val).toFixed(2)}`;
            }
            html += `<td>${val === '' ? '<span style="color:var(--text-muted)">-</span>' : display}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}
