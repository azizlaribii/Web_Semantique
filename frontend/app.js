/**
 * OntoSanté - Logique Frontend
 * Architecture : Front-end -> IA -> Fuseki API -> Back-end RDFLib -> Protégé OWL
 */

const API_BASE = window.location.origin;

// Éléments du DOM
const navTabs = document.querySelectorAll('.nav-tab');
const tabPanes = document.querySelectorAll('.tab-pane');
const iaForm = document.getElementById('ia-form');
const iaInput = document.getElementById('ia-input');
const iaIntention = document.getElementById('ia-intention');
const iaExplanation = document.getElementById('ia-explanation');
const iaSparqlCode = document.getElementById('ia-sparql-code');
const iaTableContainer = document.getElementById('ia-table-container');
const iaJsonRaw = document.getElementById('ia-json-raw');
const responseStatus = document.getElementById('response-status');
const personsGrid = document.getElementById('persons-grid');
const countAll = document.getElementById('count-all');
const sparqlEditor = document.getElementById('sparql-editor');
const btnRunSparql = document.getElementById('btn-run-sparql');
const directSparqlTable = document.getElementById('direct-sparql-table');
const sparqlTiming = document.getElementById('sparql-timing');

let allPersonsData = [];
let visNetworkInstance = null;

// Initialisation au chargement
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initViewerTabs();
    initQuickPrompts();
    initSampleQueries();
    fetchSystemStatus();
    loadPersons();
    setupGraph();
    loadMaladies();
    setupMaladieGraph();

    // Filtres maladies
    document.querySelectorAll('.mal-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.mal-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderMaladies(btn.dataset.mfilter);
        });
    });

    document.getElementById('btn-reset-graph-mal').addEventListener('click', () => {
        if (visMaladieNetwork) visMaladieNetwork.fit();
    });

    // Formulaire IA Maladie
    const malIaForm = document.getElementById('mal-ia-form');
    if (malIaForm) {
        malIaForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const q = document.getElementById('mal-ia-input').value.trim();
            if (q) askIAMaladie(q);
        });
    }

    // Chips rapides Maladie
    document.querySelectorAll('.mal-chip').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const q = btn.dataset.mq;
            const input = document.getElementById('mal-ia-input');
            if (input && q) {
                input.value = q;
                askIAMaladie(q);
            }
        });
    });

    // Copier SPARQL Maladie
    const malCopyBtn = document.getElementById('mal-btn-copy-sparql');
    if (malCopyBtn) {
        malCopyBtn.addEventListener('click', () => {
            const code = document.getElementById('mal-ia-sparql-code').textContent;
            navigator.clipboard.writeText(code);
            malCopyBtn.textContent = 'Copié !';
            setTimeout(() => malCopyBtn.textContent = 'Copier', 2000);
        });
    }

    // Viewer tabs Maladie
    document.querySelectorAll('[data-vtab^="mal-"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.vtab;
            btn.closest('.results-viewer').querySelectorAll('.viewer-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            btn.closest('.results-viewer').querySelectorAll('.vtab-pane').forEach(p => p.classList.remove('active'));
            document.getElementById(target).classList.add('active');
        });
    });

    // Soumission du formulaire IA
    iaForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const q = iaInput.value.trim();
        if (q) askIA(q);
    });

    // Copier SPARQL
    document.getElementById('btn-copy-ia-sparql').addEventListener('click', () => {
        navigator.clipboard.writeText(iaSparqlCode.textContent);
        alert('Requête SPARQL copiée dans le presse-papier !');
    });

    // Exécuter SPARQL console
    btnRunSparql.addEventListener('click', () => {
        executeDirectSparql(sparqlEditor.value);
    });

    // Filtres des personnes
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderPersons(btn.dataset.filter);
        });
    });

    // Reset Graph
    document.getElementById('btn-reset-graph').addEventListener('click', () => {
        if (visNetworkInstance) visNetworkInstance.fit();
    });

    // Requête type par défaut dans l'éditeur SPARQL
    sparqlEditor.value = `PREFIX : <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?medecin ?nom ?age ?specialite ?tel WHERE {
    ?medecin rdf:type/rdfs:subClassOf* :Medecin .
    OPTIONAL { ?medecin :nom ?nom }
    OPTIONAL { ?medecin :age ?age }
    OPTIONAL { ?medecin :specialite ?specialite }
    OPTIONAL { ?medecin :telephone ?tel }
}`;
});

