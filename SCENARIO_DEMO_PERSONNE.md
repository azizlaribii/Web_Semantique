# 📋 Scénario de Démonstration — Module Personne & Rôles
**Matière :** Web Sémantique (ESPRIT 2026/2027)  
**Classe cible :** `med:Personne` et l'ensemble de ses sous-classes  
**Architecture :** Angular (Frontend) ↔ Flask Python (Backend) ↔ RDFLib / Graph OWL (Web Sémantique)

---

## 🎯 Objectif de la Démonstration
Prouver que le module **Personne** satisfait à 100% les critères de la grille d'évaluation officielle d'ESPRIT :
1. **Requêtes SPARQL complexes** (SELECT, FILTER, SAMPLE, GROUP BY, subClassOf*, COALESCE, COUNT).
2. **Individus instanciés** avec des types riches (Médecins, Spécialistes, Patients, Stagiaires, Stuff Médical).
3. **Scénario cohérent** (Consultation, ajout dynamique, filtrage multi-critères).
4. **API IA avancée** (Traduction Langage Naturel ➔ SPARQL, découverte dynamique de nouvelles sous-classes, 100% de taux de succès).
5. **Interface Graphique interactive** (Angular, dashboard, table CRUD, cartes profil, chatbot intégré).
6. **Communication BE ↔ FE fluide** (REST JSON, gestion des erreurs, temps de réponse < 500ms).
7. **Valeur Ajoutée** (Moteur dynamique sans redémarrage, slot-filling sémantique, suggestions automatiques).

---

## 🎬 Déroulé pas-à-pas de la Démonstration (Soutenance)

### Étape 1 : Visualisation des Individus & Ontologie (2 pts)
- **Action :** Ouvrir le Dashboard Angular sur le module **Personnes & Rôles**.
- **Ce que le validateur voit :**
  - La liste de tous les individus instanciés (~20 individus) : Médecins Généralistes (`Dr Ahmed`, `Dr Fatima`), Spécialistes (`Dr Sophie Martin` en Cardiologie, `Dr Karim`), Patients Adultes (`Sami`, `Omar`, `Sara`), Patients Enfants (`Amina`), Stagiaires (`Ali`), et Stuff Médical (`Asma` ASH, `azmi` Secrétaire).
  - Propriétés complètes : Nom, Prénom, Rôle/Classe, Âge, Téléphone, Email, CIN, Numéro de Dossier, Groupe Sanguin.

---

### Étape 2 : Exécution de Requêtes SPARQL Complexes (4 pts)
Montrer dans l'onglet SPARQL ou via les requêtes du backend :
1. **Requête avec héritage transitif (`rdfs:subClassOf*`) :**
   ```sparql
   PREFIX : <http://example.org/ontologie-medicale#>
   SELECT DISTINCT ?personne ?role ?nom WHERE {
       ?personne rdf:type ?role .
       ?role rdfs:subClassOf* :Personne .
       OPTIONAL { ?personne :nom ?nom }
   }
   ```
2. **Requête d'agrégation & statistiques (`COUNT`) :**
   ```sparql
   PREFIX : <http://example.org/ontologie-medicale#>
   SELECT (COUNT(DISTINCT ?m) AS ?totalMedecins) WHERE {
       ?m rdf:type/rdfs:subClassOf* :Medecin .
   }
   ```
3. **Requête multi-critères avec filtres d'âge et extraction sécurisée (`COALESCE`) :**
   ```sparql
   PREFIX : <http://example.org/ontologie-medicale#>
   SELECT DISTINCT ?patient ?nom ?age ?dossier WHERE {
       ?patient rdf:type/rdfs:subClassOf* :Patient ;
                :age ?age ;
                :numeroDossier ?dossier .
       OPTIONAL { ?patient :nom ?nom }
       FILTER(?age >= 18 && ?age <= 60)
   } ORDER BY ?age
   ```

---

### Étape 3 : Démonstration du Chatbot IA Sémantique (4 pts)
Tester en direct les prompts suivants devant le jury :
1. **Compréhension des rôles et sous-classes spécifiques :**
   - Question : `donne moi toutes les secrétaires médicale`
   - Résultat : Trouve immédiatement l'individu `azmi` avec le rôle `Secrétaires médicales`.
2. **Compréhension du Stuff Médical :**
   - Question : `qui fait partie du stuff medical`
   - Résultat : Trouve `Asma` (Agents de service hospitalier) et `azmi` (Secrétaire médicale).
3. **Filtres sémantiques et intervalles d'âge :**
   - Question : `personnes entre 20 et 40 ans`
   - Résultat : Liste filtrée avec les âges respectifs ordonnés.
4. **Recherche par attribut médical précis :**
   - Question : `patient avec groupe sanguin A+`
   - Résultat : Extrait les patients correspondants (`Sami Trabelsi`).
5. **Comptage automatique :**
   - Question : `combien de medecins`
   - Résultat : Calcul direct en SPARQL (`COUNT`) avec explication en langage naturel.

---

### Étape 4 : Preuve de la Dynamicité (Valeur Ajoutée - 2 pts)
1. **Action :** Ajouter un nouvel individu ou une nouvelle sous-classe dans l'ontologie via le formulaire CRUD ou Protégé :
   - Exemple : Ajouter un individu `Mariem` avec rôle `Secrétaire médicale`.
2. **Vérification immédiate dans le chat sans redémarrer le serveur :**
   - Question : `combien de secretaires` ➔ Réponse : `2 résultats`.
   - Question : `cherche Mariem` ➔ La fiche complète s'affiche.
3. **Confinement strict :**
   - Prouver que le chat Personne ne renvoie jamais de concepts parasites hors-sujet (`Maladie`, `Médicament`).

---

### Étape 5 : Communication Backend / Frontend & UI (3 + 3 pts)
- Architecture en services découplés (`ApiService` sous Angular, `ia_service.py` et `rdflib_service.py` sous Flask).
- Réactivité immédiate avec loaders visuels, gestion d'erreurs en alertes stylisées, pagination et filtres dynamiques.

