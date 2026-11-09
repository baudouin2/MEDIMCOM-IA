# MEDIMCOM IA — autonomous agents, jurist and knowledge base (local prototype)

Team **ShifaMiko** (Université de Yaoundé I) · AI for Good Lab / Sandbox Hackathon – United Arab Emirates (ITU) · submission of 10 November 2026.

MEDIMCOM IA lets a doctor and a deaf patient with limited literacy communicate through pictograms. Autonomous agents collaborate around a shared consultation record: a **translator** (text ⇄ pictograms; refuses to guess when no safe pictogram exists; the team's pictogram model plugs in via `docs/technique/CONTRAT_AGENT1.md`), an **assistant** (patient state, missing facts, sourced suggestions, reading of documents sent by the patient) and a **jurist** (deterministic checks of prescriptions, messages to the patient and data requests against UAE law and DoH / DHA / MOHAP standards; crisis advisor; gap detection). In the crisis scenario, institutional agents (health authority, hospital, crisis cell) receive fragmented information, never see the patient record, and record measures only with a checked binding legal basis. The doctor always decides. Every step is written to a SHA-256 hash-chained journal.

- **Technical report** (official template, 5 pages): `docs/soumission/MEDIMCOM_IA_Technical_Report.pdf` (Word: `.docx`)
- **Detailed technical documentation** (agents, jurist rules, auditability): `docs/soumission/MEDIMCOM_IA_Technical_Documentation.pdf`
- **Gap analysis**: `docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf` · reference links of all knowledge-base materials: `docs/soumission/KB_reference_links.md`
- **Submission map** (every item of the call → file): `SUBMISSION.md`
- **Knowledge base**: `kb/` — 47 sources (33 official texts, 11 secondary sources, 3 to confirm), 139 provisions, 81 UAE rules + 67 Cameroon rules (`--pays CM`), 9 gaps, 65 test questions, 148 vector-ready chunks; packaged for the ITU reference ingestion code in `kb/InputDocs/`
- Screenshots: `docs/captures/` · demo video script: `docs/video/SCRIPT_VIDEO.md` · working documents (in French): `docs/technique/`, `docs/pictogrammes/`, `docs/equipe/`

## Run it

```bash
# optional: put an API key in CLE_API.txt (one line: CLE=your_key). The provider is recognised from the key:
# Groq / OpenRouter / Gemini / Mistral (free tiers) or xAI / Anthropic / OpenAI (paid). Guide: docs/GUIDE_CLE_API.md
bash lancer_local.sh                    # Linux / macOS (Windows: WSL or Git Bash) — or: python3 interface/serveur.py
bash lancer_local.sh ollama             # local open-source model: nothing leaves the computer
bash lancer_local.sh sans-ia            # written rules only (no language model)
bash lancer_local.sh diagnostic         # checks Internet, key, quota and model, and says what to do
```

Doctor screen at the private link printed on start-up (`/medecin?jeton=…`, a per-run secret token); patient screen at `/patient` (text-free pictograms, optional fr/en/ar labels, emergency button, sending of documents such as earlier prescriptions). Step-by-step demo: `python3 interface/serveur.py --demo scenarios/grossesse.json` (also `allergie.json`, `crise.json`). The React interface is shipped already built in `interface/web/dist/`: nothing to install to run it.

```bash
python main.py                                   # consultation scenario (no AI needed)
python main.py --scenario scenarios/crise.json   # crisis scenario
python main.py --langue en                       # jurist findings in English
python evaluer_agents.py                         # agent evaluation: safety invariants + capability scorecard
python exporter_journal.py sortie/journal.json   # readable HTML audit trail
python verifier_journal.py sortie/journal.json --falsifier 10   # tamper test: the modified line is detected
python -m pytest -q                              # 208 tests
python kb/outils/evaluer_recherche.py            # retrieval: recall@3 = 0.89, recall@5 = 0.97, MRR = 0.86
python outils/verifier_formel.py                 # formal verification: exhaustive enumeration + Z3 SMT proofs, runtime monitor
python outils/constituer_base_v2.py              # optional extended knowledge base v2, built on this computer
                                                 # (87 official documents, ~1,300 health pictogram concepts, WHO fact sheets)
```

**Limitations** (details in `README.md`, section 6): only 7 documented medicines are checked (others give "insufficient evidence" and cannot be overridden); adult doses only; pictograms not yet tested with deaf users; online models with fictitious patients only; one consultation per server; no HTTPS or user accounts.

Prototype with fictitious patients only; not a medical device and not legal advice. The Arabic text of UAE legislation prevails.

## License

Code: Apache 2.0 (`LICENSE`). ARASAAC pictograms remain under CC BY-NC-SA 4.0 (non-commercial); third-party content is listed in `NOTICE.md`.