// ----------------------------------------------------------------------
// Gestion des Onglets
// ----------------------------------------------------------------------
function initTabs() {
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.dataset.tab;
            navTabs.forEach(t => t.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            tab.classList.add('active');
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add('active');

            if (targetId === 'tab-graph' && visNetworkInstance) {
                setTimeout(() => visNetworkInstance.fit(), 200);
            }
        });
    });
}

function initViewerTabs() {
    document.querySelectorAll('.viewer-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            // Limité au bloc de résultats courant (sinon les onglets des autres modules se désactivent)
            const viewer = tab.closest('.results-viewer') || document;
            viewer.querySelectorAll('.viewer-tab').forEach(t => t.classList.remove('active'));
            viewer.querySelectorAll('.vtab-pane').forEach(p => p.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(tab.dataset.vtab).classList.add('active');
        });
    });
}

// ----------------------------------------------------------------------
// Animation du Flux de l'Architecture (comme sur la slide)
// ----------------------------------------------------------------------
function triggerArchitectureAnimation() {
    const nodes = [
        document.getElementById('node-frontend'),
        document.getElementById('arrow-1'),
        document.getElementById('node-ia'),
        document.getElementById('arrow-2'),
        document.getElementById('node-fuseki'),
        document.getElementById('arrow-3'),
        document.getElementById('node-backend'),
        document.getElementById('arrow-4'),
        document.getElementById('node-protege')
    ];

    nodes.forEach((el, index) => {
        setTimeout(() => {
            el.classList.add('active', 'flow-highlight');
            setTimeout(() => el.classList.remove('flow-highlight'), 800);
        }, index * 180);
    });
}

