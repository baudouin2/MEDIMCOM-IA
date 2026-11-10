# MEDIMCOM IA — pictogram-based medical consultation with autonomous agents and a jurist (local prototype)

Team **ShifaMiko** (Baudouin Nkana Bilong, Franck Ndonkou, Fotsing Engoulou — Université de Yaoundé I) ·
ITU **AI for Good Lab Hackathon – United Arab Emirates** · submission of 10 November 2026.

- **Submission map** (every item of the call → file): [`SUBMISSION.md`](SUBMISSION.md)
- **Technical report** (official template, 5 pages): [`docs/soumission/MEDIMCOM_IA_Technical_Report.pdf`](docs/soumission/MEDIMCOM_IA_Technical_Report.pdf) ([Word](docs/soumission/MEDIMCOM_IA_Technical_Report.docx)) ·
  **Detailed technical documentation** (agents, rules, auditability): [`docs/soumission/MEDIMCOM_IA_Technical_Documentation.pdf`](docs/soumission/MEDIMCOM_IA_Technical_Documentation.pdf) ·
  **Gap analysis**: [`docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf`](docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf)
- **Knowledge base for the ITU reference ingestion code**: [`kb/InputDocs/`](kb/InputDocs/)
- **Extended knowledge base `base_v2`** (87 official documents, ~1,300 pictogram concepts, WHO fact sheets): published
  separately because of its size — download and install it as described in [section 4.2](#42-extended-knowledge-base-base_v2)
- **Detailed guide** (every command, building the knowledge base, hybrid search, formal methods): [`README_FR.md`](README_FR.md)

> Prototype with **fictitious patients only**. Not a medical device and not legal advice. The Arabic text of UAE
> legislation prevails over the English versions used here.

## 1. What it does

A doctor and a **deaf patient with limited literacy** communicate through **pictograms**. Autonomous agents work around a
shared consultation record, talk to each other through typed messages, and write every step to a tamper-evident journal.

**How an agent works.** Every agent — translator, assistant, jurist, institutions — has the same architecture: a
**language model drives it** in a reason-and-act loop (it reads the record and its messages, decides what to do, and calls
its own tools), and a **written, verified policy** takes over at once if the model fails, times out or runs out of quota.
Each agent's limits are enforced in its tools, not only in its instructions. Which agents use the model is a setting
(`AGENTS=assistant` by default, `AGENTS=assistant,juriste` or `AGENTS=tous`); see section 6.

| Agent | Role |
|---|---|
| **Translator** (agent 1) | text ⇄ pictograms. Refuses to guess: a word without a safe pictogram is shown to the doctor "without pictogram", never replaced by a wrong image. Reads the context (instruction, question, narrative…) and corrects typing and dictation errors. Never removes a negation, a limit, a number, a dose or a medicine name. |
| **Assistant** (agent 3) | keeps the patient state (confirmed or not), spots missing facts, proposes questions and sourced treatment options, checks every medicine against the patient (pregnancy, age, allergies, current treatments), reads documents (photos of prescriptions, receipts). Uses a language model if one is configured; otherwise a deterministic watch does the essential. |
| **Jurist** (agent 2) | an agent whose **verdicts come from a deterministic rule engine** grounded in UAE law and regulator standards (DoH, DHA, MOHAP), which it calls as tools (`verifier_prescription`, `verifier_envoi_patient`, `verifier_partage_donnees`, `obligations_etat_patient`, `signaler_lacune`, plus knowledge-base search). When a model drives it, the model decides what to check and when, writes the explanations, answers the institutions' legal questions and links gaps — but **cannot change a verdict**. Verdicts cite the provision, the article, the official link and its verification level. Re-checks on its own when the patient's state changes; crisis advisor; detects legal gaps. Cameroonian law with `--pays CM`. |
| **Institutions** (crisis scenario) | health authority, hospital, crisis cell: fragmented information, own mandates, **no access to the patient record**, measures only with a checked binding legal basis. |

**The doctor always decides.** Nothing reaches the patient without the doctor's validation and a compliant verdict of the
jurist. A "to review" verdict can be overridden by a named doctor with a written justification; a "blocked" one cannot.

| Verdict | Meaning | Who can override |
|---|---|---|
| `CONFORME` (compliant) | the decision can go ahead (with its obligations) | — |
| `PREUVES_INSUFFISANTES` (insufficient evidence) | information is missing: an unknown is never assumed safe | nobody: the information is needed |
| `A_REVOIR` (to review) | real issue, but a matter of human judgement | the doctor, in writing, by name |
| `BLOQUE` (blocked) | a binding rule (law, regulator standard) or the system's safety safeguard forbids it | nobody |

## 2. Quick start (two minutes)

Requirements: **Python 3.10+** (Linux or macOS; on Windows use WSL or Git Bash). The compiled web interface is included:
nothing else to install for the basic use.

```bash
# 1. optional — choose a language model: put ONE API key in CLE_API.txt (one line):
#      CLE=your_key
# 2. optional — extended knowledge base: unzip base_v2.zip at the root (section 4.2)
# 3. start
bash lancer_local.sh
# 4. open the private DOCTOR link printed in the terminal; the PATIENT screen is http://127.0.0.1:8000/patient
```

At start-up the terminal says which provider and model are used, e.g.

```
✓ CLE_API.txt: Groq (online) — free tier — model qwen/qwen3.8-27b
  Reminder: messages are sent to the provider, outside the country: FICTITIOUS patients only (UAE Federal Law No. 2 of 2019, Art. 13).
DOCTOR screen (private link, do not share): http://127.0.0.1:8000/medecin?jeton=…
PATIENT screen: http://127.0.0.1:8000/patient
```

### The API key file `CLE_API.txt`

One line, `CLE=your_key`. The provider is **recognised from the beginning of the key**, free or paid:

| Key starts with | Provider | Price | Default model |
|---|---|---|---|
| `gsk_` | Groq | free tier (quota per minute / day) | `qwen/qwen3.8-27b` (open source) |
| `sk-or-` | OpenRouter | free ":free" models | `google/gemma-4-31b-it:free` |
| `AIza` | Google Gemini | free tier | `gemini-3.8-flash` |
| (no prefix) | Mistral AI — add a line `FOURNISSEUR=mistral` | free tier | `mistral-large-latest` |
| `xai-` | xAI (Grok) | paid | `grok-4.7` |
| `sk-ant-` | Anthropic (Claude) | paid | `claude-haiku-5-5` |
| `sk-` / `sk-proj-` | OpenAI (GPT) | paid | `gpt-5.4-mini` |

Optional extra lines: `MODELE=…` (another model), `CLE_SECOURS=…` (key of another provider, used when the first one fails:
quota, outage, no credits), `PATIENTS_FICTIFS=non` (switches the online model off). Without a key, the agents run on their
written, formally verified rules — everything works, less flexibly. If the model named is not available for the key, a model
of the same family is chosen and the terminal says so.

`CLE_API.txt` is **excluded from Git** (`.gitignore`); the repository only contains `CLE_API.exemple.txt`. The key is never
printed. A copy is kept in `~/.config/medimcom/env` (readable by you only) so it survives a new version of the folder.
Full guide: [`docs/GUIDE_CLE_API.md`](docs/GUIDE_CLE_API.md).

### Other ways to start

```bash
bash lancer_local.sh ollama            # open-source model qwen3:8b ON this computer: no key, nothing leaves (≥ 8 GB RAM)
VISION=1 bash lancer_local.sh ollama   # + qwen3-vl:8b to read photos of prescriptions, receipts, medicine boxes
bash lancer_local.sh sans-ia           # written rules only (no language model)
AGENTS=assistant,juriste bash lancer_local.sh   # the model also drives the jurist (AGENTS=tous: every agent)
bash lancer_local.sh cle               # shows which provider / model CLE_API.txt will give
bash lancer_local.sh diagnostic        # "model unavailable"? tests Internet, certificates, key, quota, model, real call
RESEAU=1 bash lancer_local.sh          # patient tablet on the same Wi-Fi (trusted network only)
PAYS=CM bash lancer_local.sh           # the jurist applies Cameroonian law
bash lancer_demo.sh                    # everything needed to film the demo (3 servers + journal)

python3 interface/serveur.py --demo scenarios/grossesse.json   # step-by-step demo ("Next step" button)
python3 interface/serveur.py --demo scenarios/crise.json       # crisis scenario with the institutions' board
python3 main.py --scenario scenarios/crise.json                # terminal run of a scenario, no interface
```

## 3. The two screens

- **Doctor screen** (private link with a per-run secret token): patient record with **automatic saving** (each field is
  used by the agents as soon as it is left); conversation where each message is shown with its pictogram translation and
  validated, corrected (pictogram editor), rephrased, cancelled, removed from the patient screen or hidden; agents panel
  (assistant questions to send or refuse, suggestions, prescription with the jurist's analysis, law texts readable in one
  click, gaps, crisis); documents of the patient; dictation; doctor language FR / EN / AR; readable **audit journal** with a
  responsibility report.
- **Patient screen** (tablet): text-free pictograms (optional fr / en / ar labels), 20 tabs, search by word or meaning,
  **Combine** (e.g. HEAD + PAIN in one image), a guided "Describe my pain" (where, how, how much, since when, symptoms,
  treatment), "I don't understand", emergency button, **"My prescription"** (pictograms + PDF), and **"Send a document"**
  (photo or file: prescription, medicine box, receipt, X-ray, lab result).

## 4. Knowledge base

### 4.1 Core base in the repository (`kb/`)

- `sources.json` — 47 sources: UAE (federal laws, DoH, DHA, MOHAP, AI charter and strategy), Cameroon, global examples
  (UN, WHO, EU, FDA, NHS, ISO, African Union), ITU references (Y.3172, AI Readiness Framework 2.0); 33 read on the
  official text, 11 known through secondary sources, 3 to confirm.
- `fiches.jsonl` — 139 provisions (article, plain-language summary, short quote when read, themes, legal basis).
- `regles_uae.json` · `regles_cm.json` — jurist rules (UAE and Cameroon), each citing its provisions; typed signature and
  background axioms. `specification_formelle.json` — safety and utility requirements checked for all inputs.
- `lacunes.json` — 9 policy and standards gaps with global examples; `questions_test.jsonl` — 65 retrieval questions.
- `InputDocs/` — the same base **in the format of the ITU reference ingestion code** (`AI_Strategies/`, `AI_Use_Cases/`,
  `Inputs.md`): `python -m server.knowledge.ingest --dir kb/InputDocs --reset`. `index/chunks.jsonl` — 148 vector-ready chunks.

Keyword search (BM25, no dependency) on 65 test questions: recall@1 = 0.80, recall@3 = 0.89, recall@5 = 0.97, MRR = 0.86
(`python kb/outils/evaluer_recherche.py`). Optional hybrid search (keywords + meaning, local embedding model):
`pip install -r requirements-vecteurs.txt`, then `python outils/vectoriser_base.py` and `--recherche fastembed:e5`.

### 4.2 Extended knowledge base (`base_v2`)

`kb/` is enough to run everything. `base_v2` makes the agents much richer; it is too large for the Git history and is
published as a release file.

| Folder of `base_v2/` | Content |
|---|---|
| `01_base_juridique/` | **87 official, open documents** (UAE host country, Cameroon, African Union, UN, WHO, ITU…), each as `fiche.md` (metadata, official link), `texte.md`, `articles.jsonl` (split by article) and `original.pdf`; plus a requirement × jurisdiction matrix and `corpus_rag.jsonl` |
| `02_pictogrammes/` | ARASAAC, Mulberry and OpenMoji pictograms filtered for medical consultation: **1,287 concepts in 30 categories** (welcome, ask, describe a pain, give an instruction, prescribe…), with `catalogue.csv`, `notions.csv` and `LICENCES.md` |
| `03_references_medicales/` | WHO fact sheets (fr / en / ar) split by section, MedlinePlus summaries, Wikidata fr / en / ar lexicon with ICD-10 codes |
| `04_jeu_de_donnees_assistant/` · `05_jeux_entrainement/` | fictitious cases for the assistant; datasets to train or evaluate a model (images ⇄ labels, pictograms ⇄ sentences, legal retrieval, WHO Q&A), with a data sheet |
| `journal.json` | address, date and SHA-256 fingerprint of every document and image |

**Install it (once):**

```bash
# 1. download base_v2.zip from the Releases page of this repository:
#    https://github.com/baudouin2/MEDIMCOM-IA/releases
# 2. unzip it at the root of the project, so that the folder is MEDIMCOM_IA/base_v2/
unzip base_v2.zip -d .
ls base_v2/01_base_juridique base_v2/02_pictogrammes >/dev/null && echo "base_v2 OK"
# 3. start as usual: the base is found automatically (no option needed)
bash lancer_local.sh
```

The base is looked for in this order: the `MEDIMCOM_BASE` variable, `MEDIMCOM_IA/base_v2/`, then `~/MEDIMCOM_base_v2/`
(`--base aucune` runs without it). With `base_v2`, `lancer_local.sh` also installs the optional local embedding model for
search by meaning.

**What it changes for the agents:** the translator uses the 1,287-concept consultation vocabulary and its images (same
safety rules: negations, "at most", numbers, doses and medicine names are never lost); the patient's palette gets all the
illustrated concepts; the `consulter_base` tool of every agent also returns the articles of the 87 official texts and the
sections of the WHO fact sheets, with their links. The jurist's verdicts still come only from its verified rules in `kb/`.

**Rebuild it from scratch** (network needed, everything downloaded from the official sources with SHA-256 fingerprints):
`python outils/constituer_base_v2.py` → `~/MEDIMCOM_base_v2` (details in [`README_FR.md`](README_FR.md)).
Pictogram licences: ARASAAC CC BY-NC-SA 4.0 (non-commercial), Mulberry CC BY-SA 2.0 UK, OpenMoji CC BY-SA 4.0 — see
`base_v2/02_pictogrammes/LICENCES.md`.

## 5. Robustness, audit and formal methods

- **Tamper-evident journal**: every reasoning step, action, message and verdict, SHA-256 chained.
  `python verifier_journal.py sortie/journal.json --falsifier 10` shows that a modified line is detected;
  `python exporter_journal.py sortie/journal.json` gives a readable HTML report with **responsibility chains** (who proposed,
  what was checked and on which basis, who decided) and **failures** of the AI and of the law (model unavailable, check
  caught by the safety net, gap, refused crisis measure).
- **Formal verification** of the jurist's rules for *all* inputs (exhaustive enumeration on the real engine + SMT proofs with
  Z3), a runtime monitor of 10 safety invariants on the journal, automatic exploration with attacks, mutation analysis:
  `python outils/verifier_formel.py` — see `docs/technique/METHODES_FORMELLES.md` and `RAPPORT_VERIFICATION_FORMELLE.md`.
