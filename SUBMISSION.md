# MEDIMCOM IA — submission map (ITU AI for Good Sandbox Hackathon) · use case country: Cameroon

Team **ShifaMiko** (Université de Yaoundé I) · submission of 10 November 2026 · main documentation in [README.md](README.md)
(English; French version: [README_FR.md](README_FR.md)). Limitations: README.md, section 6.

This page maps every item of the call to where it is in this repository.

## Submission materials

| Material requested | Where |
|---|---|
| Technical report (max. 5 pages, official template) | [`docs/soumission/MEDIMCOM_IA_Technical_Report.pdf`](docs/soumission/MEDIMCOM_IA_Technical_Report.pdf) · Word: [`MEDIMCOM_IA_Technical_Report.docx`](docs/soumission/MEDIMCOM_IA_Technical_Report.docx) |
| GitHub repository | this repository (all code published; only obsolete drafts in `archives/` are excluded) |
| Knowledge base (policies, regulations, strategies) | [`kb/`](kb/) — 32 sources and 63 provisions used for Cameroon (47 and 139 with the UAE second country file), 10 gaps; **ready for the ITU reference ingestion code** in [`kb/InputDocs/`](kb/InputDocs/) (`AI_Strategies/`, `AI_Use_Cases/`, manifest `Inputs.md`): `python -m server.knowledge.ingest --dir kb/InputDocs --reset`; vector-ready chunks in `kb/index/chunks.jsonl` |
| Reference links of the knowledge base documents | [`docs/soumission/KB_reference_links.md`](docs/soumission/KB_reference_links.md) |
| Policy, standards and legislative gaps (annex) | [`docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf`](docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf) · source: [`kb/lacunes.json`](kb/lacunes.json) |
| Demo video (max. 7 min, if shortlisted) | script: [`docs/video/MEDIMCOM_IA_Demo_script_EN.docx`](docs/video/MEDIMCOM_IA_Demo_script_EN.docx) · plan [`docs/video/SCRIPT_VIDEO.md`](docs/video/SCRIPT_VIDEO.md) |

## Technical requirements of the call

| Requirement | Where |
|---|---|
| Agentic AI solution in a domain (healthcare) | `medimcom/agents.py` — translator, assistant, jurist; [`docs/technique/ARCHITECTURE_AGENTS.md`](docs/technique/ARCHITECTURE_AGENTS.md) |
| Alignment with the country's documents (Cameroonian law; UN CRPD and WHO IHR, binding on Cameroon; WHO, UNESCO, African Union guidance) | `kb/sources.json`, `kb/fiches.jsonl`, jurist rules `kb/regles_cm.json` (68 rules, default); second country file `kb/regles_uae.json` (`--pays AE`) |
| Interactive error scenarios released in sequenced chunks | `scenarios/grossesse.json`, `scenarios/allergie.json`, `scenarios/contagion.json` (fragmented events, expected outcomes); `python interface/serveur.py --demo scenarios/contagion.json` |
| Audit logging and reasoning traces | SHA-256 hash-chained journal (`medimcom/journal.py`); readable report with responsibility chains and AI / legal failures: `python exporter_journal.py sortie/journal.json`; tamper test: `python verifier_journal.py sortie/journal.json --falsifier 10` |
| ITU-T Y.3172 pipeline | technical report, section 4; `kb/InputDocs/AI_Use_Cases/MEDIMCOM_IA_use_case_healthcare_Cameroon.md` |
| ITU AI Readiness Framework 2.0 | technical report, section 4 (each Y.3172 node mapped to a readiness factor and dimension) |

## Evaluation criteria

| Criterion | How to check it |
|---|---|
| Knowledge base quality | `python kb/outils/verifier_kb.py` (consistency) · `python kb/outils/evaluer_recherche.py` (retrieval: recall@3, MRR on 65 questions) |
| Agent capability in error scenarios | `python evaluer_agents.py` (safety invariants + expected outcomes per scenario) |
| Gap identification | `docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf` — 10 domain gaps with global policy examples |
| Auditability | doctor screen → « Journal » (readable audit trail, sources, responsibilities) · `exporter_journal.py` |
| Alignment with ITU standards | technical report, section 4 |
| Engineering rigour (additional) | `python -m pytest -q` · `python outils/verifier_formel.py` (exhaustive enumeration + Z3 proofs, runtime monitor) — [`docs/technique/RAPPORT_VERIFICATION_FORMELLE.md`](docs/technique/RAPPORT_VERIFICATION_FORMELLE.md) |

## Run it in two minutes

```bash
# 1. optional: CLE_API.txt has one line, CLE=your_key — the provider is recognised from the key:
#    Groq / OpenRouter / Gemini / Mistral (free tiers) or xAI / Anthropic / OpenAI (paid). Without a key: rule-based agents.
# 2. start
bash lancer_local.sh               # Linux / macOS (Windows: WSL or Git Bash) — or: python3 interface/serveur.py
# 3. open the private doctor link printed in the terminal, and http://127.0.0.1:8000/patient for the patient tablet
```

Key guide: [`docs/GUIDE_CLE_API.md`](docs/GUIDE_CLE_API.md). Prototype with fictitious patients only; not a medical
device and not legal advice; the official texts (Official Gazette of Cameroon) prevail.