// ----------------------------------------------------------------------
// 1. Assistant IA : Question Utilisateur -> SPARQL -> Fuseki -> Données
// ----------------------------------------------------------------------
async function askIA(question) {
    responseStatus.className = 'status-pill status-processing';
    responseStatus.textContent = 'IA & Fuseki en cours...';

    // Déclencher l'animation visuelle du pipeline de la slide
    triggerArchitectureAnimation();

    try {
        const res = await fetch(`${API_BASE}/api/ia/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const data = await res.json();

        if (data.error) {
            alert(`Erreur : ${data.error}`);
            responseStatus.className = 'status-pill';
            responseStatus.textContent = 'Erreur';
            return;
        }

        // 1. Intention et explication IA
        iaIntention.textContent = `Intention détectée : ${data.intention}`;
        iaExplanation.textContent = `${data.explanation} (${data.count} résultat(s) trouvés)`;

        // 2. Requête SPARQL générée
        iaSparqlCode.textContent = data.sparql_query;

        // 3. JSON Fuseki brut
        iaJsonRaw.textContent = JSON.stringify(data.data, null, 2);

        // 4. Affichage du tableau de résultats
        renderBindingsTable(data.data, iaTableContainer);

        responseStatus.className = 'status-pill status-ready';
        responseStatus.textContent = `Terminé (${data.count} résultats)`;
    } catch (err) {
        console.error(err);
        responseStatus.className = 'status-pill';
        responseStatus.textContent = 'Échec de connexion';
    }
}

function initQuickPrompts() {
    document.querySelectorAll('.chip:not(.mal-chip):not(.med-chip)').forEach(chip => {
        chip.addEventListener('click', (e) => {
            e.stopPropagation();
            const q = chip.dataset.q;
            if (q) {
                iaInput.value = q;
                askIA(q);
            }
        });
    });
}

// ----------------------------------------------------------------------
// 2. Rendu de tableau générique pour résultats SPARQL Fuseki
// ----------------------------------------------------------------------
function renderBindingsTable(fusekiData, container) {
    const vars = fusekiData.head ? fusekiData.head.vars : [];
    const bindings = fusekiData.results ? fusekiData.results.bindings : [];

    if (!bindings || bindings.length === 0) {
        container.innerHTML = '<p class="placeholder-text">Aucun résultat trouvé pour cette requête.</p>';
        return;
    }

    let html = '<table><thead><tr>';
    vars.forEach(v => {
        html += `<th>?${v}</th>`;
    });
    html += '</tr></thead><tbody>';

    bindings.forEach(row => {
        html += '<tr>';
        vars.forEach(v => {
            const cell = row[v];
            if (!cell) {
                html += '<td style="color:var(--text-muted)">-</td>';
            } else {
                let displayVal = cell.value;
                if (displayVal.includes('#')) {
                    displayVal = displayVal.split('#').pop();
                } else if (displayVal.startsWith('http')) {
                    displayVal = displayVal.split('/').pop();
                }
                html += `<td><strong>${escapeHtml(displayVal)}</strong></td>`;
            }
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ----------------------------------------------------------------------
// 3. Explorateur des Personnes (Médecins, Patients, Stagiaires)
// ----------------------------------------------------------------------
async function loadPersons() {
    try {
        const res = await fetch(`${API_BASE}/api/personnes`);
        allPersonsData = await res.json();
        countAll.textContent = allPersonsData.length;
        renderPersons('ALL');
    } catch (err) {
        console.error(err);
        personsGrid.innerHTML = '<p class="placeholder-text">Impossible de charger les personnes depuis l\'API.</p>';
    }
}

function renderPersons(filter) {
    let filtered = allPersonsData;
    if (filter !== 'ALL') {
        filtered = allPersonsData.filter(p => p.types.some(t => t.toLowerCase().includes(filter.toLowerCase())));
    }

    if (filtered.length === 0) {
        personsGrid.innerHTML = '<p class="placeholder-text">Aucun individu trouvé pour ce filtre.</p>';
        return;
    }

    let html = '';
    filtered.forEach(p => {
        const isMedecin = p.types.some(t => t.includes('Medecin'));
        const isPatient = p.types.some(t => t.includes('Patient'));
        const isStagiaire = p.types.some(t => t.includes('Stagiaire'));

        let avatar = '👤';
        let mainTypeClass = 'type-patient';
        if (isMedecin) { avatar = '🩺'; mainTypeClass = 'type-medecin'; }
        else if (isPatient) { avatar = '🩹'; mainTypeClass = 'type-patient'; }
        else if (isStagiaire) { avatar = '🎓'; mainTypeClass = 'type-stagiaire'; }

        html += `
        <div class="person-card">
            <div class="person-card-header">
                <div class="person-avatar">${avatar}</div>
                <div class="person-info">
                    <h3>${escapeHtml(p.nom || p.id)}</h3>
                    <div class="person-types">
                        ${p.types.map(t => `<span class="type-badge ${mainTypeClass}">${t}</span>`).join('')}
                    </div>
                </div>
            </div>
            <div class="person-attrs">
                <div class="attr-row"><span class="attr-label">Identifiant OWL :</span><span class="attr-val">${escapeHtml(p.id)}</span></div>
                ${p.age ? `<div class="attr-row"><span class="attr-label">Âge :</span><span class="attr-val">${p.age} ans</span></div>` : ''}
                ${p.cin ? `<div class="attr-row"><span class="attr-label">CIN :</span><span class="attr-val">${p.cin}</span></div>` : ''}
                ${p.telephone ? `<div class="attr-row"><span class="attr-label">Téléphone :</span><span class="attr-val">${p.telephone}</span></div>` : ''}
                ${p.specialite ? `<div class="attr-row"><span class="attr-label">Spécialité :</span><span class="attr-val">${p.specialite}</span></div>` : ''}
                ${p.service ? `<div class="attr-row"><span class="attr-label">Service :</span><span class="attr-val" style="color:var(--accent-cyan); font-weight:600;">🏥 ${escapeHtml(p.service.replace('Service_', ''))}</span></div>` : ''}
                ${p.numeroDossier ? `<div class="attr-row"><span class="attr-label">N° Dossier :</span><span class="attr-val">${p.numeroDossier}</span></div>` : ''}
                ${p.groupeSanguin ? `<div class="attr-row"><span class="attr-label">Groupe Sanguin :</span><span class="attr-val">${p.groupeSanguin}</span></div>` : ''}
                ${p.adresse ? `<div class="attr-row"><span class="attr-label">Adresse :</span><span class="attr-val">${p.adresse}</span></div>` : ''}
            </div>
        </div>
        `;
    });

    personsGrid.innerHTML = html;
}

// ----------------------------------------------------------------------
// 4. Console SPARQL / Fuseki
// ----------------------------------------------------------------------
async function executeDirectSparql(query) {
    const start = performance.now();
    try {
        const res = await fetch(`${API_BASE}/api/sparql`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        const duration = Math.round(performance.now() - start);
        sparqlTiming.textContent = `${duration} ms`;

        const data = await res.json();
        if (data.error) {
            directSparqlTable.innerHTML = `<p style="color:var(--accent-rose); padding:1.5rem;">Erreur : ${escapeHtml(data.error)}</p>`;
            return;
        }

        renderBindingsTable(data, directSparqlTable);
    } catch (err) {
        directSparqlTable.innerHTML = `<p style="color:var(--accent-rose); padding:1.5rem;">Erreur de connexion : ${err.message}</p>`;
    }
}

function initSampleQueries() {
    const samples = {
        'all-medecins': `PREFIX : <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?medecin ?nom ?specialite ?numeroOrdre ?tel WHERE {
    ?medecin rdf:type/rdfs:subClassOf* :Medecin .
    OPTIONAL { ?medecin :nom ?nom }
    OPTIONAL { ?medecin :specialite ?specialite }
    OPTIONAL { ?medecin :numeroOrdre ?numeroOrdre }
    OPTIONAL { ?medecin :telephone ?tel }
}`,
        'all-patients': `PREFIX : <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?patient ?nom ?age ?dossier ?groupeSanguin WHERE {
    ?patient rdf:type/rdfs:subClassOf* :Patient .
    OPTIONAL { ?patient :nom ?nom }
    OPTIONAL { ?patient :age ?age }
    OPTIONAL { ?patient :numeroDossier ?dossier }
    OPTIONAL { ?patient :groupeSanguin ?groupeSanguin }
}`,
        'soins': `PREFIX : <http://example.org/ontologie-medicale#>

SELECT ?medecin ?patient ?service WHERE {
    ?medecin :soigne ?patient .
    OPTIONAL { ?patient :estPrisEnChargePar ?service }
}`,
        'symptomes': `PREFIX : <http://example.org/ontologie-medicale#>

SELECT ?patient ?symptome WHERE {
    ?patient :presente ?symptome .
}`,
        'disjoint': `PREFIX : <http://example.org/ontologie-medicale#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?c1 ?c2 WHERE {
    ?c1 owl:disjointWith ?c2 .
}`
    };

    document.querySelectorAll('.btn-sample').forEach(btn => {
        btn.addEventListener('click', () => {
            const query = samples[btn.dataset.sample];
            if (query) {
                sparqlEditor.value = query;
                executeDirectSparql(query);
            }
        });
    });
}

// ----------------------------------------------------------------------
// 5. Graphe Sémantique Vis.js
// ----------------------------------------------------------------------
async function setupGraph() {
    try {
        const res = await fetch(`${API_BASE}/api/graph`);
        const graphData = await res.json();

        const container = document.getElementById('network-graph');
        const nodes = new vis.DataSet(graphData.nodes.map(n => {
            let color = '#38bdf8';
            let shape = 'dot';
            if (n.id.includes('Dr_')) color = '#38bdf8';
            else if (['Sami', 'Amina'].includes(n.id)) color = '#10b981';
            else if (n.id.includes('Stagiaire')) color = '#f59e0b';
            else if (n.id.includes('Service')) { color = '#a855f7'; shape = 'diamond'; }
            else if (n.id.includes('Fievre') || n.id.includes('Grippe')) { color = '#f43f5e'; shape = 'triangle'; }

            return {
                id: n.id,
                label: n.id,
                color: { background: color, border: '#ffffff' },
                shape: shape,
                font: { color: '#ffffff', face: 'Outfit' },
                size: 20
            };
        }));

        const edges = new vis.DataSet(graphData.edges.map(e => ({
            from: e.from,
            to: e.to,
            label: e.label,
            arrows: 'to',
            color: { color: '#64748b', highlight: '#38bdf8' },
            font: { color: '#94a3b8', size: 10, face: 'JetBrains Mono' }
        })));

        const data = { nodes, edges };
        const options = {
            physics: {
                stabilization: true,
                barnesHut: { gravitationalConstant: -3000, springLength: 120 }
            },
            interaction: { hover: true, zoomView: true }
        };

        visNetworkInstance = new vis.Network(container, data, options);
    } catch (err) {
        console.error('Erreur chargement graphe :', err);
    }
}

// ----------------------------------------------------------------------
// 6. Statut du système
// ----------------------------------------------------------------------
async function fetchSystemStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/summary`);
        const data = await res.json();
        if (data.triples_count) {
            document.getElementById('triples-count').textContent = `${data.triples_count} Triplets OWL`;
        }
    } catch (err) {
        console.warn('Statut indisponible :', err);
    }
}