- **Evaluation bench**: `python evaluer_agents.py` (100 % safety required, capability measured).
- **Tests**: `python -m pytest -q` (200+ tests); continuous integration in `.github/workflows/ci.yml`.

## 6. Limitations (read before use)

**Medicines and clinical content**
- Only the **medicines documented in the knowledge base** are checked clinically: paracetamol, ibuprofen, aspirin,
  amoxicillin, metformin, tramadol and misoprostol (plus one fictitious unapproved product used in tests). Any other medicine
  gets **insufficient evidence** ("medicine not in the knowledge base: marketing approval cannot be checked"); this verdict
  cannot be overridden, so such a prescription cannot reach the patient through the system. Adding a medicine means adding
  its official label as provisions and its rules (`kb/`), then re-running the checks.
- Clinical rules come from public official labels (FDA / DailyMed) and serve as **examples to be validated by a doctor** and
  replaced by the UAE formulary. Dose checks use **adult** maximum daily doses; there is no weight-based paediatric dosing.
  Interactions are only checked for the cases written in the rules (e.g. anticoagulant + NSAID).
- Treatment options proposed by the assistant are symptomatic (pain, fever) and always checked by the jurist; the assistant
  never diagnoses.

**Language and pictograms**
- The doctor's input is processed in **French** (English supported for translation; Arabic labels on the patient side, to be
  reviewed by a native speaker). The doctor screen is complete in French; its English and Arabic versions are partial.
  Context reading and typo correction are rule-based: unusual phrasing may be read as ambiguous, and the doctor is then
  asked to confirm.
