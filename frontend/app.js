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
            document.querySelectorAll('.viewer-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.vtab-pane').forEach(p => p.classList.remove('active'));

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
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const q = chip.dataset.q;
            iaInput.value = q;
            askIA(q);
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
