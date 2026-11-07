# MEDIMCOM IA — consultation médicale en pictogrammes, agents autonomes et juriste (prototype local)

Équipe **ShifaMiko** (Baudouin Nkana Bilong, Franck Ndonkou, Fotsing Engoulou — Université de Yaoundé I) · Hackathon AI for Good Lab / Sandbox – Émirats arabes unis (UIT) · rendu le 10 novembre 2026.
English summary for the jury: [README_EN.md](README_EN.md).

## Le dossier en un coup d'œil

| Je cherche… | C'est ici |
|---|---|
| Ce qu'on envoie au jury | `docs/soumission/` : rapport technique (5 pages), analyse des lacunes (PDF, en anglais), liens de référence de la base (`KB_reference_links.md`) |
| Ce qu'ont dit les organisateurs (sessions de suivi) | [`docs/equipe/NOTES_SESSIONS_UIT.md`](docs/equipe/NOTES_SESSIONS_UIT.md) |
| Qui fait quoi, ce qui reste à faire | [`docs/equipe/REPARTITION.md`](docs/equipe/REPARTITION.md) |
| Où chaque exigence de l'appel est satisfaite | [`docs/equipe/SUIVI_EXIGENCES.md`](docs/equipe/SUIVI_EXIGENCES.md) |
| Le code des agents | `medimcom/` (+ `main.py`, `evaluer_agents.py`) · guide : [`docs/technique/ARCHITECTURE_AGENTS.md`](docs/technique/ARCHITECTURE_AGENTS.md) |
| La base de connaissances (droit des Émirats) | `kb/` |
| Les écrans médecin et patient | `interface/` · captures : `docs/captures/` |
| Les pictogrammes et les tests avec des personnes sourdes | `pictogrammes/` · `docs/pictogrammes/` (planche, livret, protocole) |
| Le script de la vidéo | [`docs/video/SCRIPT_VIDEO.md`](docs/video/SCRIPT_VIDEO.md) |
| Régénérer le rapport | `python outils/generer_rapport.py` |
| Anciennes versions de travail (pas pour GitHub) | `archives/` |

Des agents autonomes collaborent autour d'un **dossier de consultation partagé**, avec une **messagerie directe** et un **journal infalsifiable** :

