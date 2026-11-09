# MEDIMCOM IA — autonomous agents, jurist and knowledge base (local prototype)

Team **ShifaMiko** · AI for Good Lab / Sandbox Hackathon – United Arab Emirates (ITU).

MEDIMCOM IA lets a doctor and a deaf patient with limited literacy communicate through pictograms. Autonomous agents collaborate around a shared consultation record: a **translator** (text ⇄ pictograms; demo dictionary now, the team's pictogram model plugs in via `docs/technique/CONTRAT_AGENT1.md`), an **assistant** (patient state, missing facts, sourced suggestions) and a **jurist** (deterministic checks of prescriptions, messages to the patient and data requests against UAE law; crisis advisor; gap detection). In the crisis scenario, institutional agents (health authority, hospital, crisis cell) receive fragmented information, never see the patient record, and record measures only with a checked binding legal basis. The doctor always decides. Every step is written to a SHA-256 hash-chained journal.

- Technical report (5 pages): `docs/soumission/MEDIMCOM_IA_Technical_Report.pdf`
- Gap analysis: `docs/soumission/MEDIMCOM_IA_Gap_Analysis.pdf`
- Screenshots of the doctor and patient screens: `docs/captures/`
- Working documents (in French): `docs/technique/` (agent architecture, pictogram-engine contract), `docs/pictogrammes/` (pictogram sheet, test booklet, user-test protocol), `docs/video/` (video script), `docs/equipe/` (team roles, requirement tracking). Regenerate the report with `python outils/generer_rapport.py`.
- Knowledge base: `kb/` — 40 sources (30 official texts, 7 secondary, 3 to confirm), 124 provisions, 61 UAE rules + 48 Cameroon rules (`--pays CM`), 9 gaps, 65 test questions, 133 vector-ready chunks; reference links of all materials: `docs/soumission/KB_reference_links.md`.

Local interface, written in React (`interface/web/`, compiled build shipped in `interface/web/dist/`, so nothing to install to run it): `python interface/serveur.py` — doctor screen at the private link printed on start-up (`/medecin?jeton=…`, a per-run secret token), patient screen at `/patient` (text-free pictograms, optional fr/en/ar labels, emergency button); `--demo scenarios/grossesse.json` for a step-by-step demo. Pictograms come from existing pictogram databases; the prototype ships 46 placeholder SVG icons (`docs/pictogrammes/Planche_pictogrammes.pdf`); user-test protocol (to run with deaf participants): `docs/pictogrammes/PROTOCOLE_TESTS.md`. Prototype security: token-protected doctor actions, same-origin JSON-only writes, localhost by default; no HTTPS or user accounts — synthetic data only.

```bash
python main.py                                   # consultation scenario (no AI needed)
python main.py --scenario scenarios/crise.json   # crisis scenario
python main.py --langue en                       # jurist findings in English
python main.py --mode ollama --modele qwen3:8b   # real agents with a local model
python main.py --mode openai --url http://localhost:8080/v1 --modele qwen2.5-7b-instruct   # any OpenAI-compatible server
python evaluer_agents.py                         # agent evaluation: safety invariants + capability scorecard
python exporter_journal.py sortie/journal.json   # readable HTML audit trail
python -m pytest -q                              # 103 tests
python kb/outils/evaluer_recherche.py            # retrieval: recall@3 = 0.94, recall@5 = 0.97
python outils/verifier_formel.py                 # formal verification: exhaustive enumeration + Z3 SMT proofs of the rule
                                                 # specification, runtime monitor (10 invariants) over generated adversarial runs
python outils/constituer_base_v2.py              # knowledge base v2 on this computer, organised by hackathon requirement:
                                                 # 87 official documents (Cameroon first, UN, WHO, UNESCO, OECD, CoE, AU, UAE),
                                                 # article-level split + RAG chunks + requirement/gap matrix; health-filtered
                                                 # pictograms (ARASAAC, Mulberry, OpenMoji; 1,287 concepts in 30 communicative categories, 3000 target),
                                                 # WHO fact sheets fr/en/ar, MedlinePlus, Wikidata lexicon, training sets + datasheet
```

Prototype with synthetic data; not a medical device and not legal advice. The Arabic text of UAE legislation prevails.

## License

Code: Apache 2.0 (`LICENSE`). ARASAAC pictograms remain under CC BY-NC-SA 4.0 (non-commercial); third-party content is listed in `NOTICE.md`.