- The pictogram vocabulary is finite: 46 demo icons, or 1,287 consultation concepts with `base_v2`. Missing words are shown
  "without pictogram" (by design). Pictograms have **not yet been tested with deaf users** (protocol ready:
  `docs/pictogrammes/PROTOCOLE_TESTS.md`).

**Language models**
- By default only the **assistant** is driven by the language model (response time, free-tier quotas, reproducible demos);
  the other agents run their written policy. `AGENTS=tous` lets the model drive every agent, the jurist included. In every
  case the **jurist's verdicts come from the rule engine**, never from the model: a legal verdict must be reproducible,
  auditable and provable, and a model can invent a legal provision. Model-driven agents are tested with simulated and
  deliberately chaotic models; their capability with a real model is not yet fully measured.
- With an online provider (Groq, Gemini, OpenRouter, Mistral, xAI, Anthropic, OpenAI) the messages leave the computer and the
  country: **fictitious patients only** (UAE Federal Law No. 2 of 2019, Art. 13). For real data use a local model
  (`bash lancer_local.sh ollama`) or an authorised in-country host.
- Free tiers have quotas; model names change (an automatic replacement is chosen and reported). Anthropic and OpenAI support
  was tested with simulated servers only (`python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3 --sans-repli`
  measures a real model).