- **Agent 3 · Assistant** : tient l'état du patient, repère ce qui manque, fait poser des questions, suggère au médecin (avec la source), retire ses suggestions devenues inutiles, alerte en priorité en cas d'urgence.
- **Agent 2 · Juriste** : contrôle chaque prescription, chaque message destiné au patient et chaque demande de partage de données avec un **moteur de règles déterministe** fondé sur le droit des Émirats ; revérifie quand l'état du patient change ; rappelle les obligations (consentement, déclaration de maladie) ; répond aux questions en **mode conseiller** pendant une crise ; signale les **lacunes** du droit avec des exemples mondiaux.
- **Agent 1 · Traducteur** (texte ⇄ pictogrammes) : traduit les questions de l'assistant et chaque prescription conforme (avec la question d'accord), propose chaque message au médecin, l'envoie seulement après validation et feu vert du juriste, rapporte les réponses du patient. Il tourne avec un lexique de démonstration ; le modèle de pictogrammes de l'équipe se branche selon `docs/technique/CONTRAT_AGENT1.md`.
- **Agents institutionnels (crise)** : autorité de santé, hôpital, cellule de crise. Chacun ne reçoit que ses propres informations (fragmentées), **n'a pas accès au dossier du patient**, n'enregistre une mesure qu'avec une base légale contraignante, officielle et donnant un pouvoir d'agir (vérifiée par l'outil), et fait contrôler toute demande de données par le juriste.
- **Le médecin décide toujours.** Il peut maintenir une décision « à revoir » en la justifiant (son nom est enregistré) ; une décision « bloquée » ne peut pas être maintenue.

## Interface (écran médecin + écran patient)

- **Médecin :** écrire ou **dicter** (bouton micro, Chrome ou Edge, français / anglais / arabe) ; le texte est traduit en pictogrammes, combinés quand c'est plus lisible (« brûlure au ventre à gauche » = une image VENTRE + BRÛLURE + GAUCHE) ; rien ne part sans « Valider et envoyer ».
- **Patient :** tous les pictogrammes illustrés de la base, en 20 onglets (douleur, intensité 0 à 10, sensations, localisation…) et une **recherche** par mot en français, anglais ou arabe.

```bash
python interface/serveur.py                                  # affiche le lien PRIVÉ de l'écran médecin (/medecin?jeton=…) · patient : http://127.0.0.1:8000/patient
python interface/serveur.py --demo scenarios/grossesse.json  # bouton « Étape suivante » (démonstration, vidéo)
python interface/serveur.py --demo scenarios/crise.json      # crise, avec le tableau des institutions
```

L'interface est écrite en **React** (TypeScript, Tailwind, polices IBM Plex latin et arabe incluses, sans appel à Internet) dans `interface/web/`. La version compilée (`interface/web/dist/`) est fournie : **aucune installation n'est nécessaire pour l'utiliser**, le serveur Python la sert directement. Pour modifier les écrans : `cd interface/web && npm install && npm run dev` (http://localhost:5173, branché sur le serveur Python lancé à côté), puis `npm run build`. Voir `interface/web/LISEZMOI.md`. Les anciennes pages HTML restent disponibles avec `--interface classique`.

- **Écran médecin :** dossier patient ; conversation où chaque message est montré avec sa traduction en pictogrammes et validé ou rejeté sur place ; panneau des agents (messages du juriste avec leurs références, suggestions de l'assistant, ordonnance avec l'analyse du juriste, lacunes du droit, crise).
- **Écran patient (tablette) :** message reçu en grand, catégories, grille de pictogrammes, plateau de réponse, bouton d'urgence.

Écran patient sans texte obligatoire (étiquettes facultatives fr / en / عربي), palette de réponses, bouton **Combiner** (deux pictogrammes en une image, par exemple tête + douleur), bouton d'urgence. L'agent traducteur combine aussi des pictogrammes de lui-même quand c'est plus clair ; une réponse « tête + douleur, 8 » devient dans le dossier : douleur, localisation tête, intensité 8. Aucune installation : bibliothèque standard de Python. Pictogrammes : le projet utilise des pictogrammes issus de bases existantes ; `medimcom/bibliotheque.py` contient 46 icônes SVG de démonstration pour le prototype (+ chiffres, doses, médicaments), planche `docs/pictogrammes/Planche_pictogrammes.pdf`. Tests avec des personnes sourdes : `docs/pictogrammes/PROTOCOLE_TESTS.md` et `docs/pictogrammes/Livret_test_pictogrammes.pdf`. Vidéo : `docs/video/SCRIPT_VIDEO.md`.

Sécurité de l'interface (prototype) : l'écran médecin et toutes ses actions exigent un jeton secret tiré à chaque démarrage (le lien est affiché dans le terminal) ; les requêtes d'écriture doivent être en JSON et venir de la même origine (une autre page web ne peut rien déclencher, y compris par « DNS rebinding » : seuls localhost et les adresses IP sont acceptés) ; le serveur écoute sur 127.0.0.1 par défaut. Avec `--hote 0.0.0.0` (tablette), tout appareil du Wi-Fi peut répondre comme le patient et ses réponses deviennent des faits confirmés : réseau de confiance uniquement. Il n'y a ni HTTPS ni comptes utilisateurs : données fictives uniquement, jamais sur un réseau ouvert.

## Lancer

Sous Linux ou macOS, remplacer `python` par `python3` si besoin.

```bash
# Mode simulé : aucune IA, aucune installation (Python 3.10+)
python main.py                                   # consultation (grossesse)
python main.py --scenario scenarios/crise.json   # crise (maladie transmissible, téléconsultation, institutions)
python main.py --scenario scenarios/allergie.json   # autre patient, autre déroulé
python main.py --ordre aleatoire --graine 3      # ordre de passage des agents aléatoire
python main.py --langue en                       # constats du juriste en anglais
python main.py --pays CM                         # le juriste applique le droit camerounais (consultations)
python main.py --pictogrammes paquet.module:Classe   # brancher le moteur de pictogrammes de l'agent 1

# Vrais agents par API en ligne, sans machine puissante (offres gratuites ; patients fictifs uniquement)
export GEMINI_API_KEY=...          # clé gratuite : https://aistudio.google.com/apikey   (Windows : $env:GEMINI_API_KEY="...")
export GROQ_API_KEY=...            # clé gratuite : https://console.groq.com/keys
python main.py --fournisseur gemini --secours groq,openrouter --donnees-fictives
python interface/serveur.py --fournisseur gemini --secours groq --donnees-fictives     # interface de démonstration

# Vrais agents avec un modèle local (Ollama : https://ollama.com)
ollama pull qwen3:8b
pip install -r requirements.txt
python main.py --mode ollama --modele qwen3:8b
python main.py --mode openai --url http://localhost:8080/v1 --modele qwen2.5-7b-instruct   # llama.cpp, LM Studio, vLLM…

# Évaluer les agents (sécurité doit rester à 100 %, capacité mesurée)
python evaluer_agents.py
python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3 --sans-repli

# Tests (103) et contrôles de la base
python -m pytest -q                  # ou : python tests/test_noyau.py
python kb/outils/verifier_kb.py      # cohérence sources / fiches / règles / lacunes / questions
python kb/outils/evaluer_recherche.py
python kb/outils/construire_index.py # export pour une base vectorielle
ollama pull bge-m3 && python kb/outils/construire_vecteurs.py   # base vectorielle (sens), locale
python kb/outils/evaluer_recherche.py --comparer --encodeur ollama:bge-m3   # mots vs sens vs hybride
python main.py --recherche ollama:bge-m3          # agents avec recherche hybride
python kb/outils/telecharger_sources.py   # télécharge les textes officiels et fige leur SHA-256 (réseau requis)

# Journal infalsifiable et page HTML lisible
python verifier_journal.py sortie/journal.json --falsifier 10
python exporter_journal.py sortie/journal.json

# Documents (nécessitent : pip install playwright pypdf && python -m playwright install chromium)
python pictogrammes/exporter.py --pdf            # SVG + docs/pictogrammes/Planche_pictogrammes.pdf
python pictogrammes/livret.py --pdf              # docs/pictogrammes/Livret_test_pictogrammes.pdf + clé du test
python outils/generer_rapport.py                 # docs/soumission/ (rapport ≤ 5 pages + analyse des lacunes)
```

Choisir un modèle qui **sait appeler des outils** (`qwen3:8b`, `llama3.1:8b`). Guide technique des agents (partie de Franck) : [`docs/technique/ARCHITECTURE_AGENTS.md`](docs/technique/ARCHITECTURE_AGENTS.md).

## Solidité : méthodes formelles

Les verdicts ne viennent jamais du modèle de langage. Ils viennent d'un moteur de règles dont la sémantique est écrite :
- logique à trois valeurs (une information inconnue n'est jamais supposée sans danger) ;
- treillis des verdicts (le plus strict l'emporte) ;
- refus par défaut ;
- connaissances de fond (un homme n'est pas enceint).

Une **spécification formelle** (`kb/specification_formelle.json`) fixe ce qui doit être empêché et ce qui doit rester possible. Elle est vérifiée pour **toutes** les entrées possibles par deux méthodes indépendantes : une énumération exhaustive sur le moteur réel, et une preuve par solveur SMT (Z3). Un **moniteur** contrôle dix invariants de sûreté sur le journal (exemple : aucun message au patient sans validation humaine). Il tourne sur des centaines de suites d'événements générées automatiquement, dont des attaques. Cette vérification a trouvé et fait corriger 8 défauts. Méthode, littérature et traçabilité : [`docs/technique/METHODES_FORMELLES.md`](docs/technique/METHODES_FORMELLES.md) ; résultats : [`docs/technique/RAPPORT_VERIFICATION_FORMELLE.md`](docs/technique/RAPPORT_VERIFICATION_FORMELLE.md).

```bash
pip install -r requirements-dev.txt          # pytest et z3-solver
python outils/verifier_formel.py             # énumération, preuves SMT, exploration, rapport (2 à 3 minutes)
python outils/verifier_formel.py --mutations # + analyse de mutation (plus long)
python outils/verifier_formel.py --journal sortie/journal.json   # surveiller un journal existant
```

L'intégration continue (`.github/workflows/ci.yml`) relance tests, vérification formelle et banc d'évaluation à chaque modification.

## Verdicts du juriste

| Verdict | Sens | Qui peut passer outre |
|---|---|---|
| CONFORME | la décision peut avancer (avec ses obligations) | — |
| PREUVES_INSUFFISANTES | une information manque : une inconnue n'est jamais supposée sans danger | personne : il faut l'information |
| A_REVOIR | problème réel, mais affaire de jugement humain | le médecin, par écrit, nommément |
| BLOQUE | une règle contraignante (loi, norme d'un régulateur) l'interdit | personne |

Seule une source contraignante peut **bloquer** ; une recommandation clinique peut au plus demander une **révision**. Chaque constat cite la fiche de la base, l'article, le lien officiel et le niveau de vérification.

## Base de connaissances (`kb/`)

| Fichier | Contenu |
|---|---|
| `sources.json` | 40 textes : Émirats (lois fédérales, DoH, DHA, MOHAP, charte et stratégie IA), Cameroun (exercice de la médecine, données personnelles, handicap, déontologie, pharmacie, code pénal), exemples mondiaux (ONU, OMS, UE, FDA, NHS, ISO, UA), références UIT (Y.3172, cadre de préparation à l'IA 2.0), comparaison Cameroun |
| `fiches.jsonl` | 124 dispositions (article, résumé, citation courte, thèmes, base juridique) |
| `regles_uae.json` · `regles_cm.json` | 61 règles du juriste pour les Émirats, 49 pour le Cameroun (`--pays CM`), chacune citant ses fiches ; signature typée des variables et 3 axiomes (connaissances de fond) |
| `specification_formelle.json` | 30 exigences de sûreté et d'utilité que les règles doivent satisfaire pour toutes les entrées (vérifiées par `outils/verifier_formel.py`) |
| `lacunes.json` | 9 lacunes : ce que disent les textes, ce qui manque, exemples mondiaux, réponse de MEDIMCOM |
| `questions_test.jsonl` | 65 questions (anglais et français) avec la fiche attendue |
| `index/chunks.jsonl` | 133 morceaux autonomes avec métadonnées, prêts pour une base vectorielle |
| `outils/` | contrôle, évaluation, export, téléchargement avec empreintes |

Niveaux de vérification : `official_text` (lu sur le site officiel), `secondary_source` (connu par un cabinet ou la presse : obtenir le texte officiel), `to_confirm`. Le texte arabe des lois prévaut.

## Constituer la base sur votre ordinateur

**Version 2 (recommandée)** : base plus volumineuse, filtrée santé / consultation, rangée selon les exigences du hackathon.

```bash
python outils/constituer_base_v2.py --audit-pictos                      # 1. inventaire des étiquettes ARASAAC (rapide, sans images)
python outils/constituer_base_v2.py                                     # 2. base complète, de zéro -> ~/MEDIMCOM_base_v2 (--ancienne-base facultatif)
python outils/constituer_base_v2.py                                     # 3. relancer après avoir déposé des PDF dans entrees_manuelles/
```

| Dossier produit | Contenu |
|---|---|
| `01_base_juridique/` | 87 documents officiels et ouverts (catalogue `kb/corpus/catalogue_sources.json`) : `A_cameroun/` (santé, IA-numérique-cybersécurité, données, institutions, handicap), `B_international/` (ONU droits humains, IA, OMS, handicap, données, éthique médicale, UIT), `C_afrique_regional/` (UA), `D_emirats_pays_hote/`. Par document : `fiche.md`, `texte.md`, `articles.jsonl`, `original.pdf`. Plus `matrice_exigences.md` (exigence × juridiction, lacunes), `index_sources.csv`, `corpus_rag.jsonl` |
| `02_pictogrammes/` | ARASAAC, Mulberry, OpenMoji filtrés pour la consultation : 1 287 notions en 30 catégories organisées selon ce qu'on veut dire (accueillir, questionner, décrire une douleur, donner une consigne, conseiller, rassurer, prescrire un traitement, une opération, un régime, une hygiène de vie) ; notions composées = suites de pictogrammes (`kb/corpus/vocabulaire_consultation.json`) ; `catalogue.csv`, `notions.csv`, `planches/`, `audit/rejets.csv`, `LICENCES.md` |
| `03_references_medicales/` | fiches d'information de l'OMS (fr / en / ar) découpées par section, résumés MedlinePlus, lexique Wikidata fr / en / ar avec codes CIM-10 — construits de zéro |
| `04_jeu_de_donnees_assistant/` | cas fictifs pour l'assistant médical |
| `05_jeux_entrainement/` | jeux prêts pour entraîner ou évaluer un modèle : images ⇄ libellés (format imagefolder), pictogrammes ⇄ phrases fr/en, classification et recherche juridiques, questions-réponses OMS, lexique ; `FICHE_DE_DONNEES.md` |
| `a_telecharger_a_la_main.md`, `entrees_manuelles/` | documents à obtenir à la main ; déposer `<ID>.pdf` puis relancer |
| `journal.json` | adresse, date et empreinte SHA-256 de chaque document et image |

**Tous les pictogrammes, tous domaines** : `--tous-pictos` prend le catalogue complet d'ARASAAC, de Mulberry et d'OpenMoji
(plus de 10 000 images ; téléchargement en parallèle, `--paralleles 6`, repris là où il s'était arrêté). Les images hors
santé vont dans « Tous les mots » (`90_vocabulaire_general`) et « Émojis, symboles » (`91_emojis_symboles`), triées par
popularité ; les contenus marqués sexualité ou violence par ARASAAC sont gardés dans `98_sensible`, jamais dans les onglets
du patient, seulement par la recherche. Le traducteur utilise le mot-clé français exact de ces images quand le vocabulaire
de consultation n'a rien (« voiture », « école ») ; jamais un libellé anglais, jamais un contenu sensible.

Objectif de volume des pictogrammes : `--objectif-pictos 3000` (par défaut) ; si la sélection stricte ne suffit pas, le script élargit par paliers sans jamais lever la liste noire, et indique dans `02_pictogrammes/LISEZMOI.md` si l'objectif est atteint. Le tri des pictogrammes se règle dans `kb/corpus/filtres_pictogrammes.json` (liste blanche, liste noire, plafonds) ; voir `kb/corpus/LISEZMOI.md`.

**Brancher la base sur les agents.** Placez-la dans `MEDIMCOM_IA/base_v2` (ou laissez-la dans `~/MEDIMCOM_base_v2`) : elle est trouvée
automatiquement au lancement, sans option. Le traducteur utilise alors le vocabulaire de consultation et les images de la base
(`medimcom/base_v2.py`, mêmes règles de sûreté : négation, « au maximum », chiffres, doses) ; l'outil `consulter_base` des agents
renvoie, en plus des dispositions du juriste, les articles des textes officiels et les sections des fiches de l'OMS, avec leur lien ;
la palette du patient s'enrichit des notions illustrées. `--base aucune` revient à la base interne seule ; `MEDIMCOM_PICTOS=demo`
garde le lexique de démonstration.

```bash
python outils/evaluer_base_v2.py      # chiffres pour le rapport : traduction, recherche juridique, recherche OMS -> base_v2/06_evaluation/
```

**Version 1** (toujours disponible) : `python outils/constituer_base.py` produit l'ancienne arborescence `1_textes_juridiques/ 2_pictogrammes/ 3_jeu_de_donnees_assistant/`.

Les images ARASAAC sont téléchargées automatiquement ; celles de Tawasol, Mulberry ou Sclera se déposent dans `pictogrammes/bases/images/<base>/<ID>.png` (voir `pictogrammes/bases/LISEZMOI.md`). SantéBD reste bloquée sans accord écrit. Relancer le script met tout à jour sans rien retélécharger.

Recherche mesurée (BM25 sans dépendance, lexique français → anglais) : rappel@1 = 0,80 · rappel@3 = 0,94 · rappel@5 = 0,97 · MRR = 0,87.

### Sécurité clinique des prescriptions

Le juriste rapproche chaque prescription de la fiche du patient (grossesse, âge, rein, foie, ulcère, anticoagulant, allergie)
et de la dose par jour, à partir de notices officielles citées mot pour mot (tramadol, paracétamol, ibuprofène, aspirine,
amoxicilline, metformine, misoprostol). L'assistant dit aussitôt pourquoi ne pas prescrire en l'état et propose une
alternative contrôlée par le juriste pour ce patient. Détail, niveaux et limites : `docs/technique/SECURITE_CLINIQUE.md`.

### Recherche hybride : mots-clés + sens (facultative, en local)

Les agents cherchent dans **quatre collections** : dispositions vérifiées du juriste (`kb/`), articles des textes officiels,
sections des fiches de l'OMS, et **pictogrammes** (libellés fr / en / ar, synonymes, mots-clés ARASAAC, catégorie).

| Étape | Comment |
|---|---|
| Découpage | textes officiels : par article (« Article 12 », « Art. 3 »), puis fenêtres de 1 800 caractères avec 200 de recouvrement ; OMS : par section ; `kb/` : une disposition par morceau ; pictogrammes : une fiche par notion |
| Contexte | chaque morceau est encodé précédé de son titre et de son article (« Loi 2/2019 — Article 13 ») |
| Vectorisation | modèle d'encodage **local** (aucune donnée ne sort, aucune clé) : `fastembed:e5` = multilingual-e5-large (1 024 dim., fr/en/ar), `fastembed:mpnet` (plus rapide), ou `ollama:bge-m3` |
| Similarité | cosinus sur vecteurs normalisés |
| Fusion | les 30 meilleurs par mots-clés (BM25) et les 30 meilleurs par le sens, fusionnés par rangs réciproques (RRF, k = 60) ; pour les pictogrammes, s'y ajoutent la ressemblance d'écriture (fautes de frappe) et le libellé exact en tête |
| Traçabilité | chaque résultat dit pourquoi il est là : rang par mots, rang et cosinus par le sens |
| Sûreté | la recherche sert à **citer** et à **proposer** : le verdict du juriste reste celui du moteur de règles ; un pictogramme proche n'est jamais inséré sans que le médecin le choisisse |

```bash
pip install -r requirements-vecteurs.txt                       # une fois : fastembed (ONNX, sans PyTorch) + numpy
python outils/vectoriser_base.py                               # tout encoder (reprend où il s'était arrêté) -> base_v2/07_vecteurs/
python interface/serveur.py --fournisseur xai --effort low --donnees-fictives --recherche fastembed:e5
python outils/evaluer_base_v2.py --recherche fastembed:e5      # compare mots-clés, sens et hybride (chiffres pour le rapport)
```

Ce que les agents en font : `consulter_base` (tous les agents) devient hybride ; le nouvel outil `chercher_pictogrammes` permet
au traducteur et à l'assistant de trouver une image pour un mot absent (« essoufflement », « tête qui tourne ») ; sur chaque
proposition, les pictogrammes proches des mots non traduits sont proposés au médecin, qui clique pour les ajouter ; le patient
et le médecin trouvent un pictogramme par le sens dans leur barre de recherche. Si le modèle manque, tout continue en BM25 et
le journal le dit. `--exporter` écrit aussi les vecteurs au format `{id, text, metadata, embedding}` (Chroma, base de l'UIT).

## Organisation

```
MEDIMCOM_IA/
├── README.md · README_EN.md · requirements.txt
├── main.py               lance une consultation ou une crise (terminal)
├── evaluer_agents.py     banc d'évaluation (invariants de sécurité + attendus)
├── verifier_journal.py · exporter_journal.py   journal infalsifiable, page HTML lisible
├── medimcom/             le cœur
│   ├── agents.py         Agent (observer → réfléchir → agir) : Traducteur, Assistant, Juriste,
│   │                     institutions AutoriteSante, Hopital, CelluleCrise
│   ├── dossier.py        dossier partagé, versionné ; maintien nominatif d'une décision
│   ├── messagerie.py     messages directs typés : demande, information, alerte, proposition, desaccord
│   ├── orchestrateur.py  libère les événements, laisse les agents agir jusqu'à stabilité
│   ├── journal.py        journal chaîné (SHA-256) + vérification
│   ├── regles.py · base.py   moteur de règles du juriste (sémantique formelle) · base de connaissances (citations, BM25, lacunes)
│   ├── formel.py · formel_smt.py   vérification exhaustive des règles · preuves SMT (Z3), analyse de mutation
│   ├── surveillance.py · exploration.py   moniteur du journal (R1 à R10) · exploration automatique du système
│   ├── cerveaux.py       CerveauSimule (sans IA) · CerveauOllama · CerveauOpenAI
│   ├── session.py · evaluation.py · mandats.json
│   ├── pictogrammes.py   interface du moteur de pictogrammes + lexique de démonstration
│   └── bibliotheque.py   icônes SVG de démonstration, libellés fr / en / ar
├── interface/            serveur.py (sans dépendance) · web/ (interface React : src/, dist/ compilé) · classique/ (pages HTML simples)
├── pictogrammes/         exporter.py, livret.py, analyse_tests.py, svg/ (46 fichiers), test/ (clé, modèle de réponses)
├── kb/                   base de connaissances (voir ci-dessus) + outils/
├── scenarios/            grossesse.json · crise.json · allergie.json — chacun avec ses attendus
├── tests/                103 tests
├── outils/               verifier_formel.py (vérification formelle) · constituer_base_v2.py (base complète sur votre ordinateur) · constituer_base.py (version 1) · jeu_assistant.py (jeu de données)
│                         · generer_rapport.py · generer_fiche.py (fiche projet d'une page)
├── donnees/              presentations_cliniques.json (10 motifs de consultation, à valider par un médecin)
├── docs/
│   ├── soumission/       MEDIMCOM_IA_Technical_Report.pdf · MEDIMCOM_IA_Gap_Analysis.pdf · KB_reference_links.md
│   ├── equipe/           REPARTITION.md · SUIVI_EXIGENCES.md · NOTES_SESSIONS_UIT.md · MEDIMCOM_IA_Fiche_projet.pdf
│   ├── technique/        ARCHITECTURE_AGENTS.md · CONTRAT_AGENT1.md · METHODES_FORMELLES.md · RAPPORT_VERIFICATION_FORMELLE.md
│   ├── pictogrammes/     Planche_pictogrammes.pdf · Livret_test_pictogrammes.pdf · PROTOCOLE_TESTS.md
│   ├── video/            SCRIPT_VIDEO.md
│   └── captures/         écrans médecin et patient
└── archives/             versions de travail dépassées (exclu de Git)
```

## Limites connues

- Les modes Ollama et compatible OpenAI sont implémentés ; leurs garde-fous sont testés avec des modèles factices, dont un modèle « chaotique » qui ne casse jamais les invariants de sécurité. Les résultats de référence viennent des politiques écrites. **À faire : `python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3 --sans-repli`** (voir le guide, section 8).
- Les règles cliniques (AINS, misoprostol) sont des exemples tirés de sources publiques : **à valider par un médecin** et à remplacer par le formulaire des Émirats. Praticiens et médicament non enregistré : fictifs.
- 7 sources ne sont connues que par une source secondaire (dont la résolution 51/2021, dont la page officielle n'a pas pu être lue, et trois lois camerounaises) et 3 restent à confirmer (code de déontologie, pharmacie et code pénal camerounais) ; les originaux arabes ne sont pas encore intégrés ; la norme IA du DoH doit être révisée en octobre 2026 et la date de révision de la politique IA de la DHA est passée : à revérifier.

⚠️ Prototype de hackathon, données fictives : ce n'est pas un dispositif médical ni un avis juridique.

## Licence

Code : Apache 2.0 (`LICENSE`). Les pictogrammes ARASAAC restent sous licence CC BY-NC-SA 4.0 (non commercial) ; détail des contenus de tiers dans `NOTICE.md`.