// ======================================================================
// MODULE MALADIE
// ======================================================================
let allMaladiesData = [];
let visMaladieNetwork = null;

const GRAVITE_LABEL = { '1': 'Légère', '2': 'Modérée', '3': 'Grave' };
const GRAVITE_COLOR = { '1': '#22c55e', '2': '#f59e0b', '3': '#ef4444' };
const TYPE_ICON = {
    'Grippe': '🤧', 'Angine': '🦠', 'Diabete': '💉',
    'Hypertension': '❤️', 'UlcereGastrique': '🫀',
    'MaladieInfectieuse': '🦠', 'MaladieChronique': '📅', 'MaladieDigestive': '🫀'
};
const TYPE_PARENT = {
    'Grippe': 'MaladieInfectieuse', 'Angine': 'MaladieInfectieuse',
    'Diabete': 'MaladieChronique', 'Hypertension': 'MaladieChronique',
    'UlcereGastrique': 'MaladieDigestive'
};

async function loadMaladies() {
    try {
        const res = await fetch(`${API_BASE}/api/maladies`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        allMaladiesData = await res.json();
        document.getElementById('mal-count-all').textContent = allMaladiesData.length;
        renderMaladies('ALL');
    } catch (err) {
        document.getElementById('maladies-grid').innerHTML =
            `<div class="error-msg">⚠️ Module Maladie indisponible. Lancez d'abord <code>maladie_owlready2.py</code> puis redémarrez le serveur.</div>`;
    }
}

function getMainType(m) {
    const priority = ['Grippe','Angine','Diabete','Hypertension','UlcereGastrique',
                      'MaladieInfectieuse','MaladieChronique','MaladieDigestive'];
    for (const t of priority) if (m.types.includes(t)) return t;
    return m.types[0] || 'Maladie';
}

function renderMaladies(filter) {
    const grid = document.getElementById('maladies-grid');
    let data = allMaladiesData;
    if (filter !== 'ALL') {
        data = data.filter(m => m.types.includes(filter) || TYPE_PARENT[getMainType(m)] === filter);
    }
    if (!data.length) {
        grid.innerHTML = '<p class="placeholder-text">Aucune maladie trouvée.</p>';
        return;
    }
    grid.innerHTML = data.map(m => buildMaladieCard(m)).join('');
}

function buildMaladieCard(m) {
    const type = getMainType(m);
    const icon = TYPE_ICON[type] || '🏥';
    const grav = m.gravite || '1';
    const gravLabel = GRAVITE_LABEL[grav] || 'Inconnue';
    const gravColor = GRAVITE_COLOR[grav] || '#6b7280';
    const contagieux = m.contagieuse === 'true' ? '⚠️ Contagieuse' : '✅ Non contagieuse';
    const chronique = m.chronique === 'true' ? '🔄 Chronique' : '⏱️ Aigüe';
    const symptomes = m.symptomes.length
        ? m.symptomes.map(s => `<span class="chip-tag">${s}</span>`).join('')
        : '<span class="chip-tag empty">Aucun</span>';
    const medicaments = m.medicaments.length
        ? m.medicaments.map(med => `<span class="chip-tag chip-green">${med}</span>`).join('')
        : '<span class="chip-tag empty">Aucun</span>';

    return `
    <div class="person-card maladie-card" data-types="${m.types.join(' ')}">
        <div class="card-avatar" style="background: linear-gradient(135deg, ${gravColor}33, ${gravColor}66)">
            <span style="font-size:2rem">${icon}</span>
        </div>
        <div class="card-info">
            <div class="card-name">${m.nom || m.id}</div>
            <div class="card-role" style="color:${gravColor}">${type.replace('Maladie','Maladie ')}</div>
            <div class="card-badges">
                <span class="badge" style="background:${gravColor}22;color:${gravColor};border:1px solid ${gravColor}44">
                    ● Gravité : ${gravLabel}
                </span>
                ${m.codeCIM ? `<span class="badge badge-cyan">CIM-10: ${m.codeCIM}</span>` : ''}
            </div>
        </div>
        <div class="card-details">
            <div class="detail-row"><span class="detail-label">Statut</span><span>${contagieux} · ${chronique}</span></div>
            ${m.duree ? `<div class="detail-row"><span class="detail-label">Durée</span><span>${m.duree}</span></div>` : ''}
            <div class="detail-row"><span class="detail-label">🌡️ Symptômes</span><div class="chips-row">${symptomes}</div></div>
            <div class="detail-row"><span class="detail-label">💊 Traitements</span><div class="chips-row">${medicaments}</div></div>
        </div>
    </div>`;
}

async function setupMaladieGraph() {
    try {
        const res = await fetch(`${API_BASE}/api/graph-maladie`);
        if (!res.ok) return;
        const graphData = await res.json();
        const container = document.getElementById('network-graph-mal');
        if (!container || !window.vis) return;

        const NODE_COLORS = {
            maladie:    { bg: '#fca5a5', border: '#ef4444' },
            symptome:   { bg: '#fdba74', border: '#f97316' },
            medicament: { bg: '#86efac', border: '#22c55e' },
            default:    { bg: '#a5b4fc', border: '#6366f1' }
        };

        const mal_ids = new Set(allMaladiesData.map(m => m.id));
        const sym_kw = ['Fievre','Fatigue','Toux','Maux','Nausee','Douleur','Soif','Cephalee'];
        const med_kw = ['Paracetamol','Amoxicilline','Ibuprofene','Metformine','Amlodipine','Omeprazole'];

        const nodes = new vis.DataSet(graphData.nodes.map(n => {
            let color = NODE_COLORS.default;
            if (mal_ids.has(n.id)) color = NODE_COLORS.maladie;
            else if (sym_kw.some(k => n.id.includes(k))) color = NODE_COLORS.symptome;
            else if (med_kw.some(k => n.id.includes(k))) color = NODE_COLORS.medicament;
            return { id: n.id, label: n.label.replace(/_/g,' '), color: { background: color.bg, border: color.border }, font: { size: 13 }, shape: 'box', borderWidth: 2 };
        }));
        const edges = new vis.DataSet(graphData.edges.map((e, i) => ({
            id: i, from: e.from, to: e.to, label: e.label,
            arrows: 'to', font: { size: 10, color: '#94a3b8' },
            color: { color: '#475569' }
        })));


        visMaladieNetwork = new vis.Network(container, { nodes, edges }, {
            layout: { improvedLayout: true },
            physics: { stabilization: { iterations: 150 } },
            edges: { smooth: { type: 'cubicBezier' } }
        });
    } catch (err) {
        console.warn('Graphe Maladie indisponible :', err);
    }
}

// ======================================================================
// ASSISTANT IA — MODULE MALADIE
// ======================================================================
async function askIAMaladie(question) {
    const statusEl   = document.getElementById('mal-response-status');
    const intentEl   = document.getElementById('mal-ia-intention');
    const explEl     = document.getElementById('mal-ia-explanation');
    const sparqlEl   = document.getElementById('mal-ia-sparql-code');
    const tableEl    = document.getElementById('mal-ia-table-container');
    const jsonEl     = document.getElementById('mal-ia-json-raw');

    // Loading state
    statusEl.textContent = 'Traitement...';
    statusEl.className = 'status-pill status-loading';
    intentEl.textContent = 'Analyse de la question...';
    explEl.textContent   = '';
    sparqlEl.textContent = '# Génération SPARQL en cours...';
    tableEl.innerHTML    = '<div class="loader-container"><div class="spinner"></div><p>Interrogation de l\'ontologie...</p></div>';

    try {
        const res = await fetch(`${API_BASE}/api/ia-maladie/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // Mise à jour UI
        statusEl.textContent = 'Résultat reçu';
        statusEl.className   = 'status-pill status-ok';
        intentEl.textContent = data.intention || 'Analyse terminée';
        explEl.textContent   = data.explication || '';
        sparqlEl.textContent = data.sparql || '';

        // Données
        const bindings = data.data?.results?.bindings || [];
        const vars     = data.data?.head?.vars || [];

        jsonEl.textContent = JSON.stringify(data.data, null, 2);
        renderMaladieIATable(vars, bindings, tableEl);

    } catch (err) {
        statusEl.textContent = 'Erreur';
        statusEl.className   = 'status-pill status-error';
        intentEl.textContent = 'Erreur de connexion';
        explEl.textContent   = err.message;
        tableEl.innerHTML    = `<p class="placeholder-text" style="color:#ef4444">⚠️ ${err.message}</p>`;
    }
}

function renderMaladieIATable(vars, bindings, container) {
    if (!bindings.length) {
        container.innerHTML = '<p class="placeholder-text">Aucun résultat trouvé pour cette requête.</p>';
        return;
    }

    const LABEL_MAP = {
        maladie: 'Maladie', nom: 'Nom', codeCIM: 'Code CIM-10',
        gravite: 'Gravité', contagieuse: 'Contagieuse', chronique: 'Chronique',
        duree: 'Durée', symptome: 'Symptôme', medicament: 'Médicament',
        operation: 'Opération', medecin: 'Médecin', patient: 'Patient',
        ordonnance: 'Ordonnance', type: 'Type'
    };

    const GRAVITE_BADGE = { '1': { label: 'Légère', color: '#22c55e' },
                             '2': { label: 'Modérée', color: '#f59e0b' },
                             '3': { label: 'Grave',   color: '#ef4444' } };

    let html = '<table class="results-table"><thead><tr>';
    vars.forEach(v => { html += `<th>${LABEL_MAP[v] || v}</th>`; });
    html += '</tr></thead><tbody>';

    bindings.forEach(row => {
        html += '<tr>';
        vars.forEach(v => {
            const val = row[v]?.value ?? '';
            let display = val;
            // Formater gravité
            if (v === 'gravite' && GRAVITE_BADGE[val]) {
                const g = GRAVITE_BADGE[val];
                display = `<span style="color:${g.color};font-weight:600">● ${g.label}</span>`;
            }
            // Formater booléens
            else if (v === 'contagieuse' || v === 'chronique') {
                display = val === 'true'
                    ? '<span style="color:#f97316">⚠️ Oui</span>'
                    : '<span style="color:#22c55e">✅ Non</span>';
            }
            // Nettoyer les URIs
            else if (val.startsWith('http')) {
                display = val.split('#').pop();
            }
            html += `<td>${display}</td>`;
        });
        html += '</tr>';
    });

    html += `</tbody></table><p class="timing-badge" style="margin-top:8px">${bindings.length} résultat(s)</p>`;
    container.innerHTML = html;
}
