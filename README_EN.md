# MEDIMCOM IA — detailed guide (commands, knowledge base, hybrid search, formal methods)

Team **ShifaMiko** (Baudouin Nkana Bilong, Franck Ndonkou, Fotsing Engoulou — University of Yaoundé I) · ITU AI for Good Lab / Sandbox Hackathon – United Arab Emirates · submission of 10 November 2026.
Main page for the jury: [README.md](README.md) · submission map: [SUBMISSION.md](SUBMISSION.md).

## The folder at a glance

| I am looking for… | It is here |
|---|---|
| Start in two minutes | paste a key (optional) in `CLE_API.txt`, then `bash lancer_local.sh` — guide: [`docs/GUIDE_CLE_API.md`](docs/GUIDE_CLE_API.md) |
| The submission map (every requirement of the call → file) | [`SUBMISSION.md`](SUBMISSION.md) |
| What is sent to the jury | `docs/soumission/`: technical report (official template, 5 pages), detailed technical documentation, gap analysis, knowledge-base reference links (`KB_reference_links.md`) |
| The base in the format of the ITU reference ingestion code | [`kb/InputDocs/`](kb/InputDocs/) (`AI_Strategies/`, `AI_Use_Cases/`, `Inputs.md`) — `python kb/outils/exporter_inputdocs.py` |
| The extended knowledge base `base_v2` | release file of the repository — installation: [README.md, section 4.2](README.md#42-extended-knowledge-base-base_v2); building: section "Building the knowledge base" below |
| What the organisers said (mentoring sessions) | [`docs/equipe/NOTES_SESSIONS_UIT.md`](docs/equipe/NOTES_SESSIONS_UIT.md) |
| Who does what | [`docs/equipe/REPARTITION.md`](docs/equipe/REPARTITION.md) |
| Where each requirement of the call is met | [`docs/equipe/SUIVI_EXIGENCES.md`](docs/equipe/SUIVI_EXIGENCES.md) |
| The agents' code | `medimcom/` (+ `main.py`, `evaluer_agents.py`) · guide: [`docs/technique/ARCHITECTURE_AGENTS.md`](docs/technique/ARCHITECTURE_AGENTS.md) |
| The knowledge base (UAE law) | `kb/` |
| The doctor and patient screens | `interface/` · screenshots: `docs/captures/` |
| Pictograms and tests with deaf people | `pictogrammes/` · `docs/pictogrammes/` (sheet, booklet, protocol) |
| The demo video | step-by-step script [`docs/video/MEDIMCOM_IA_Script_demo_pas_a_pas.docx`](docs/video/MEDIMCOM_IA_Script_demo_pas_a_pas.docx) · plan [`docs/video/SCRIPT_VIDEO.md`](docs/video/SCRIPT_VIDEO.md) · `bash lancer_demo.sh` |
| Regenerate the detailed documentation | `python outils/generer_rapport.py` |
| Old working versions (not for GitHub) | `archives/` |

## The agents

Autonomous agents collaborate around a **shared consultation record**, with **direct messaging** and a **tamper-evident
journal**. Every agent has the same architecture: a **language model drives it** in a reason-and-act loop (it reads the
record and its messages, decides what to do and calls its own tools), and a **written, verified policy** takes over at once
if the model fails, times out or runs out of quota. Which agents use the model: `AGENTS=assistant` (default),
`AGENTS=assistant,juriste` or `AGENTS=tous`.

- **Agent 3 · Assistant**: keeps the patient state, spots what is missing, has questions asked, makes suggestions to the doctor (with the source), withdraws suggestions that became useless, raises emergencies first.
- **Agent 2 · Jurist**: checks every prescription, every message to the patient and every data-sharing request; its **verdicts come from a deterministic rule engine** grounded in UAE law, which it calls as tools. When a language model drives it, the model decides what to check and when, writes the explanations and answers the institutions, but **cannot change a verdict**. It re-checks when the patient's state changes, recalls obligations (consent, disease notification), answers questions in **advisor mode** during a crisis, and reports legal **gaps** with global examples.
- **Agent 1 · Translator** (text ⇄ pictograms): translates the assistant's questions and every compliant prescription (with the consent question), proposes each message to the doctor, sends it only after validation and the jurist's green light, reports the patient's answers. It runs with a demo lexicon, or with the 1,287-concept vocabulary of `base_v2`; the team's pictogram engine plugs in according to `docs/technique/CONTRAT_AGENT1.md`.
- **Institutional agents (crisis)**: health authority, hospital, crisis cell. Each one only receives its own (fragmented) information, **has no access to the patient record**, records a measure only with a binding, official legal basis that grants the power to act (checked by the tool), and has every data request checked by the jurist.
- **The doctor always decides.** A "to review" decision can be maintained with a justification (the doctor's name is recorded); a "blocked" decision cannot.

## Interface (doctor screen + patient screen)

- **Doctor:** type or **dictate** (microphone button, Chrome or Edge, French / English / Arabic); the text is translated into pictograms, combined when it is clearer ("burning in the left belly" = one image BELLY + BURN + LEFT); nothing leaves without "Validate and send".
- **Patient:** all the illustrated pictograms of the base, in 20 tabs (pain, intensity 0 to 10, sensations, location…) and a **search** by word in French, English or Arabic.

```bash
python interface/serveur.py                                  # prints the PRIVATE doctor link (/medecin?jeton=…) · patient: http://127.0.0.1:8000/patient
python interface/serveur.py --demo scenarios/grossesse.json  # "Next step" button (demonstration, video)
python interface/serveur.py --demo scenarios/crise.json      # crisis, with the institutions' board
bash lancer_demo.sh                                          # everything needed to film the demo (3 servers + journal)
```

The interface is written in **React** (TypeScript, Tailwind, IBM Plex Latin and Arabic fonts included, no Internet call) in
`interface/web/`. The compiled version (`interface/web/dist/`) is provided: **nothing to install to use it**, the Python
server serves it directly. To change the screens: `cd interface/web && npm install && npm run dev`
(http://localhost:5173, connected to the Python server running next to it), then `npm run build`. See
`interface/web/LISEZMOI.md`. The old HTML pages remain available with `--interface classique`.

- **Doctor screen:** patient record (saved automatically, used by the agents as soon as a field is left); conversation where each message is shown with its pictogram translation and validated or rejected on the spot; agents panel (jurist messages with their references, assistant suggestions and questions, prescription with the jurist's analysis, law gaps, crisis); documents sent by the patient; readable audit journal.
- **Patient screen (tablet):** message received in large, categories, pictogram grid, answer tray, "I don't understand", emergency button, "My prescription", "Send a document".

Patient screen with no mandatory text (optional labels fr / en / عربي), answer palette, **Combine** button (two pictograms in
one image, e.g. head + pain), emergency button. The translator also combines pictograms by itself when it is clearer; an
answer "head + pain, 8" becomes in the record: pain, location head, intensity 8. The project uses pictograms from existing
databases; `medimcom/bibliotheque.py` contains 46 demo SVG icons for the prototype (+ numbers, doses, medicines), sheet
`docs/pictogrammes/Planche_pictogrammes.pdf`. Tests with deaf people: `docs/pictogrammes/PROTOCOLE_TESTS.md` and
`docs/pictogrammes/Livret_test_pictogrammes.pdf`.

Interface security (prototype): the doctor screen and all its actions require a secret token drawn at each start (the link
is printed in the terminal); write requests must be JSON and come from the same origin (another web page cannot trigger
anything, including through "DNS rebinding": only localhost and IP addresses are accepted); the server listens on 127.0.0.1
by default. With `--hote 0.0.0.0` (tablet), any device on the Wi-Fi can answer as the patient and its answers become
confirmed facts: trusted network only. There is neither HTTPS nor user accounts: fictitious data only, never on an open
network.

## Starting

### In one command, with the key of your choice

1. **API key (optional)**: `CLE_API.txt` (created at first start) contains a single line, `CLE=votre_clé`: replace
   `votre_clé` with **one** key. The provider is recognised from the beginning of the key: Groq `gsk_`, OpenRouter `sk-or-`,
   Gemini `AIza`, Mistral (with `FOURNISSEUR=mistral`) — free tiers; xAI/Grok `xai-`, Anthropic/Claude `sk-ant-`, OpenAI
   `sk-` — paid. Without a key: agents on their written rules (everything works). Full guide:
   [`docs/GUIDE_CLE_API.md`](docs/GUIDE_CLE_API.md).
2. **Extended base (optional)**: unzip `base_v2.zip` (release file) at the root → `MEDIMCOM_IA/base_v2/`; it is found
   automatically.
3. **Start**:

```bash
bash lancer_local.sh              # the key of CLE_API.txt; without a key: Ollama if installed, otherwise written rules
bash lancer_local.sh ollama       # open-source model qwen3:8b ON the computer: no key, nothing leaves (8 GB of memory at least)
VISION=1 bash lancer_local.sh ollama   # same + qwen3-vl:8b to read photos of prescriptions, receipts, medicine boxes
bash lancer_local.sh sans-ia      # written rules only
bash lancer_local.sh cle          # says which provider and model CLE_API.txt will give
bash lancer_local.sh diagnostic   # "model unavailable"? tests Internet, certificates, key, quota, model, and says what to do
```

The script prepares Python (`.venv` folder), installs what is missing, then shows the recognised provider and the doctor and
patient links. Options: `RESEAU=1` (tablet on the same Wi-Fi), `PAYS=CM`, `PORT=8001`, `AGENTS=tous`.
`python3 interface/serveur.py` also reads `CLE_API.txt` (unless `--mode` or `--fournisseur` is given). `CLE_API.txt` is
excluded from Git: the key never goes to GitHub. With an online model, fictitious patients only (reminded at start-up).

### Detailed commands

On Linux or macOS, replace `python` with `python3` if needed.

```bash
# Simulated mode: no AI, nothing to install (Python 3.10+)
python main.py                                   # consultation (pregnancy)
python main.py --scenario scenarios/crise.json   # crisis (communicable disease, teleconsultation, institutions)
python main.py --scenario scenarios/allergie.json   # another patient, another course of events
python main.py --ordre aleatoire --graine 3      # random order of the agents' turns
python main.py --langue en                       # jurist findings in English
python main.py --pays CM                         # the jurist applies Cameroonian law (consultations)
python main.py --pictogrammes paquet.module:Classe   # plug in agent 1's pictogram engine

# Real agents through an online API, no powerful machine needed (free tiers; fictitious patients only)
export GEMINI_API_KEY=...          # free key: https://aistudio.google.com/apikey   (Windows: $env:GEMINI_API_KEY="...")
export GROQ_API_KEY=...            # free key: https://console.groq.com/keys
python main.py --fournisseur gemini --secours groq,openrouter --donnees-fictives
python interface/serveur.py --fournisseur gemini --secours groq --donnees-fictives     # demo interface
python interface/serveur.py --agents-ia tous                                          # the model drives every agent

# Real agents with a local model (Ollama: https://ollama.com)
ollama pull qwen3:8b
pip install -r requirements.txt
python main.py --mode ollama --modele qwen3:8b
python main.py --mode openai --url http://localhost:8080/v1 --modele qwen2.5-7b-instruct   # llama.cpp, LM Studio, vLLM…

# Evaluate the agents (safety must stay at 100 %, capability measured)
python evaluer_agents.py
python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3 --sans-repli

# Tests (200+) and checks of the knowledge base
python -m pytest -q
python kb/outils/verifier_kb.py      # consistency of sources / provisions / rules / gaps / questions
python kb/outils/evaluer_recherche.py
python kb/outils/construire_index.py # export for a vector database
ollama pull bge-m3 && python kb/outils/construire_vecteurs.py   # vector base (meaning), local
python kb/outils/evaluer_recherche.py --comparer --encodeur ollama:bge-m3   # keywords vs meaning vs hybrid
python main.py --recherche ollama:bge-m3          # agents with hybrid search
python kb/outils/telecharger_sources.py   # downloads the official texts and freezes their SHA-256 (network needed)

# Tamper-evident journal and readable HTML page
python verifier_journal.py sortie/journal.json --falsifier 10
python exporter_journal.py sortie/journal.json

# Documents (need: pip install playwright pypdf && python -m playwright install chromium)
python pictogrammes/exporter.py --pdf            # SVG + docs/pictogrammes/Planche_pictogrammes.pdf
python pictogrammes/livret.py --pdf              # docs/pictogrammes/Livret_test_pictogrammes.pdf + answer key
python outils/generer_rapport.py                 # docs/soumission/ (detailed documentation + gap analysis)
```

Choose a model that **can call tools** (`qwen3:8b`, `llama3.1:8b`). Technical guide of the agents:
[`docs/technique/ARCHITECTURE_AGENTS.md`](docs/technique/ARCHITECTURE_AGENTS.md).

## Robustness: formal methods

Verdicts never come from the language model. They come from a rule engine whose semantics is written down:
- three-valued logic (an unknown fact is never assumed safe);
- lattice of verdicts (the strictest wins);
- deny by default;
- background knowledge (a man is not pregnant).

A **formal specification** (`kb/specification_formelle.json`, 32 requirements) states what must be prevented and what must
remain possible. It is checked for **all** possible inputs by two independent methods: exhaustive enumeration on the real
engine, and an SMT-solver proof (Z3). A **runtime monitor** checks ten safety invariants on the journal (e.g. no message to
the patient without human validation). It runs on hundreds of automatically generated event sequences, attacks included.
This verification found defects that were then fixed. Method, literature and traceability:
[`docs/technique/METHODES_FORMELLES.md`](docs/technique/METHODES_FORMELLES.md); results:
[`docs/technique/RAPPORT_VERIFICATION_FORMELLE.md`](docs/technique/RAPPORT_VERIFICATION_FORMELLE.md).

```bash
pip install -r requirements-dev.txt          # pytest and z3-solver
python outils/verifier_formel.py             # enumeration, SMT proofs, exploration, report (2 to 3 minutes)
python outils/verifier_formel.py --mutations # + mutation analysis (longer)
python outils/verifier_formel.py --journal sortie/journal.json   # monitor an existing journal
```

Continuous integration (`.github/workflows/ci.yml`) re-runs the tests, the formal verification and the evaluation bench on
every change.

## The jurist's verdicts

| Verdict | Meaning | Who can override |
|---|---|---|
| CONFORME (compliant) | the decision can go ahead (with its obligations) | — |
| PREUVES_INSUFFISANTES (insufficient evidence) | information is missing: an unknown is never assumed safe | nobody: the information is needed |
| A_REVOIR (to review) | real issue, but a matter of human judgement | the doctor, in writing, by name |
| BLOQUE (blocked) | a binding rule (law, regulator standard) forbids it | nobody |

Only a binding source can **block**; a clinical recommendation can at most ask for a **review**. Each finding cites the
provision of the base, the article, the official link and the verification level.

## Core knowledge base (`kb/`)

| File | Content |
|---|---|
| `sources.json` | 47 sources: UAE (federal laws, DoH, DHA, MOHAP, AI charter and strategy), Cameroon (practice of medicine, personal data, disability, ethics code, pharmacy, criminal code), global examples (UN, WHO, EU, FDA, NHS, ISO, African Union), ITU references (Y.3172, AI Readiness Framework 2.0) |
| `fiches.jsonl` | 139 provisions (article, plain-language summary, short quote, themes, legal basis) |
| `regles_uae.json` · `regles_cm.json` | jurist rules for the UAE and for Cameroon (`--pays CM`), each citing its provisions; typed signature of the variables and 3 axioms (background knowledge) |
| `specification_formelle.json` | 32 safety and utility requirements that the rules must satisfy for all inputs (checked by `outils/verifier_formel.py`) |
| `lacunes.json` | 9 gaps: what the texts say, what is missing, global examples, MEDIMCOM's response |
| `questions_test.jsonl` | 65 questions (English and French) with the expected provision |
| `index/chunks.jsonl` | 148 self-contained chunks with metadata, ready for a vector database |
| `InputDocs/` | the same base in the format of the ITU reference ingestion code |
| `outils/` | checking, evaluation, export, download with fingerprints |

Verification levels: `official_text` (read on the official site), `secondary_source` (known from a law firm or the press:
get the official text), `to_confirm`. 33 sources are read on the official text, 11 known through secondary sources, 3 to
confirm. The Arabic text of the laws prevails.

Measured search (BM25 with no dependency, French → English lexicon) on 65 questions: recall@1 = 0.80 · recall@3 = 0.89 ·
recall@5 = 0.97 · MRR = 0.86 (measured on 9 November 2026).

## Extended knowledge base (`base_v2`)

**Using it:** download `base_v2.zip` from the Releases page of the repository
(https://github.com/baudouin2/MEDIMCOM-IA/releases) and unzip it at the root so that the folder is `MEDIMCOM_IA/base_v2/`
(check: `ls base_v2/01_base_juridique base_v2/02_pictogrammes`). It is found automatically at start-up, with no option:
first the `MEDIMCOM_BASE` variable, then `MEDIMCOM_IA/base_v2/`, then `~/MEDIMCOM_base_v2/`. `--base aucune` goes back to
the internal base only; `MEDIMCOM_PICTOS=demo` keeps the demo lexicon.

**What it brings to the agents.** The translator uses the consultation vocabulary and the images of the base
(`medimcom/base_v2.py`, same safety rules: negation, "at most", numbers, doses); the `consulter_base` tool of the agents
returns, in addition to the jurist's provisions, the articles of the official texts and the sections of the WHO fact
sheets, with their links; the patient's palette gets the illustrated concepts. The jurist's verdicts still come only from
its verified rules in `kb/`.

### Building the knowledge base on your computer

**Version 2 (recommended)**: larger base, filtered for health / consultation, organised according to the hackathon
requirements.

```bash
python outils/constituer_base_v2.py --audit-pictos                      # 1. inventory of the ARASAAC labels (fast, no images)
python outils/constituer_base_v2.py                                     # 2. full base, from scratch -> ~/MEDIMCOM_base_v2 (--ancienne-base optional)
python outils/constituer_base_v2.py                                     # 3. run again after placing PDFs in entrees_manuelles/
```

| Folder produced | Content |
|---|---|
| `01_base_juridique/` | 87 official, open documents (catalogue `kb/corpus/catalogue_sources.json`): `A_cameroun/` (health, AI-digital-cybersecurity, data, institutions, disability), `B_international/` (UN human rights, AI, WHO, disability, data, medical ethics, ITU), `C_afrique_regional/` (African Union), `D_emirats_pays_hote/`. For each document: `fiche.md`, `texte.md`, `articles.jsonl`, `original.pdf`. Plus `matrice_exigences.md` (requirement × jurisdiction, gaps), `index_sources.csv`, `corpus_rag.jsonl` |
| `02_pictogrammes/` | ARASAAC, Mulberry, OpenMoji filtered for the consultation: 1,287 concepts in 30 categories organised by what one wants to say (welcome, ask, describe a pain, give an instruction, advise, reassure, prescribe a treatment, an operation, a diet, a healthy lifestyle); compound concepts = sequences of pictograms (`kb/corpus/vocabulaire_consultation.json`); `catalogue.csv`, `notions.csv`, `planches/`, `audit/rejets.csv`, `LICENCES.md` |
| `03_references_medicales/` | WHO fact sheets (fr / en / ar) split by section, MedlinePlus summaries, Wikidata fr / en / ar lexicon with ICD-10 codes — built from scratch |
| `04_jeu_de_donnees_assistant/` | fictitious cases for the medical assistant |
| `05_jeux_entrainement/` | datasets ready to train or evaluate a model: images ⇄ labels (imagefolder format), pictograms ⇄ fr/en sentences, legal classification and retrieval, WHO questions and answers, lexicon; `FICHE_DE_DONNEES.md` |
| `a_telecharger_a_la_main.md`, `entrees_manuelles/` | documents to obtain by hand; place `<ID>.pdf` and run again |
| `journal.json` | address, date and SHA-256 fingerprint of every document and image |

**All pictograms, all domains**: `--tous-pictos` takes the complete catalogue of ARASAAC, Mulberry and OpenMoji (more than
10,000 images; parallel download, `--paralleles 6`, resumed where it stopped). Images outside health go to "All words"
(`90_vocabulaire_general`) and "Emojis, symbols" (`91_emojis_symboles`), sorted by popularity; content marked sexual or
violent by ARASAAC is kept in `98_sensible`, never in the patient's tabs, only through search. The translator uses the
exact French keyword of these images when the consultation vocabulary has nothing ("voiture", "école"); never an English
label, never sensitive content.

Pictogram volume target: `--objectif-pictos 3000` (default); if the strict selection is not enough, the script widens step
by step without ever lifting the blacklist, and says in `02_pictogrammes/LISEZMOI.md` whether the target was reached.
Pictogram sorting is set in `kb/corpus/filtres_pictogrammes.json` (whitelist, blacklist, caps); see `kb/corpus/LISEZMOI.md`.

```bash
python outils/evaluer_base_v2.py      # figures: translation, legal retrieval, WHO retrieval -> base_v2/06_evaluation/
```

**Version 1** (still available): `python outils/constituer_base.py` produces the old tree
`1_textes_juridiques/ 2_pictogrammes/ 3_jeu_de_donnees_assistant/`.

ARASAAC images are downloaded automatically; Tawasol, Mulberry or Sclera images are placed in
`pictogrammes/bases/images/<base>/<ID>.png` (see `pictogrammes/bases/LISEZMOI.md`). SantéBD stays blocked without written
agreement. Running the script again updates everything without downloading anything twice.

### Clinical safety of prescriptions

The jurist compares each prescription with the patient record (pregnancy, age, kidney, liver, ulcer, anticoagulant,
allergy) and with the daily dose, from official labels quoted word for word (tramadol, paracetamol, ibuprofen, aspirin,
amoxicillin, metformin, misoprostol). Any other medicine gets "insufficient evidence". The assistant immediately says why
not to prescribe as is and proposes an alternative checked by the jurist for this patient. Details, levels and limits:
`docs/technique/SECURITE_CLINIQUE.md`.

### Hybrid search: keywords + meaning (optional, local)

The agents search **four collections**: the jurist's verified provisions (`kb/`), articles of the official texts, sections
of the WHO fact sheets, and **pictograms** (fr / en / ar labels, synonyms, ARASAAC keywords, category).

| Step | How |
|---|---|
| Splitting | official texts: by article ("Article 12", "Art. 3"), then windows of 1,800 characters with 200 of overlap; WHO: by section; `kb/`: one provision per chunk; pictograms: one card per concept |
| Context | each chunk is encoded preceded by its title and its article ("Law 2/2019 — Article 13") |
| Vectorisation | **local** embedding model (no data leaves, no key): `fastembed:e5` = multilingual-e5-large (1,024 dim., fr/en/ar), `fastembed:mpnet` (faster), or `ollama:bge-m3` |
| Similarity | cosine on normalised vectors |
| Fusion | the 30 best by keywords (BM25) and the 30 best by meaning, merged by reciprocal ranks (RRF, k = 60); for pictograms, spelling similarity (typos) is added and the exact label comes first |
| Traceability | each result says why it is there: keyword rank, meaning rank and cosine |
| Safety | search serves to **cite** and to **propose**: the jurist's verdict remains that of the rule engine; a close pictogram is never inserted unless the doctor chooses it |

```bash
pip install -r requirements-vecteurs.txt                       # once: fastembed (ONNX, no PyTorch) + numpy
python outils/vectoriser_base.py                               # encode everything (resumes where it stopped) -> base_v2/07_vecteurs/
python interface/serveur.py --fournisseur xai --effort low --donnees-fictives --recherche fastembed:e5
python outils/evaluer_base_v2.py --recherche fastembed:e5      # compares keywords, meaning and hybrid
```

What the agents do with it: `consulter_base` (all agents) becomes hybrid; the `chercher_pictogrammes` tool lets the
translator and the assistant find an image for a missing word ("shortness of breath", "dizziness"); on each proposal, the
pictograms close to the untranslated words are offered to the doctor, who clicks to add them; the patient and the doctor
find a pictogram by meaning in their search bar. If the model is missing, everything continues with BM25 and the journal
says so. `--exporter` also writes the vectors in the `{id, text, metadata, embedding}` format (Chroma, ITU base).

## Organisation

```
MEDIMCOM_IA/
├── README.md (main page) · README_FR.md (this detailed guide) · SUBMISSION.md (submission map) · requirements.txt
├── CLE_API.exemple.txt   template of the key file; CLE_API.txt (your key, excluded from Git) is copied from it at first start
├── lancer_local.sh       one-command start (key of CLE_API.txt, Ollama or written rules; diagnostic)
├── lancer_demo.sh        starts everything needed to film the demo
├── main.py               runs a consultation or a crisis (terminal)
├── evaluer_agents.py     evaluation bench (safety invariants + expected outcomes)
├── verifier_journal.py · exporter_journal.py   tamper-evident journal, readable HTML page
├── medimcom/             the core
│   ├── agents.py         Agent (observe → reason → act): Traducteur, Assistant, Juriste,
│   │                     institutions AutoriteSante, Hopital, CelluleCrise
│   ├── dossier.py        shared, versioned record; named maintenance of a decision
│   ├── messagerie.py     typed direct messages: request, information, alert, proposal, disagreement
│   ├── orchestrateur.py  releases the events, lets the agents act until stable
│   ├── journal.py        chained journal (SHA-256) + verification
│   ├── regles.py · base.py   jurist's rule engine (formal semantics) · knowledge base (citations, BM25, gaps)
│   ├── base_v2.py        plugs the extended base into the agents
│   ├── formel.py · formel_smt.py   exhaustive verification of the rules · SMT proofs (Z3), mutation analysis
│   ├── surveillance.py · exploration.py   journal monitor (R1 to R10) · automatic exploration of the system
│   ├── cerveaux.py       CerveauSimule (no AI) · CerveauOllama · CerveauOpenAI (Groq, Gemini, OpenRouter, Mistral, xAI, Anthropic, OpenAI)
│   ├── cle_api.py        reads CLE_API.txt: provider recognised from the key
│   ├── documents.py      documents sent by the patient (text, PDF, photo), facts kept unconfirmed
│   ├── session.py · evaluation.py · mandats.json
│   ├── pictogrammes.py   interface of the pictogram engine + demo lexicon
│   └── bibliotheque.py   demo SVG icons, fr / en / ar labels
├── interface/            serveur.py (no dependency) · web/ (React interface: src/, compiled dist/) · classique/ (simple HTML pages)
├── pictogrammes/         exporter.py, livret.py, analyse_tests.py, svg/ (46 files), test/ (answer key, answer template)
├── kb/                   core knowledge base (see above) + outils/ + InputDocs/ (format of the ITU reference code)
├── base_v2/              extended knowledge base — release file, not in Git
├── scenarios/            grossesse.json · crise.json · allergie.json — each with its expected outcomes
├── tests/                automated tests (python -m pytest -q)
├── outils/               verifier_formel.py (formal verification) · constituer_base_v2.py (full base on your computer) · constituer_base.py (version 1) · jeu_assistant.py (dataset)
│                         · generer_rapport.py · generer_fiche.py (one-page project sheet) · diagnostic_modele.py
├── donnees/              presentations_cliniques.json (10 reasons for consultation, to be validated by a doctor)
├── docs/
│   ├── GUIDE_CLE_API.md  plugging in a model: key, free and paid providers, security, failures
│   ├── soumission/       MEDIMCOM_IA_Technical_Report.pdf/.docx (official template) · MEDIMCOM_IA_Technical_Documentation.pdf · MEDIMCOM_IA_Gap_Analysis.pdf · KB_reference_links.md
│   ├── equipe/           REPARTITION.md · SUIVI_EXIGENCES.md · NOTES_SESSIONS_UIT.md · MEDIMCOM_IA_Fiche_projet.pdf
│   ├── technique/        ARCHITECTURE_AGENTS.md · CONTRAT_AGENT1.md · METHODES_FORMELLES.md · RAPPORT_VERIFICATION_FORMELLE.md · SECURITE_CLINIQUE.md
│   ├── pictogrammes/     Planche_pictogrammes.pdf · Livret_test_pictogrammes.pdf · PROTOCOLE_TESTS.md
│   ├── video/            MEDIMCOM_IA_Script_demo_pas_a_pas.docx · SCRIPT_VIDEO.md · specimen_previous_prescription.pdf · installer_obs.sh
│   └── captures/         doctor and patient screens
└── archives/             outdated working versions (excluded from Git)
```

## Known limitations

- The model-driven modes (Ollama, OpenAI-compatible APIs) are implemented; their safeguards are tested with fake models, including a "chaotic" model that never breaks the safety invariants. Reference results come from the written policies. **To do: `python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3 --sans-repli`**.
- Only 7 medicines are checked clinically (see above); the clinical rules (NSAIDs, misoprostol…) are examples from public sources: **to be validated by a doctor** and replaced by the UAE formulary. Adult doses only. Practitioners and the unregistered medicine are fictitious.
- The doctor screen is fully available in French; the English and Arabic versions of the screen are partial.
- 11 sources are known only through a secondary source and 3 remain to confirm (mostly Cameroonian texts); Arabic originals are not yet integrated; the DoH AI standard and the DHA AI policy are due for revision: to re-check.
- Pictograms have not yet been tested with deaf users (protocol ready).

⚠️ Hackathon prototype, fictitious data: not a medical device and not legal advice.

## Licence

Code: Apache 2.0 (`LICENSE`). ARASAAC pictograms remain under CC BY-NC-SA 4.0 (non-commercial); Mulberry CC BY-SA 2.0 UK;
OpenMoji CC BY-SA 4.0; details of third-party content in `NOTICE.md`.
