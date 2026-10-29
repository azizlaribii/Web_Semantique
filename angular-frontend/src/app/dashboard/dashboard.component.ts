import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../core/services/auth.service';
import { ApiService } from '../core/services/api.service';
import { Personne, User } from '../core/models/user.model';
import { NavbarComponent } from '../shared/navbar/navbar.component';
import { NlpAnalyseComponent } from './medicament/nlp-analyse.component';
import { MedicamentCrudComponent } from './medicament/medicament-crud.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, NavbarComponent, NlpAnalyseComponent, MedicamentCrudComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  auth = inject(AuthService);
  private api = inject(ApiService);

  currentUser = this.auth.currentUser;

  // Active tab
  activeTab = signal<'personnes' | 'ia-personnes' | 'ia-maladies' | 'ia-medicaments' | 'gestion-medicaments' | 'maladies' | 'sparql' | 'profil' | 'explorateur-ontologie'>('personnes');

  // ── EXPLORATEUR DYNAMIQUE ONTOLOGIE ─────────────────────
  ontologySchema = signal<any>(null);
  loadingOntologySchema = signal(false);
  ontologySearch = signal('');
  ontologyActiveSubTab = signal<'all' | 'individuals' | 'object_properties' | 'datatype_properties' | 'classes'>('all');
  selectedIndividualDetail = signal<any>(null);
  loadingIndividualDetail = signal(false);
  reloadMessage = signal('');
  isReloadingOntology = signal(false);

  filteredOntologyIndividuals = computed(() => {
    const s = this.ontologySchema();
    if (!s || !s.individuals) return [];
    const q = this.ontologySearch().toLowerCase().trim();
    if (!q) return s.individuals;
    return s.individuals.filter((i: any) =>
      (i.nom && i.nom.toLowerCase().includes(q)) ||
      (i.label && i.label.toLowerCase().includes(q)) ||
      (i.types && i.types.some((t: string) => t.toLowerCase().includes(q)))
    );
  });

  filteredOntologyObjProps = computed(() => {
    const s = this.ontologySchema();
    if (!s || !s.object_properties) return [];
    const q = this.ontologySearch().toLowerCase().trim();
    if (!q) return s.object_properties;
    return s.object_properties.filter((p: any) =>
      (p.nom && p.nom.toLowerCase().includes(q)) ||
      (p.label && p.label.toLowerCase().includes(q)) ||
      (p.domain && p.domain.toLowerCase().includes(q)) ||
      (p.range && p.range.toLowerCase().includes(q))
    );
  });

  filteredOntologyDataProps = computed(() => {
    const s = this.ontologySchema();
    if (!s || !s.datatype_properties) return [];
    const q = this.ontologySearch().toLowerCase().trim();
    if (!q) return s.datatype_properties;
    return s.datatype_properties.filter((p: any) =>
      (p.nom && p.nom.toLowerCase().includes(q)) ||
      (p.label && p.label.toLowerCase().includes(q)) ||
      (p.domain && p.domain.toLowerCase().includes(q)) ||
      (p.range && p.range.toLowerCase().includes(q))
    );
  });

  filteredOntologyClasses = computed(() => {
    const s = this.ontologySchema();
    if (!s || !s.classes) return [];
    const q = this.ontologySearch().toLowerCase().trim();
    if (!q) return s.classes;
    return s.classes.filter((c: any) =>
      (c.nom && c.nom.toLowerCase().includes(q)) ||
      (c.label && c.label.toLowerCase().includes(q)) ||
      (c.superClasses && c.superClasses.some((sc: string) => sc.toLowerCase().includes(q)))
    );
  });

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
    'Quelles sont les ordonnances ?',
    'Donne-moi l\'ordonnance de Sami',
    'Quelles sont les consultations ?',
    'Qui connaît le Dr Ahmed ?',
    'Qui connaît qui ?',
    'Donne-moi les sous-classes de Personne',
    'Donne-moi le médecin Aziz Laribi',
    'Quelles sont les sous-classes de Medecin ?',
    'Quelles sont les classes de l\'ontologie ?',
    'Qui a pour spécialité Cardiologie ?',
    'Quelles sont les Object Properties ?',
    'Quelles sont les Data Properties ?',
    'Quels sont tous les individus ?',
    'Donne-moi la liste des patients.',
    'Qui est Jean Testeur ?',
    'Donne-moi Jihene Ounis',
    'Quels sont les cardiologues ?',
    'Médecins avec plus de 40 ans.',
  ];

  // ── IA MALADIES ─────────────────────────────────────────────────────────
  iaMaladieQuestion = '';
  iaMaladieLoading = signal(false);
  iaMaladieResult = signal<any>(null);
  iaMaladieError = signal('');
  iaMaladiePrompts = [
    'Afficher les maladies de chaque patient.',
    'Afficher la maladie dont souffre Ahmed.',
    'Afficher les patients atteints de diabète.',
    'Afficher les médicaments associés à la grippe.',
    'Afficher le médicament associé à l’angine.',
    'Afficher les maladies chroniques présentes dans l’ontologie.',
    'Afficher les symptômes du diabète.',
    'Afficher les symptômes de l’asthme.',
    'Afficher les symptômes de l\'angine.',
    'Afficher les symptômes de la grippe.',
    'Afficher le symptôme commun à la grippe et à l\'angine.',
    'Afficher la maladie qui a le plus de symptômes.',
    'Afficher les médicaments associés à chaque maladie.',
    'Afficher les symptômes digestifs.',
    'Afficher les maladies infectieuses présentes dans l\'ontologie.',
    'Afficher les symptômes associés à chaque maladie infectieuse.',
    'Afficher les symptômes généraux.',
    'Afficher les médecins qui prennent en charge chaque maladie.',
  ];

  // ── IA MÉDICAMENTS ───────────────────────────────────────────────────────
  iaMedicamentQuestion = '';
  iaMedicamentLoading = signal(false);
  iaMedicamentResult = signal<any>(null);
  iaMedicamentError = signal('');
  iaMedicamentPrompts = [
    'Quels sont les effets secondaires du Brufen ?',
    'Ma femme est enceinte, peut-elle prendre du brufin ?',
    'Mon fils a la grippe, que lui donner ?',
    'Y a-t-il une interaction entre Coumadine et Aspegic ?',
    'Quels médicaments provoquent des saignements ?',
    'Médicaments sans contre-indication',
    'Quel est le médicament le plus efficace ?',
    'Quels médicaments contiennent de l\'ibuprofène ?',
    'Quels médicaments sont à risque ?',
    'Trier les médicaments du moins cher au plus cher',
  ];

  // Colonnes du tableau de résultats Médicaments : déduites des données renvoyées
  private static MED_COLS: Record<string, string> = {
    medicament: 'Médicament', medicament1: 'Médicament 1', medicament2: 'Médicament 2',
    autreMedicament: 'Interagit avec', niveauRisque: 'Risque', description: 'Description',
    contreIndication: 'Contre-indication', type: 'Type', condition: 'Condition',
    effet: 'Effet secondaire', effetGrave: 'Effet grave', famille: 'Famille', frequence: 'Fréquence',
    gravite: 'Gravité', molecule: 'Molécule', formuleBrute: 'Formule brute', masseMolaire: 'Masse molaire',
    maladie: 'Maladie', codeCIM: 'Code CIM-10', classe: 'Classe', posologie: 'Posologie', dosage: 'Dosage',
    forme: 'Forme', prixTND: 'Prix (TND)', ordonnance: 'Ordonnance', codeATC: 'Code ATC', essai: 'Essai',
    phase: 'Phase', nombrePatients: 'Patients', tauxEfficacite: 'Efficacité (%)', annee: 'Année',
    objectif: 'Objectif', nombre: 'Nombre', propriete: 'Propriété', valeur: 'Valeur'
  };

  medColumns(rows: any[]): string[] {
    const cols: string[] = [];
    (rows || []).forEach(r => Object.keys(r).forEach(k => { if (!cols.includes(k)) cols.push(k); }));
    return cols;
  }

  medColLabel(col: string): string {
    return DashboardComponent.MED_COLS[col] || col;
  }

  medCell(col: string, value: any): string {
    if (value === undefined || value === null || value === '') return '—';
    if (col === 'gravite') return ({ '1': 'Légère', '2': 'Modérée', '3': 'Grave' } as any)[value] || value;
    if (col === 'ordonnance') return value === 'true' ? 'Oui' : 'Non';
    if (col === 'niveauRisque') return ({ Eleve: 'Élevé', Modere: 'Modéré', Faible: 'Faible' } as any)[value] || value;
    return String(value);
  }

  onMedicamentsChanged(): void {
    this.loadCatalog();
  }

  // Colonnes dynamiques du tableau de résultats IA Personnes
  private static PERSONNE_COLS: Record<string, string> = {
    nom: 'Nom & Prénom',
    nomDisplay: 'Nom',
    nomClean: 'Nom',
    role: 'Rôle / Spécialité',
    specialite: 'Spécialité',
    age: 'Âge',
    cin: 'CIN',
    telephone: 'Téléphone',
    tel: 'Téléphone',
    email: 'Email',
    ordonnance: 'Ordonnance',
    medecin: 'Médecin Prescripteur',
    patient: 'Patient Destinataire',
    date: 'Date',
    medicaments: 'Médicaments Prescrits',
    consultation: 'Consultation',
    salle: 'Salle de Consultation',
    personne1: 'Personne 1',
    relation: 'Relation Symétrique',
    personne2: 'Personne 2',
    connaissance: 'En relation avec',
    individu: 'Individu',
    numeroOrdre: 'N° Ordre',
    numeroDossier: 'N° Dossier',
    groupeSanguin: 'Groupe Sanguin',
    valeur_ou_cible: 'Valeur / Entité reliée',
    propriete: 'Propriété / Relation',
    sujet: 'Sujet (Source)',
    nom_sujet: 'Sujet',
    objet: 'Objet (Cible)',
    type: 'Type / Classe',
    classe: 'Classe OWL',
    nb_proprietes: 'Nb Propriétés',
    nb_individus: 'Instances'
  };

  getPersonneColumns(rows: any[]): string[] {
    if (!rows || rows.length === 0) return [];
    const cols: string[] = [];
    rows.forEach(r => Object.keys(r).forEach(k => {
      if (!cols.includes(k) && !['uri', 'id', 'p1', 'p2'].includes(k)) {
        cols.push(k);
      }
    }));
    return cols;
  }

  getPersonneColTitle(col: string): string {
    return DashboardComponent.PERSONNE_COLS[col] || col.charAt(0).toUpperCase() + col.slice(1);
  }

  // SPARQL state
  sparqlCategory = signal<'maladie' | 'personne'>('maladie');
  sparqlViewMode = signal<'table' | 'json'>('table');

  sparqlTemplatesMaladie: { label: string; query: string }[] = [
    {
      label: 'Afficher les maladies de chaque patient.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?patient ?maladie WHERE {
  { ?pat med:souffreDe ?mal .
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie) }
  UNION
  { ?m mal:touche ?p .
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie) }
} ORDER BY ?patient ?maladie`
    },
    {
      label: 'Afficher la maladie dont souffre Ahmed.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?patient ?maladie WHERE {
  { ?pat med:souffreDe ?mal .
    FILTER(CONTAINS(LCASE(STR(?pat)), "ahmed"))
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie) }
  UNION
  { ?m mal:touche ?p .
    FILTER(CONTAINS(LCASE(STR(?p)), "ahmed"))
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie) }
} ORDER BY ?maladie`
    },
    {
      label: 'Afficher les patients atteints de diabète.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?patient ?maladie WHERE {
  { ?pat med:souffreDe ?mal .
    FILTER(CONTAINS(LCASE(STR(?mal)), "diabete"))
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie) }
  UNION
  { ?m mal:touche ?p .
    FILTER(CONTAINS(LCASE(STR(?p)), "diabete"))
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie) }
} ORDER BY ?patient`
    },
    {
      label: 'Afficher les médicaments associés à la grippe.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?medicament WHERE {
  { ?mal med:estTraiteePar ?med .
    FILTER(CONTAINS(LCASE(STR(?mal)), "grippe"))
    BIND("Grippe" AS ?maladie)
    BIND(STRAFTER(STR(?med), "#") AS ?medicament) }
  UNION
  { ?m mal:estTraiteePar ?med .
    FILTER(CONTAINS(LCASE(STR(?m)), "grippe"))
    BIND("Grippe" AS ?maladie)
    BIND(STRAFTER(STR(?med), "#") AS ?medicament) }
} ORDER BY ?medicament`
    },
    {
      label: 'Afficher le médicament associé à l’angine.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?medicament WHERE {
  { ?mal med:estTraiteePar ?med .
    FILTER(CONTAINS(LCASE(STR(?mal)), "angine"))
    BIND("Angine" AS ?maladie)
    BIND(STRAFTER(STR(?med), "#") AS ?medicament) }
  UNION
  { ?m mal:estTraiteePar ?med .
    FILTER(CONTAINS(LCASE(STR(?m)), "angine"))
    BIND("Angine" AS ?maladie)
    BIND(STRAFTER(STR(?med), "#") AS ?medicament) }
} ORDER BY ?medicament`
    },
    {
      label: 'Afficher les maladies chroniques présentes dans l’ontologie.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT DISTINCT ?maladie ?type ?nom ?dureeTraitement WHERE {
  { ?m rdf:type med:MaladieChronique .
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND("MaladieChronique" AS ?type)
    OPTIONAL { ?m rdfs:label ?nom }
    OPTIONAL { ?m med:dureeTraitement ?dureeTraitement } }
  UNION
  { ?m rdf:type/rdfs:subClassOf* mal:MaladieChronique .
    FILTER(?m != owl:NamedIndividual && ?m != mal:MaladieChronique)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND("MaladieChronique" AS ?type)
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:dureeTraitement ?dureeTraitement } }
} ORDER BY ?maladie`
    },
    {
      label: 'Afficher les symptômes du diabète.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?symptome WHERE {
  { ?m med:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "diabete"))
    BIND("Diabete" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
  UNION
  { ?m mal:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "diabete"))
    BIND("Diabete" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
} ORDER BY ?symptome`
    },
    {
      label: 'Afficher les symptômes de l’asthme.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?symptome WHERE {
  { ?m med:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "asthme"))
    BIND("Asthme" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
  UNION
  { ?m mal:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "asthme"))
    BIND("Asthme" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
} ORDER BY ?symptome`
    },
    {
      label: "Afficher les symptômes de l'angine.",
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?symptome WHERE {
  { ?m med:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "angine"))
    BIND("Angine" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
  UNION
  { ?m mal:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "angine"))
    BIND("Angine" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
} ORDER BY ?symptome`
    },
    {
      label: 'Afficher les symptômes de la grippe.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?symptome WHERE {
  { ?m med:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "grippe"))
    BIND("Grippe" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
  UNION
  { ?m mal:aPourSymptome ?s .
    FILTER(CONTAINS(LCASE(STR(?m)), "grippe"))
    BIND("Grippe" AS ?maladie)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
} ORDER BY ?symptome`
    },
    {
      label: "Afficher le symptôme commun à la grippe et à l'angine.",
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?symptomeCommun ?grippe ?angine WHERE {
  ?m1 med:aPourSymptome ?s .
  ?m2 med:aPourSymptome ?s .
  FILTER(CONTAINS(LCASE(STR(?m1)), "grippe") && CONTAINS(LCASE(STR(?m2)), "angine"))
  BIND(STRAFTER(STR(?s), "#") AS ?symptomeCommun)
  BIND(STRAFTER(STR(?m1), "#") AS ?grippe)
  BIND(STRAFTER(STR(?m2), "#") AS ?angine)
} ORDER BY ?symptomeCommun`
    },
    {
      label: 'Afficher la maladie qui a le plus de symptômes.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT ?maladie (COUNT(DISTINCT ?s) AS ?nb_symptomes) (GROUP_CONCAT(DISTINCT STRAFTER(STR(?s), "#"); separator=", ") AS ?symptomes) WHERE {
  { ?m med:aPourSymptome ?s . BIND(STRAFTER(STR(?m), "#") AS ?maladie) }
  UNION
  { ?m mal:aPourSymptome ?s . BIND(STRAFTER(STR(?m), "#") AS ?maladie) }
} GROUP BY ?maladie ORDER BY DESC(?nb_symptomes) LIMIT 1`
    },
    {
      label: 'Afficher les médicaments associés à chaque maladie.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?medicament WHERE {
  { ?mal med:estTraiteePar ?med .
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie)
    BIND(STRAFTER(STR(?med), "#") AS ?medicament) }
  UNION
  { ?m mal:estTraiteePar ?med .
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?med), "#") AS ?medicament) }
} ORDER BY ?maladie ?medicament`
    },
    {
      label: 'Afficher les symptômes digestifs.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT DISTINCT ?symptome ?typeSymptome WHERE {
  { ?s rdf:type med:SymptomeDigestif .
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
    BIND("SymptomeDigestif" AS ?typeSymptome) }
  UNION
  { ?s rdf:type/rdfs:subClassOf* mal:SymptomeDigestif .
    FILTER(?s != owl:NamedIndividual && ?s != mal:SymptomeDigestif)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome)
    BIND("SymptomeDigestif" AS ?typeSymptome) }
} ORDER BY ?symptome`
    },
    {
      label: "Afficher les maladies infectieuses présentes dans l'ontologie.",
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT DISTINCT ?maladieInfectieuse ?nom ?codeCIM WHERE {
  { ?m rdf:type med:MaladieInfectieuse .
    BIND(STRAFTER(STR(?m), "#") AS ?maladieInfectieuse)
    OPTIONAL { ?m rdfs:label ?nom }
    OPTIONAL { ?m med:codeCIM ?codeCIM } }
  UNION
  { ?m rdf:type/rdfs:subClassOf* mal:MaladieInfectieuse .
    FILTER(?m != owl:NamedIndividual && ?m != mal:MaladieInfectieuse)
    BIND(STRAFTER(STR(?m), "#") AS ?maladieInfectieuse)
    OPTIONAL { ?m mal:nom ?nom }
    OPTIONAL { ?m mal:codeCIM ?codeCIM } }
} ORDER BY ?maladieInfectieuse`
    },
    {
      label: 'Afficher les symptômes associés à chaque maladie infectieuse.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?maladieInfectieuse ?symptome WHERE {
  { ?m rdf:type med:MaladieInfectieuse .
    ?m med:aPourSymptome ?s .
    BIND(STRAFTER(STR(?m), "#") AS ?maladieInfectieuse)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
  UNION
  { ?m rdf:type/rdfs:subClassOf* mal:MaladieInfectieuse .
    ?m mal:aPourSymptome ?s .
    BIND(STRAFTER(STR(?m), "#") AS ?maladieInfectieuse)
    BIND(STRAFTER(STR(?s), "#") AS ?symptome) }
} ORDER BY ?maladieInfectieuse ?symptome`
    },
    {
      label: 'Afficher les symptômes généraux.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT DISTINCT ?symptomeGeneral ?nom WHERE {
  { ?s rdf:type med:SymptomeGeneral .
    BIND(STRAFTER(STR(?s), "#") AS ?symptomeGeneral)
    OPTIONAL { ?s rdfs:label ?nom } }
  UNION
  { ?s rdf:type/rdfs:subClassOf* mal:SymptomeGeneral .
    FILTER(?s != owl:NamedIndividual && ?s != mal:SymptomeGeneral)
    BIND(STRAFTER(STR(?s), "#") AS ?symptomeGeneral)
    OPTIONAL { ?s mal:nomSymptome ?nom } }
} ORDER BY ?symptomeGeneral`
    },
    {
      label: 'Afficher les médecins qui prennent en charge chaque maladie.',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?maladie ?medecin WHERE {
  { ?m mal:necessiteSuiviPar ?doc .
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?doc), "#") AS ?medecin) }
  UNION
  { ?m med:necessiteSuiviPar ?doc .
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?doc), "#") AS ?medecin) }
  UNION
  { ?doc med:diagnostique ?m .
    BIND(STRAFTER(STR(?m), "#") AS ?maladie)
    BIND(STRAFTER(STR(?doc), "#") AS ?medecin) }
} ORDER BY ?maladie ?medecin`
    }
  ];

  sparqlTemplatesPersonne: { label: string; query: string }[] = [
    {
      label: 'Tous les individus et leurs rôles',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?individu ?nom ?prenom ?role WHERE {
  ?individu rdf:type ?role ;
            med:nom ?nom ;
            med:prenom ?prenom .
  FILTER (?role != <http://www.w3.org/2002/07/owl#NamedIndividual>)
} LIMIT 25`
    },
    {
      label: 'Liste des médecins et leurs spécialités',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?medecin ?nom ?specialite WHERE {
  ?medecin rdf:type med:Medecin ;
           med:nom ?nom .
  OPTIONAL { ?medecin med:specialite ?specialite }
} ORDER BY ?nom`
    },
    {
      label: 'Liste des patients et leurs contacts',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?patient ?nom ?telephone ?cin WHERE {
  ?patient rdf:type med:Patient ;
           med:nom ?nom .
  OPTIONAL { ?patient med:telephone ?telephone }
  OPTIONAL { ?patient med:cin ?cin }
} ORDER BY ?nom`
    },
    {
      label: 'Médecins avec spécialité Cardiologie',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>

SELECT ?medecin ?nom ?specialite WHERE {
  ?medecin med:nom ?nom ;
           med:specialite ?specialite .
  FILTER (CONTAINS(LCASE(?specialite), "cardio"))
}`
    },
    {
      label: 'Hiérarchie des sous-classes de Personne',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?sousClasse ?parent WHERE {
  ?sousClasse rdfs:subClassOf ?parent .
  FILTER (STRSTARTS(STR(?parent), "http://example.org/ontologie-medicale#"))
} ORDER BY ?parent ?sousClasse`
    },
    {
      label: 'Fiche complète du patient Sami',
      query: `PREFIX med: <http://example.org/ontologie-medicale#>

SELECT ?prop ?valeur WHERE {
  med:Sami ?prop ?valeur .
}`
    }
  ];

  sparqlQuery = `PREFIX med: <http://example.org/ontologie-medicale#>
PREFIX mal: <http://example.org/ontologie-maladie#>

SELECT DISTINCT ?patient ?maladie WHERE {
  { ?pat med:souffreDe ?mal .
    BIND(STRAFTER(STR(?pat), "#") AS ?patient)
    BIND(STRAFTER(STR(?mal), "#") AS ?maladie) }
  UNION
  { ?m mal:touche ?p .
    BIND(STRAFTER(STR(?p), "#") AS ?patient)
    BIND(STRAFTER(STR(?m), "#") AS ?maladie) }
} ORDER BY ?patient ?maladie`;
  sparqlLoading = signal(false);
  sparqlResult = signal<any>(null);
  sparqlError = signal('');

  // Maladies & Médicaments catalog
  maladies = signal<any[]>([]);
  medicaments = signal<any[]>([]);
  loadingCatalog = signal(false);

  // Filtered Maladies
  selectedMaladieFilter = signal<string>('ALL');
  countAllMaladies = computed(() => this.maladies().length);
  filteredMaladies = computed(() => {
    const filter = this.selectedMaladieFilter();
    const list = this.maladies();
    if (filter === 'ALL') return list;
    return list.filter(m => {
      const typesStr = (m.types || []).join(' ');
      if (filter === 'MaladieInfectieuse') {
        return typesStr.includes('Infectieuse') || ['Grippe', 'Angine', 'Bronchite', 'Paludisme'].some(k => (m.id || '').includes(k));
      }
      if (filter === 'MaladieChronique') {
        return typesStr.includes('Chronique') || m.chronique === 'true' || ['Diabete', 'Hypertension', 'Asthme', 'Anemie', 'Arthrite', 'Migraine'].some(k => (m.id || '').includes(k));
      }
      if (filter === 'MaladieDigestive') {
        return typesStr.includes('Digestive') || typesStr.includes('Ulcere') || typesStr.includes('Gastrite') || ['Ulcere', 'Gastrite'].some(k => (m.id || '').includes(k));
      }
      return typesStr.includes(filter);
    });
  });

  setMaladieFilter(filter: string): void {
    this.selectedMaladieFilter.set(filter);
  }

  getMaladieIcon(m: any): string {
    const id = (m.id || '').toLowerCase();
    const types = (m.types || []).join(' ').toLowerCase();
    if (id.includes('grippe')) return '🤧';
    if (id.includes('angine')) return '🦠';
    if (id.includes('diabete')) return '💉';
    if (id.includes('hypertension')) return '❤️';
    if (id.includes('ulcere') || id.includes('gastrite')) return '🫀';
    if (id.includes('asthme') || id.includes('bronchite')) return '🫁';
    if (id.includes('paludisme')) return '🦟';
    if (id.includes('anemie')) return '🩸';
    if (id.includes('arthrite')) return '🦴';
    if (id.includes('migraine')) return '⚡';
    if (types.includes('infectieuse')) return '🦠';
    if (types.includes('chronique')) return '🩺';
    return '🏥';
  }

  getMaladieMainTypeLabel(m: any): string {
    const id = m.id || '';
    if (id.includes('Grippe')) return 'Grippe';
    if (id.includes('Angine')) return 'Angine';
    if (id.includes('Diabete')) return 'Diabete';
    if (id.includes('Hypertension')) return 'Hypertension';
    if (id.includes('Ulcere')) return 'Ulcere';
    if (id.includes('Asthme')) return 'Asthme';
    if (id.includes('Bronchite')) return 'Bronchite';
    if (id.includes('Paludisme')) return 'Paludisme';
    if (id.includes('Anemie')) return 'Anemie';
    if (id.includes('Gastrite')) return 'Gastrite';
    if (id.includes('Migraine')) return 'Migraine';
    if (id.includes('Arthrite')) return 'Arthrite';
    const cleanType = (m.types || [])[0] || 'Maladie';
    return cleanType.replace('Maladie', '');
  }

  getMaladieGraviteLabel(m: any): string {
    const g = String(m.gravite || '2');
    if (g === '1') return 'Légère';
    if (g === '3') return 'Grave';
    return 'Modérée';
  }

  getMaladieGraviteColor(m: any): string {
    const g = String(m.gravite || '2');
    if (g === '1') return '#10b981';
    if (g === '3') return '#ef4444';
    return '#f59e0b';
  }

  getMaladieAvatarBg(m: any): string {
    const id = (m.id || '').toLowerCase();
    if (id.includes('grippe')) return 'linear-gradient(135deg, rgba(245, 158, 11, 0.28), rgba(217, 119, 6, 0.5))';
    if (id.includes('angine')) return 'linear-gradient(135deg, rgba(16, 185, 129, 0.28), rgba(5, 150, 105, 0.5))';
    if (id.includes('diabete')) return 'linear-gradient(135deg, rgba(217, 119, 6, 0.28), rgba(180, 83, 9, 0.5))';
    if (id.includes('hypertension')) return 'linear-gradient(135deg, rgba(239, 68, 68, 0.28), rgba(220, 38, 38, 0.5))';
    if (id.includes('ulcere') || id.includes('gastrite')) return 'linear-gradient(135deg, rgba(139, 92, 246, 0.28), rgba(124, 58, 237, 0.5))';
    return 'linear-gradient(135deg, rgba(14, 165, 233, 0.28), rgba(2, 132, 199, 0.5))';
  }

  getMaladieCategory(m: any): string {
    const typesStr = (m.types || []).join(' ');
    if (typesStr.includes('Infectieuse')) return 'infectieuse';
    if (typesStr.includes('Chronique') || m.chronique === 'true') return 'chronique';
    if (typesStr.includes('Digestive')) return 'digestive';
    return 'general';
  }

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

  lastReloadTimestamp = 0;
  private pollSub: any = null;

  ngOnInit(): void {
    this.refreshAllData();

    // 1. Écouter les événements de rechargement/import
    this.api.ontologyChanged$.subscribe(() => {
      this.refreshAllData();
      this.showToast('✓ Ontologie synchronisée en direct.');
    });

    // 2. Détection automatique en direct (polling doux toutes les 3s)
    this.pollSub = setInterval(() => {
      this.api.getStatus().subscribe({
        next: (status) => {
          const ts = status?.dernier_rechargement?.timestamp || 0;
          if (this.lastReloadTimestamp !== 0 && ts > this.lastReloadTimestamp) {
            this.lastReloadTimestamp = ts;
            this.refreshAllData();
            this.showToast('🔄 Mise à jour détectée : ontologie synchronisée en temps réel.');
          } else if (this.lastReloadTimestamp === 0 && ts > 0) {
            this.lastReloadTimestamp = ts;
          }
        },
        error: () => {}
      });
    }, 3000);
  }

  ngOnDestroy(): void {
    if (this.pollSub) {
      clearInterval(this.pollSub);
    }
  }

  refreshAllData(): void {
    this.loadPersonnes();
    this.loadSummary();
    this.loadCatalog();
    this.loadDynamicEntities();
    this.loadOntologySchema();
  }

  setTab(tab: 'personnes' | 'ia-personnes' | 'ia-maladies' | 'ia-medicaments' | 'gestion-medicaments' | 'maladies' | 'sparql' | 'profil' | 'explorateur-ontologie'): void {
    this.activeTab.set(tab);
    if (tab === 'explorateur-ontologie' && !this.ontologySchema()) {
      this.loadOntologySchema();
    }
  }

  loadOntologySchema(): void {
    this.loadingOntologySchema.set(true);
    this.api.getOntologySchema().subscribe({
      next: (data) => {
        this.ontologySchema.set(data);
        this.loadingOntologySchema.set(false);
      },
      error: () => {
        this.loadingOntologySchema.set(false);
      }
    });
  }

  reloadOntology(): void {
    this.isReloadingOntology.set(true);
    this.reloadMessage.set('Rechargement du fichier ontologie_medicale (1).ttl et mise à jour...');
    this.api.reloadOntology().subscribe({
      next: (res) => {
        this.isReloadingOntology.set(false);
        this.reloadMessage.set(`✓ Ontologie synchronisée en direct ! (${res.total_triplets} triplets actifs)`);
        this.loadOntologySchema();
        this.loadPersonnes();
        this.loadCatalog();
        setTimeout(() => this.reloadMessage.set(''), 4500);
      },
      error: () => {
        this.isReloadingOntology.set(false);
        this.reloadMessage.set('Erreur lors du rechargement de l\'ontologie.');
      }
    });
  }

  viewIndividualDetail(nameOrUri: string): void {
    this.loadingIndividualDetail.set(true);
    this.api.getIndividualDetail(nameOrUri).subscribe({
      next: (detail) => {
        this.selectedIndividualDetail.set(detail);
        this.loadingIndividualDetail.set(false);
      },
      error: () => {
        this.loadingIndividualDetail.set(false);
      }
    });
  }

  closeIndividualDetail(): void {
    this.selectedIndividualDetail.set(null);
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

  // ── Helpers pour affichage dynamique des tableaux Maladie ────────────────
  getMaladieColumns(donnees: any[]): string[] {
    if (!donnees || donnees.length === 0) return [];
    const first = donnees[0];
    const order = [
      'patient', 'maladie', 'maladieInfectieuse', 'symptome', 'symptomeCommun',
      'symptomeGeneral', 'typeSymptome', 'medicament', 'medecin', 'grippe', 'angine',
      'nb_symptomes', 'symptomes', 'nom', 'nomMaladie', 'nomMedicament',
      'codeCIM', 'type', 'gravite', 'contagieuse', 'dureeTraitement', 'description'
    ];
    let keys = Object.keys(first);
    if (first.maladie && first.nom && first.nom === first.maladie) {
      keys = keys.filter(k => k !== 'nom');
    }
    return keys.sort((a, b) => {
      const idxA = order.indexOf(a);
      const idxB = order.indexOf(b);
      if (idxA !== -1 && idxB !== -1) return idxA - idxB;
      if (idxA !== -1) return -1;
      if (idxB !== -1) return 1;
      return a.localeCompare(b);
    });
  }

  getColTitle(key: string): string {
    const map: Record<string, string> = {
      patient: 'Patient',
      maladie: 'Maladie',
      maladieInfectieuse: 'Maladie Infectieuse',
      medecin: 'Médecin',
      medicament: 'Médicament',
      symptome: 'Symptôme',
      symptomeCommun: 'Symptôme Commun',
      symptomeGeneral: 'Symptôme Général',
      typeSymptome: 'Type de Symptôme',
      grippe: 'Grippe',
      angine: 'Angine',
      nb_symptomes: 'Nombre de symptômes',
      symptomes: 'Noms des symptômes',
      nom: 'Nom',
      nomMaladie: 'Nom Maladie',
      nomMedicament: 'Nom Médicament',
      codeCIM: 'Code CIM',
      gravite: 'Gravité',
      contagieuse: 'Contagieuse',
      dureeTraitement: 'Durée Traitement',
      type: 'Type / Catégorie',
      description: 'Description'
    };
    return map[key] || key.charAt(0).toUpperCase() + key.slice(1);
  }

  // ── Helpers pour la Console SPARQL Endpoint ─────────────────────────────
  loadSparqlTemplate(template: { label: string; query: string }): void {
    this.sparqlQuery = template.query;
    this.onExecuteSparql();
  }

  getSparqlBindings(): any[] {
    return this.sparqlResult()?.results?.bindings || [];
  }

  getSparqlVars(): string[] {
    return this.sparqlResult()?.head?.vars || [];
  }

  cleanSparqlVal(entry: any): string {
    if (!entry) return '—';
    const val = String(entry.value || '');
    if (val.includes('#')) return val.split('#').pop() || val;
    if (val.includes('/') && val.startsWith('http')) return val.split('/').pop() || val;
    return val;
  }

  getColBadgeClass(key: string): string {
    const k = key.toLowerCase();
    if (k.includes('patient')) return 'badge-emerald';
    if (k.includes('medecin') || k.includes('docteur')) return 'badge-cyan';
    if (k.includes('symptome')) return 'badge-rose';
    if (k.includes('medicament') || k.includes('traitement')) return 'badge-purple';
    if (k.includes('maladie')) return 'badge-amber';
    if (k.includes('nb') || k.includes('count')) return 'badge-cyan';
    return 'badge-dim';
  }

  // ── CRUD Ontologie Interactif (Modifier, Supprimer, + Ajouter) ───────────
  dynamicEntities = signal<{
    patients: string[];
    maladies: string[];
    symptomes: string[];
    medicaments: string[];
    medecins: string[];
    types_maladie: string[];
  }>({
    patients: [],
    maladies: [],
    symptomes: [],
    medicaments: [],
    medecins: [],
    types_maladie: []
  });

  // Modal Modifier
  editModalOpen = signal(false);
  editingRow = signal<any>(null);
  editFormData: Record<string, string> = {};
  editLoading = signal(false);
  editError = signal('');

  // Modal Supprimer
  deleteModalOpen = signal(false);
  deletingRow = signal<any>(null);
  deleteLoading = signal(false);
  deleteError = signal('');

  // Modal + Ajouter
  addModalOpen = signal(false);
  addFormData: Record<string, string> = {};
  addLoading = signal(false);
  addError = signal('');
  customAddConfig: any = null;

  // Toast
  toastMessage = signal('');
  toastType = signal<'success' | 'error'>('success');

  showToast(msg: string, type: 'success' | 'error' = 'success'): void {
    this.toastMessage.set(msg);
    this.toastType.set(type);
    setTimeout(() => {
      if (this.toastMessage() === msg) {
        this.toastMessage.set('');
      }
    }, 4500);
  }

  loadDynamicEntities(): void {
    this.api.getDynamicEntities().subscribe({
      next: (data) => {
        if (data) this.dynamicEntities.set(data);
      },
      error: () => {}
    });
  }

  getAddButtonConfig(): { label: string; type: string; title: string; fields: string[]; prefill: Record<string, string>; allowNew: Record<string, boolean>; hidden: boolean } {
    if (this.customAddConfig) {
      return this.customAddConfig;
    }
    const q = (this.iaMaladieQuestion || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const noBtn = { label: '', type: '', title: '', fields: [], prefill: {}, allowNew: {}, hidden: true };

    // ── Q1: Afficher les maladies de chaque patient → + Ajouter une relation
    if (q.includes('maladies de chaque patient') || (q.includes('maladie') && q.includes('chaque patient'))) {
      return {
        label: '+ Ajouter une relation',
        type: 'relation_patient_maladie',
        title: 'Ajouter une relation Patient → Maladie',
        fields: ['patient', 'maladie'],
        prefill: {},
        allowNew: { maladie: true },
        hidden: false
      };
    }

    // ── Q2: Afficher la maladie dont souffre Ahmed → + Ajouter une maladie à Ahmed
    if (q.includes('souffre ahmed') || (q.includes('maladie') && q.includes('ahmed'))) {
      return {
        label: '+ Ajouter une maladie à Ahmed',
        type: 'relation_patient_maladie',
        title: 'Ajouter une maladie au patient Ahmed',
        fields: ['patient', 'maladie'],
        prefill: { patient: 'Patient_Ahmed' },
        allowNew: { maladie: true },
        hidden: false
      };
    }

    // ── Q3: Afficher les patients atteints de diabète → + Ajouter un patient atteint de diabète
    if (q.includes('patient') && q.includes('diabete') && q.includes('atteint')) {
      return {
        label: '+ Ajouter un patient atteint de diabète',
        type: 'relation_patient_maladie',
        title: 'Associer un patient au Diabète',
        fields: ['maladie', 'patient'],
        prefill: { maladie: 'Diabete' },
        allowNew: {},
        hidden: false
      };
    }

    // ── Q4: Afficher les médicaments associés à la grippe → + Ajouter un médicament à la grippe
    if (q.includes('medicament') && q.includes('grippe')) {
      return {
        label: '+ Ajouter un médicament à la grippe',
        type: 'relation_maladie_medicament',
        title: 'Associer un médicament à la Grippe',
        fields: ['maladie', 'medicament'],
        prefill: { maladie: 'Grippe' },
        allowNew: { medicament: true },
        hidden: false
      };
    }

    // ── Q5: Afficher le médicament associé à l'angine → + Ajouter un médicament à l'angine
    if (q.includes('medicament') && q.includes('angine')) {
      return {
        label: '+ Ajouter un médicament à l\'angine',
        type: 'relation_maladie_medicament',
        title: 'Associer un médicament à l\'Angine',
        fields: ['maladie', 'medicament'],
        prefill: { maladie: 'Angine' },
        allowNew: { medicament: true },
        hidden: false
      };
    }

    // ── Q6: Afficher les maladies chroniques → + Ajouter une maladie chronique
    if (q.includes('chronique') && q.includes('maladie')) {
      return {
        label: '+ Ajouter une maladie chronique',
        type: 'entity_maladie',
        title: 'Créer une nouvelle maladie chronique',
        fields: ['nom', 'type', 'gravite'],
        prefill: { type: 'MaladieChronique' },
        allowNew: {},
        hidden: false
      };
    }

    // ── Q11: Symptôme commun à la grippe et à l'angine → + Ajouter un symptôme commun
    // (MUST be before Q9/Q10 because it also contains 'angine' and 'grippe')
    if (q.includes('commun') && q.includes('grippe') && q.includes('angine')) {
      return {
        label: '+ Ajouter un symptôme commun',
        type: 'symptome_commun',
        title: 'Ajouter un symptôme commun à la Grippe et à l\'Angine',
        fields: ['symptome'],
        prefill: { maladie1: 'Grippe', maladie2: 'Angine' },
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q12: Maladie qui a le plus de symptômes → + Ajouter un symptôme à une maladie
    // (MUST be before Q7-Q10 because 'plus de symptome' is more specific)
    if (q.includes('plus de symptome')) {
      return {
        label: '+ Ajouter un symptôme à une maladie',
        type: 'relation_maladie_symptome',
        title: 'Associer un symptôme à une maladie',
        fields: ['maladie', 'symptome'],
        prefill: {},
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q7: Afficher les symptômes du diabète → + Ajouter un symptôme au diabète
    if (q.includes('symptome') && q.includes('diabete')) {
      return {
        label: '+ Ajouter un symptôme au diabète',
        type: 'relation_maladie_symptome',
        title: 'Associer un symptôme au Diabète',
        fields: ['maladie', 'symptome'],
        prefill: { maladie: 'Diabete' },
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q8: Afficher les symptômes de l'asthme → + Ajouter un symptôme à l'asthme
    if (q.includes('symptome') && q.includes('asthme')) {
      return {
        label: '+ Ajouter un symptôme à l\'asthme',
        type: 'relation_maladie_symptome',
        title: 'Associer un symptôme à l\'Asthme',
        fields: ['maladie', 'symptome'],
        prefill: { maladie: 'Asthme' },
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q9: Afficher les symptômes de l'angine → + Ajouter un symptôme à l'angine
    if (q.includes('symptome') && q.includes('angine')) {
      return {
        label: '+ Ajouter un symptôme à l\'angine',
        type: 'relation_maladie_symptome',
        title: 'Associer un symptôme à l\'Angine',
        fields: ['maladie', 'symptome'],
        prefill: { maladie: 'Angine' },
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q10: Afficher les symptômes de la grippe → + Ajouter un symptôme à la grippe
    if (q.includes('symptome') && q.includes('grippe')) {
      return {
        label: '+ Ajouter un symptôme à la grippe',
        type: 'relation_maladie_symptome',
        title: 'Associer un symptôme à la Grippe',
        fields: ['maladie', 'symptome'],
        prefill: { maladie: 'Grippe' },
        allowNew: { symptome: true },
        hidden: false
      };
    }


    // ── Q13: Afficher les médicaments associés à chaque maladie → + Ajouter un médicament
    if (q.includes('medicament') && (q.includes('chaque maladie') || q.includes('chaque'))) {
      return {
        label: '+ Ajouter un médicament',
        type: 'relation_maladie_medicament',
        title: 'Associer un médicament à une maladie',
        fields: ['maladie', 'medicament'],
        prefill: {},
        allowNew: { medicament: true },
        hidden: false
      };
    }

    // ── Q14: Afficher les symptômes digestifs → + Ajouter un symptôme digestif
    if (q.includes('symptome') && q.includes('digestif')) {
      return {
        label: '+ Ajouter un symptôme digestif',
        type: 'entity_symptome',
        title: 'Créer un nouveau symptôme digestif',
        fields: ['symptome', 'type_symptome'],
        prefill: { type_symptome: 'SymptomeDigestif' },
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q15: Afficher les maladies infectieuses → + Ajouter une maladie infectieuse
    if (q.includes('infectieuse') && q.includes('maladie') && !q.includes('symptome')) {
      return {
        label: '+ Ajouter une maladie infectieuse',
        type: 'entity_maladie',
        title: 'Créer une nouvelle maladie infectieuse',
        fields: ['nom', 'type', 'gravite'],
        prefill: { type: 'MaladieInfectieuse' },
        allowNew: {},
        hidden: false
      };
    }

    // ── Q16: Afficher les symptômes associés à chaque maladie infectieuse → + Ajouter un symptôme
    if (q.includes('symptome') && q.includes('infectieuse')) {
      return {
        label: '+ Ajouter un symptôme',
        type: 'relation_maladie_symptome',
        title: 'Associer un symptôme à une maladie infectieuse',
        fields: ['maladie', 'symptome'],
        prefill: {},
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q17: Afficher les symptômes généraux → + Ajouter un symptôme général
    if (q.includes('symptome') && (q.includes('general') || q.includes('generaux'))) {
      return {
        label: '+ Ajouter un symptôme général',
        type: 'entity_symptome',
        title: 'Créer un nouveau symptôme général',
        fields: ['symptome', 'type_symptome'],
        prefill: { type_symptome: 'SymptomeGeneral' },
        allowNew: { symptome: true },
        hidden: false
      };
    }

    // ── Q18: Afficher les médecins qui prennent en charge chaque maladie → + Ajouter une prise en charge
    if (q.includes('medecin') || q.includes('charge') || q.includes('diagnostique')) {
      return {
        label: '+ Ajouter une prise en charge',
        type: 'relation_medecin_maladie',
        title: 'Associer un médecin à une maladie',
        fields: ['maladie', 'medecin'],
        prefill: {},
        allowNew: { maladie: true },
        hidden: false
      };
    }

    // ── Fallback : Relation Patient-Maladie
    return {
      label: '+ Ajouter une relation',
      type: 'relation_patient_maladie',
      title: 'Ajouter une relation Patient → Maladie',
      fields: ['patient', 'maladie'],
      prefill: {},
      allowNew: { maladie: true },
      hidden: false
    };
  }

  openEditModal(row: any): void {
    this.editingRow.set(row);
    this.editFormData = { ...row };
    this.editError.set('');
    this.editModalOpen.set(true);
  }

  closeEditModal(): void {
    this.editModalOpen.set(false);
    this.editingRow.set(null);
  }

  saveEditModal(): void {
    const oldItem = this.editingRow();
    if (!oldItem) return;
    this.editLoading.set(true);
    this.editError.set('');

    this.api.updateOntologyRow(oldItem, this.editFormData).subscribe({
      next: (res) => {
        this.editLoading.set(false);
        this.closeEditModal();
        this.showToast('✓ Modification enregistrée avec succès dans l\'ontologie.');
        const curRes = this.iaMaladieResult();
        if (curRes?.donnees) {
          const idx = curRes.donnees.indexOf(oldItem);
          if (idx !== -1) {
            curRes.donnees[idx] = { ...oldItem, ...this.editFormData };
            this.iaMaladieResult.set({ ...curRes });
          }
        }
        this.loadCatalog();
        this.loadDynamicEntities();
      },
      error: (err) => {
        this.editLoading.set(false);
        this.editError.set(err.error?.error || 'Erreur lors de la modification.');
      }
    });
  }

  openDeleteModal(row: any): void {
    this.deletingRow.set(row);
    this.deleteError.set('');
    this.deleteModalOpen.set(true);
  }

  closeDeleteModal(): void {
    this.deleteModalOpen.set(false);
    this.deletingRow.set(null);
  }

  confirmDeleteModal(): void {
    const item = this.deletingRow();
    if (!item) return;
    this.deleteLoading.set(true);
    this.deleteError.set('');

    this.api.deleteOntologyRow(item).subscribe({
      next: (res) => {
        this.deleteLoading.set(false);
        this.closeDeleteModal();
        this.showToast('✓ Élément supprimé avec succès de l\'ontologie.');
        const curRes = this.iaMaladieResult();
        if (curRes?.donnees) {
          curRes.donnees = curRes.donnees.filter((d: any) => d !== item);
          curRes.count = Math.max(0, (curRes.count || 1) - 1);
          this.iaMaladieResult.set({ ...curRes });
        }
        const targetId = item.id || item.maladie || item.maladieInfectieuse || item.nom;
        if (targetId) {
          this.maladies.update(list => list.filter(m => m.id !== targetId && m.nom !== targetId));
        }
        this.loadCatalog();
        this.loadDynamicEntities();
      },
      error: (err) => {
        this.deleteLoading.set(false);
        this.deleteError.set(err.error?.error || 'Erreur lors de la suppression.');
      }
    });
  }

  openAddModal(): void {
    this.customAddConfig = null;
    const config = this.getAddButtonConfig();
    if (config.hidden) return;
    this.addFormData = {};

    // Apply pre-fills from config
    for (const [key, value] of Object.entries(config.prefill)) {
      this.addFormData[key] = value;
    }

    // Set defaults for non-prefilled fields
    for (const f of config.fields) {
      if (this.addFormData[f]) continue; // already prefilled

      if (f === 'patient') {
        this.addFormData[f] = this.dynamicEntities().patients[0] || 'Patient_Ahmed';
      } else if (f === 'maladie') {
        this.addFormData[f] = this.dynamicEntities().maladies[0] || 'Grippe';
      } else if (f === 'symptome') {
        this.addFormData[f] = this.dynamicEntities().symptomes[0] || '';
      } else if (f === 'medicament') {
        this.addFormData[f] = this.dynamicEntities().medicaments[0] || '';
      } else if (f === 'medecin') {
        this.addFormData[f] = this.dynamicEntities().medecins[0] || '';
      } else if (f === 'type') {
        this.addFormData[f] = config.prefill['type'] || 'MaladieInfectieuse';
      } else if (f === 'type_symptome') {
        this.addFormData[f] = config.prefill['type_symptome'] || 'SymptomeGeneral';
      } else if (f === 'gravite') {
        this.addFormData[f] = '2';
      } else if (f === 'nom') {
        this.addFormData[f] = '';
      }
    }

    this.addError.set('');
    this.addModalOpen.set(true);
  }

  openAddMaladieModal(): void {
    const filter = this.selectedMaladieFilter();
    const defaultType = (filter && filter !== 'ALL') ? filter : 'MaladieInfectieuse';
    this.customAddConfig = {
      label: '+ Ajouter une maladie',
      type: 'entity_maladie',
      title: 'Créer une nouvelle maladie dans l\'ontologie',
      fields: ['nom', 'type', 'gravite'],
      prefill: {},
      allowNew: {},
      hidden: false
    };
    this.addFormData = {
      nom: '',
      type: defaultType,
      gravite: '2'
    };
    this.addError.set('');
    this.addModalOpen.set(true);
  }

  openEditMaladieCard(m: any): void {
    const mainType = m.types?.[0] || (m.chronique === 'true' ? 'MaladieChronique' : 'MaladieInfectieuse');
    const row = {
      maladie: m.id,
      nom: m.nom || m.id,
      type: mainType,
      gravite: m.gravite || '2'
    };
    this.editingRow.set(row);
    this.editFormData = { ...row };
    this.editError.set('');
    this.editModalOpen.set(true);
  }

  openDeleteMaladieCard(m: any): void {
    const row = {
      maladie: m.id,
      nom: m.nom || m.id
    };
    this.openDeleteModal(row);
  }

  closeAddModal(): void {
    this.addModalOpen.set(false);
    this.customAddConfig = null;
  }

  saveAddModal(): void {
    const config = this.getAddButtonConfig();
    this.addLoading.set(true);
    this.addError.set('');

    this.api.addOntologyRow(config.type, this.addFormData).subscribe({
      next: (res) => {
        this.addLoading.set(false);
        this.closeAddModal();
        this.showToast('✓ ' + (res.message || 'Élément ajouté à l\'ontologie avec succès.'));

        // Re-exécuter la question pour obtenir les résultats frais de l'ontologie
        // Cela garantit que les colonnes du tableau correspondent exactement au format SPARQL
        if (this.iaMaladieQuestion) {
          this.onAskMaladies(this.iaMaladieQuestion);
        } else {
          const curRes = this.iaMaladieResult();
          if (curRes) {
            const item = res.item || { ...this.addFormData };
            const list = curRes.donnees ? [...curRes.donnees, item] : [item];
            curRes.donnees = list;
            curRes.count = list.length;
            this.iaMaladieResult.set({ ...curRes });
          }
        }
        this.loadCatalog();
        this.loadDynamicEntities();
      },
      error: (err) => {
        this.addLoading.set(false);
        this.addError.set(err.error?.error || 'Erreur lors de l\'enregistrement.');
      }
    });
  }

  getDeletableLabel(row: any): string {
    if (!row) return 'cette relation';
    if (row.maladie && !row.patient && !row.symptome && !row.medicament && !row.medecin) return `la maladie « ${row.nom || row.maladie} » de l'ontologie`;
    if (row.patient && row.maladie) return `la relation entre ${row.patient} et ${row.maladie}`;
    if (row.maladie && row.symptome) return `le symptôme ${row.symptome} pour la maladie ${row.maladie}`;
    if (row.maladie && row.medicament) return `le médicament ${row.medicament} pour la maladie ${row.maladie}`;
    if (row.medecin && row.maladie) return `la prise en charge du médecin ${row.medecin} pour ${row.maladie}`;
    if (row.nom) return `l'élément ${row.nom}`;
    return 'cette relation';
  }

  // ── MODAL ONTOLOGIE CLASSE MALADIE ──────────────────────────────
  maladieOntologyModalOpen = signal(false);
  maladieOntologyTab = signal<'tree' | 'properties' | 'axioms' | 'code'>('tree');
  maladieOntologyData = signal<any>(null);
  loadingMaladieOntology = signal(false);
  maladieOntologySearch = signal('');

  owlCodeSnippet = `@prefix mal:  <http://example.org/ontologie-maladie#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

# ===============================================================
# 1. CLASSE RACINE : Maladie (sous-classe de owl:Thing)
# ===============================================================
mal:Maladie a owl:Class ;
    rdfs:subClassOf owl:Thing ;
    rdfs:label "Maladie"^^xsd:string ;
    rdfs:comment "Toute affection pathologique dans le système médical."^^xsd:string .

# ===============================================================
# 2. SOUS-CLASSES DIRECTES DE MALADIE
# ===============================================================
mal:MaladieInfectieuse a owl:Class ;
    rdfs:subClassOf mal:Maladie ;
    rdfs:label "Maladie infectieuse"^^xsd:string .

mal:MaladieChronique a owl:Class ;
    rdfs:subClassOf mal:Maladie ;
    rdfs:label "Maladie chronique"^^xsd:string .

mal:MaladieDigestive a owl:Class ;
    rdfs:subClassOf mal:Maladie ;
    rdfs:label "Maladie digestive"^^xsd:string .

# Disjonction mutuelle stricte des trois branches
[] a owl:AllDisjointClasses ;
    owl:members ( mal:MaladieInfectieuse mal:MaladieChronique mal:MaladieDigestive ) .

# ===============================================================
# 3. SOUS-CLASSES SPÉCIALISÉES (FEUILLES TAXONOMIQUES)
# ===============================================================
mal:Grippe a owl:Class ;
    rdfs:subClassOf mal:MaladieInfectieuse ;
    owl:disjointWith mal:Angine .

mal:Angine a owl:Class ;
    rdfs:subClassOf mal:MaladieInfectieuse .

mal:Diabete a owl:Class ;
    rdfs:subClassOf mal:MaladieChronique ;
    owl:disjointWith mal:Hypertension .

mal:Hypertension a owl:Class ;
    rdfs:subClassOf mal:MaladieChronique .

mal:UlcereGastrique a owl:Class ;
    rdfs:subClassOf mal:MaladieDigestive .

# ===============================================================
# 4. CLASSES DÉFINIES (RAISONNEMENT & INFÉRENCES OWL 2)
# ===============================================================
# Maladie nécessitant une opération chirurgicale
mal:MaladieGrave a owl:Class ;
    rdfs:subClassOf mal:Maladie ;
    owl:equivalentClass [
        a owl:Class ;
        owl:intersectionOf ( mal:Maladie [
            a owl:Restriction ;
            owl:onProperty mal:necessite ;
            owl:someValuesFrom mal:Operation
        ] )
    ] ;
    rdfs:label "Maladie grave"^^xsd:string .

# Maladie chronique sous suivi médical d'un médecin
mal:MaladieAvecSuivi a owl:Class ;
    rdfs:subClassOf mal:MaladieChronique ;
    owl:equivalentClass [
        a owl:Class ;
        owl:intersectionOf ( mal:MaladieChronique [
            a owl:Restriction ;
            owl:onProperty mal:necessiteSuiviPar ;
            owl:someValuesFrom mal:Medecin
        ] )
    ] ;
    rdfs:label "Maladie avec suivi"^^xsd:string .

# Maladie traitée par un médicament
mal:MaladieTraitee a owl:Class ;
    rdfs:subClassOf mal:Maladie ;
    owl:equivalentClass [
        a owl:Class ;
        owl:intersectionOf ( mal:Maladie [
            a owl:Restriction ;
            owl:onProperty mal:estTraiteePar ;
            owl:someValuesFrom mal:Medicament
        ] )
    ] ;
    rdfs:label "Maladie traitée"^^xsd:string .

# ===============================================================
# 5. OBJECT PROPERTIES
# ===============================================================
mal:aPourSymptome a owl:ObjectProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range mal:Symptome ;
    owl:inverseOf mal:estSymptomeDe .

mal:estTraiteePar a owl:ObjectProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range mal:Medicament ;
    owl:inverseOf mal:traite .

mal:touche a owl:ObjectProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range mal:Patient ;
    owl:inverseOf mal:souffreDe .

mal:necessite a owl:ObjectProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range mal:Operation ;
    owl:inverseOf mal:estNecessairePour .

mal:provoque a owl:ObjectProperty, owl:TransitiveProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range mal:Symptome .

# ===============================================================
# 6. DATATYPE PROPERTIES (FONCTIONNELLES)
# ===============================================================
mal:nom a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range xsd:string .

mal:gravite a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range xsd:integer .

mal:codeCIM a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range xsd:string .

mal:estContagieuse a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range xsd:boolean .

mal:estChronique a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain mal:Maladie ;
    rdfs:range xsd:boolean .
`;


  openMaladieOntologyModal(): void {
    this.maladieOntologyModalOpen.set(true);
    this.loadMaladieOntologyStructure();
  }

  closeMaladieOntologyModal(): void {
    this.maladieOntologyModalOpen.set(false);
  }

  setMaladieOntologyTab(tab: 'tree' | 'properties' | 'axioms' | 'code'): void {
    this.maladieOntologyTab.set(tab);
  }

  loadMaladieOntologyStructure(): void {
    this.loadingMaladieOntology.set(true);
    this.api.getMaladieOntologyStructure().subscribe({
      next: (data) => {
        this.maladieOntologyData.set(data);
        this.loadingMaladieOntology.set(false);
      },
      error: (err) => {
        console.error('Erreur chargement ontologie maladie', err);
        this.loadingMaladieOntology.set(false);
      }
    });
  }

  copyOntologyCode(codeText: string): void {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(codeText).then(() => {
        this.showToast('✓ Code OWL copié dans le presse-papiers.');
      });
    }
  }

  getFilteredOntoSubclasses(): any[] {
    const data = this.maladieOntologyData();
    if (!data || !data.subclasses) return [];
    const q = this.maladieOntologySearch().toLowerCase().trim();
    if (!q) return data.subclasses;

    return data.subclasses.filter((sc: any) => {
      const matchName = sc.name?.toLowerCase().includes(q) || sc.id?.toLowerCase().includes(q);
      const matchChildren = sc.children?.some((c: any) => c.name?.toLowerCase().includes(q) || c.id?.toLowerCase().includes(q));
      const matchIndiv = sc.individuals?.some((i: any) => i.nom?.toLowerCase().includes(q) || i.id?.toLowerCase().includes(q));
      return matchName || matchChildren || matchIndiv;
    });
  }

  getFilteredOntoProperties(): any[] {
    const data = this.maladieOntologyData();
    if (!data || !data.object_properties) return [];
    const q = this.maladieOntologySearch().toLowerCase().trim();
    if (!q) return data.object_properties;

    return data.object_properties.filter((p: any) =>
      p.name?.toLowerCase().includes(q) ||
      p.label?.toLowerCase().includes(q) ||
      p.domain?.toLowerCase().includes(q) ||
      p.range?.toLowerCase().includes(q)
    );
  }

  getFilteredOntoDatatypeProperties(): any[] {
    const data = this.maladieOntologyData();
    if (!data || !data.datatype_properties) return [];
    const q = this.maladieOntologySearch().toLowerCase().trim();
    if (!q) return data.datatype_properties;

    return data.datatype_properties.filter((p: any) =>
      p.name?.toLowerCase().includes(q) ||
      p.type?.toLowerCase().includes(q) ||
      p.description?.toLowerCase().includes(q)
    );
  }
}