- Reading **photos** needs a model that sees images (online vision model, or `VISION=1` with Ollama). Text and text-PDF
  documents are read without a model. Extracted facts enter the record as **unconfirmed**.
- **Dictation**: in the browser (Chrome / Edge, audio transcribed by Google) or on the server with a Groq (Whisper) or xAI
  key — fictitious patients only.

**Prototype infrastructure**
- One consultation per running server: "New consultation" resets it for everyone. The consultation lives in memory; the
  journal can be exported from the Journal page.
- No user accounts and no HTTPS locally: the doctor screen is protected by a secret token, the patient screen is open to the
  network when `RESEAU=1` is used (trusted network only). Patients can upload at most 10 documents per consultation.

**Knowledge base**
- 11 sources are known through secondary sources and 3 remain to confirm; Arabic originals are not yet integrated; some
  regulator documents are due for revision (re-check dates). Cameroonian rules rely largely on secondary sources: a rule only
  **blocks** when it cites a law whose content was read.

## 7. Repository structure

```
MEDIMCOM_IA/
├── README.md · README_FR.md (detailed guide) · SUBMISSION.md · LICENSE · NOTICE.md
├── CLE_API.exemple.txt     template of the key file (CLE_API.txt = your key, excluded from Git)
├── lancer_local.sh         one-command start (key, Ollama or rules; diagnostic)
├── lancer_demo.sh          everything needed to film the demo
├── main.py · evaluer_agents.py · verifier_journal.py · exporter_journal.py
├── medimcom/               core: agents, rule engine (regles.py), record, messaging, journal, brains (LLM providers),
│                           context reading, safety and ethics guards, documents, prescriptions, formal methods
├── interface/              serveur.py (Python standard library) · web/ (React + TypeScript; compiled build in web/dist/)
├── kb/                     core knowledge base (+ InputDocs/ for the ITU ingestion code, index/, outils/)
├── base_v2/                extended knowledge base — release file, not in Git (section 4.2)
├── scenarios/              grossesse.json · allergie.json · crise.json — fragmented events with expected outcomes
├── tests/                  automated tests
├── outils/                 formal verification, report generation, diagnostics, knowledge-base builders
├── pictogrammes/           pictogram export, test booklet, analysis of user tests, external databases
├── donnees/                fictitious clinical presentations (to be validated by a doctor)
└── docs/                   soumission/ (report, gaps, KB links) · technique/ · pictogrammes/ · video/ · equipe/ · captures/
```

Code identifiers and some working documents (`docs/technique/`, `docs/equipe/`) are in French; code comments, terminal
messages, this page, the detailed guide `README_FR.md`, `SUBMISSION.md`, the technical report and the gap analysis are in
English.

## 8. Licence

Code: Apache 2.0 (`LICENSE`). ARASAAC pictograms remain under CC BY-NC-SA 4.0 (non-commercial use, credits shown in the
interface); Mulberry symbols CC BY-SA 2.0 UK; OpenMoji CC BY-SA 4.0; other third-party content is listed in `NOTICE.md`.
