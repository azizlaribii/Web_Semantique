# Scénario de démonstration — Module Médicament

Durée conseillée : 8 à 10 minutes. Thématique : **Pharmaceutique et Santé** (molécules, effets secondaires,
contre-indications, données cliniques).

**Avant de commencer :** `python run_app.py`, se connecter, ouvrir l'onglet **Gestion Médicaments** et
cliquer sur **Réinitialiser l'ontologie** (deux clics) pour repartir de l'état d'origine.

---

## 1. L'ontologie dans Protégé (≈ 2 min) — critères *Individus* et *Valeur ajoutée*

Ouvrir `ontologie_medicament.owl` dans Protégé.

- **Classes** : `Medicament` et ses 7 classes thérapeutiques, `Molecule`, `EffetSecondaire` (7 familles),
  `ConditionClinique`, `InteractionMedicamenteuse`, `EssaiClinique`.
- **Axiomes** : disjonctions (onglet *Disjoint With*), restriction `Medicament ⊑ contientMolecule some Molecule`,
  propriété symétrique `interagitAvec`.
- **Classes définies** : `EffetGrave ≡ EffetSecondaire ⊓ graviteEffet value 3`,
  `MedicamentARisque ≡ Medicament ⊓ peutProvoquer some EffetGrave`.
- Lancer **HermiT** (*Reasoner → Start reasoner*) : Brufen, Aspegic, Coumadine… apparaissent dans
  `MedicamentARisque` sans l'avoir déclaré.
- **Individus** : 8 médicaments, 8 molécules, 12 effets, 6 conditions, 5 interactions, 6 essais cliniques.
- Lien avec le module Maladie : `Glucophage traite mal:Diabete_Type2`.

## 2. Le module NLP (≈ 3 min) — critère *Api IA*

Dans l'onglet **IA — Médicaments**, taper les questions suivantes. Pour chacune, montrer le **panneau Analyse NLP**
(tokens et lemmes spaCy → entités → texte délexicalisé → intention et confiance → requête SPARQL).

| Question à taper | Ce qu'il faut montrer |
|---|---|
| `Quels sont les effets secondaires du Brufen ?` | Cas simple : entité Médicament, intention `effets_secondaires` |
| `Ma femme est enceinte, peut-elle prendre du brufin ?` | Faute de frappe **corrigée** (« brufin » → Brufen), 2 entités (Condition + Médicament) |
| `Mon fils a la grippe, que lui donner ?` | Phrase jamais vue à l'entraînement ; requête **croisée** vers le module Maladie |
| `Effets du paracétamol` | La **molécule** est reconnue et reliée au médicament Doliprane |
| `Médicaments sans contre-indication` | Le paramètre **négation** produit un `FILTER NOT EXISTS` |
| `Quel est le médicament le plus efficace ?` | **Superlatif** → `ORDER BY DESC(...) LIMIT 3` sur les essais cliniques |

À dire : *« Pas de LLM. spaCy (modèle `fr_core_news_sm`) fait la tokenisation, la lemmatisation et
la reconnaissance d'entités avec un PhraseMatcher alimenté par l'ontologie. Les entités sont remplacées
par leur type, puis un classifieur scikit-learn (TF-IDF + régression logistique) entraîné sur 360 phrases
choisit l'intention parmi 15. Un gabarit SPARQL est ensuite rempli avec les entités. »*
Chiffre à citer : **82 % de précision en validation croisée** (`python backend/test_ia_medicament.py`).

## 3. Le CRUD en SPARQL Update (≈ 3 min) — critère *Requêtes SPARQL*

Dans l'onglet **Gestion Médicaments** :

1. **Create** — Nom `Spasfon`, classe Antalgique, dosage `80 mg`, prix `4.5`, molécule
   *+ Nouvelle molécule…* `Phloroglucinol` / `C6H6O3`, effets *Eruption cutanée* et *Hépatotoxicité*,
   contre-indiqué en cas de *Grossesse*, traite *Ulcère gastrique*. Cliquer **Ajouter**.
   → Montrer la requête `INSERT DATA` affichée, puis le médicament dans la liste : badge **« À risque »** ajouté
   automatiquement (règle d'inférence SPARQL, car l'hépatotoxicité est un effet grave).
2. **Le NLP reconnaît le nouveau médicament** — dans **IA — Médicaments**, taper `effets secondaires du spasfon`.
3. **Update** — Sur la ligne Spasfon, **Modifier** : prix `5.2`, décocher *Hépatotoxicité*, **Enregistrer**.
   → Requête `DELETE { } INSERT { } WHERE { }` limitée aux champs modifiés ; le badge « À risque » disparaît.
4. **Delete** — **Supprimer** (deux clics). → Requête `DELETE WHERE` qui retire aussi le médicament de
   la liste `owl:AllDifferent` (liste RDF chaînée).
5. Montrer que `ontologie_medicament.owl` est réellement modifié (le rouvrir dans Protégé après l'étape 1).

## 4. Communication front / back (≈ 1 min) — critères *Interfaces* et *Communication FE/BE*

- Frontend Angular → API Flask en JSON : `POST /api/ia/ask`, `GET/POST/PUT/DELETE /api/medicaments`.
- Ouvrir l'outil réseau du navigateur (F12 → Réseau) pendant un ajout pour montrer la requête `POST` et sa réponse
  (`operation`, `sparql_update`).
- Onglet **SPARQL** du dashboard : requête libre sur le graphe.

---

## Architecture à présenter

```
Navigateur — Angular 18 (dashboard)
   │  fetch JSON : POST /api/ia-medicament/ask · GET/POST/PUT/DELETE /api/medicaments
   ▼
Flask (backend/app.py)
   ├── nlp_medicament.py        spaCy + scikit-learn + difflib  → intention + entités
   ├── ia_medicament_service.py gabarits SPARQL par intention
   └── medicament_service.py    RDFLib : SELECT, SPARQL Update, règles d'inférence, sauvegarde OWL
   ▼
ontologie_medicament.owl  (+ ontologie_maladie.owl pour les liens croisés)
```

## Questions probables du jury

- **Pourquoi délexicaliser ?** Pour que le classifieur apprenne la forme de la question et non les noms :
  un médicament ajouté par le CRUD est compris sans réentraîner le modèle.
- **Que se passe-t-il si l'intention est incertaine ?** On prend l'intention la plus probable dont les
  paramètres obligatoires sont présents (ex. une fiche exige un médicament), sinon on liste les médicaments.
- **Les inférences après un ajout ?** HermiT n'est pas relancé à chaque écriture : des règles SPARQL Update
  reproduisent les 4 classes définies (`EffetGrave`, `MedicamentARisque`, `MedicamentSurOrdonnance`,
  `MedicamentEvalueCliniquement`). On peut toujours relancer HermiT dans Protégé pour vérifier.
- **Les données sont-elles réelles ?** Molécules, formules et codes ATC oui ; prix et essais cliniques
  sont des valeurs pédagogiques fictives.
