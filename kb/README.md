# Knowledge base (English)

| File | Content |
|---|---|
| `sources.json` | Manifest: id, title, short title, type, jurisdiction, authority, dates, official URL, download URL, language, verification level, role, use |
| `fiches.jsonl` | One provision per line: id, source, reference (article/section), title, plain-language summary, short verbatim quote when read, themes, modes (consultation / crisis), legal basis, agents |
| `regles_uae.json` · `regles_cm.json` | Jurist rules for the UAE (host country) and for Cameroon (`--pays CM`; most Cameroonian texts known through secondary sources or to confirm — a rule only BLOCKS when it cites a law whose content was read); French field names, `detail` in French, `detail_en` in English; every rule cites provision ids; a typed `signature` (open or closed world per variable) and `axiomes` (background knowledge) give the rules a formal semantics |
| `specification_formelle.json` | Formal specification: safety (`au_moins`, `jamais`) and utility (`au_plus`) requirements the rules must meet for all inputs, checked by `outils/verifier_formel.py` (exhaustive enumeration + Z3 proofs); see `docs/technique/METHODES_FORMELLES.md` |
| `lacunes.json` | Gap catalogue: situation, existing UAE texts, what is missing, global examples, MEDIMCOM response |
| `questions_test.jsonl` | Retrieval test set with expected provision ids |
| `index/chunks.jsonl` | Self-contained chunks `{id, text, metadata}` for any vector store (regenerate with `outils/construire_index.py`) |
| `index/vecteurs_<encoder>.jsonl` | Vector base: one line per chunk `{id, text, metadata, embedding}` after a header line `{"_index": {encoder, dimension, chunk fingerprint, cosine}}`. `vecteurs_hachage-1024.jsonl` is a dependency-free fallback (word similarity only); build the semantic one locally with `bge-m3` |
| `InputDocs/` | The same knowledge base in the format of the **ITU reference ingestion code** (CrashingGuru/ITUAIReadiness, `server/knowledge/ingest.py`): `AI_Strategies/` (one Markdown file per source with its metadata and provisions), `AI_Use_Cases/` (use case, Y.3172 pipeline, gaps), manifest `Inputs.md`. Ingest with `python -m server.knowledge.ingest --dir kb/InputDocs --reset`; regenerate with `python kb/outils/exporter_inputdocs.py` |
| `outils/` | `verifier_kb.py` (consistency), `evaluer_recherche.py` (recall@k, MRR; `--comparer` for BM25 vs vectors vs hybrid), `construire_index.py` (chunks), `construire_vecteurs.py` (vector base), `telecharger_sources.py` (download originals, pin SHA-256, detect changes) |

**Legal basis labels**: `LOI` (law), `NORME` (binding regulator standard), `POLITIQUE` (regulator policy), `RECOMMANDATION` (clinical reference), `STRATEGIE`, `ENGAGEMENT_INTERNATIONAL` (treaty), `EXEMPLE_MONDIAL` (global example), `COMPARATIF` (Cameroon, comparison only).

**Verification levels**: `official_text` (read on the official publisher's site), `secondary_source` (known through a law firm or press summary — obtain the official text before production use), `to_confirm`.

**Rules for maintainers**: never cite an article number that was not read; keep the Arabic-prevails warning; re-run `outils/verifier_kb.py` and the tests after any change; run `outils/telecharger_sources.py --verifier` regularly to detect changes in official texts. Checked on 27 October 2026.

## Vector base

```bash
ollama pull bge-m3                                                  # multilingual embedding model (fr / en / ar), runs locally
python kb/outils/construire_vecteurs.py                             # -> kb/index/vecteurs_ollama-bge-m3.jsonl
python kb/outils/evaluer_recherche.py --comparer --encodeur ollama:bge-m3   # BM25 vs vectors vs hybrid on the test questions
python main.py --recherche ollama:bge-m3                            # agents search the base with hybrid retrieval
```

Hybrid retrieval fuses BM25 (words) and vectors (meaning) by reciprocal rank fusion; the jurist's verdicts stay rule-based whatever the retrieval. An index whose chunks no longer match the provisions is refused (rebuild it).

Loading the file into another vector store (example: Chroma):

```python
import json, chromadb
lignes = [json.loads(l) for l in open("kb/index/vecteurs_ollama-bge-m3.jsonl", encoding="utf-8")][1:]   # skip the header
col = chromadb.PersistentClient("kb_chroma").get_or_create_collection("medimcom", metadata={"hnsw:space": "cosine"})
col.add(ids=[x["id"] for x in lignes], documents=[x["text"] for x in lignes],
        metadatas=[x["metadata"] for x in lignes], embeddings=[x["embedding"] for x in lignes])
```
