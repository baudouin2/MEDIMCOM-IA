"""Exports the knowledge base in the format expected by the ITU reference code (repository
CrashingGuru/ITUAIReadiness, `simulation/server/knowledge/ingest.py`): an `InputDocs/` folder of text files (.md),
filed in subfolders whose name becomes the `document_category` metadata, with an `Inputs.md` manifest.

    python kb/outils/exporter_inputdocs.py                  # -> kb/InputDocs/
    # then, in the ITU repository:  python -m server.knowledge.ingest --dir <path>/kb/InputDocs --reset

  - AI_Strategies/  one source per file (laws, standards, policies, strategies, global examples), with its
                    metadata (authority, jurisdiction, dates, official link, verification level) and each of its
                    provisions (reference, summary, short quote when the text was read);
  - AI_Use_Cases/   the MEDIMCOM IA use case (agents, data, ITU-T Y.3172 pipeline) and the identified gaps.
File names start with the country or organisation, so that the ITU ingestion infers jurisdiction and type.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

KB = Path(__file__).resolve().parent.parent
SORTIE = KB / "InputDocs"

PREFIXES_JURIDICTION = [("AE", "UAE"), ("CM", "Cameroon"), ("US", "US"), ("EU", "EU"), ("UK", "UK"),
                        ("African Union", "African_Union"), ("International", "International")]


def _nom_fichier(src: dict) -> str:
    juri = src.get("jurisdiction", "")
    pays = next((p for k, p in PREFIXES_JURIDICTION if juri.startswith(k)), "International")
    titre = src.get("short_title") or src.get("title") or src["id"]
    titre = re.sub(r"^(UAE|Cameroon|Cameroun|US|EU|UK)\s+", "", titre)
    titre = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode()       # « pénal » -> « penal »
    base = re.sub(r"[^A-Za-z0-9]+", "_", f"{pays} {titre}").strip("_")
    genre = src.get("type", "").lower()
    suffixe = ("policy" if any(x in genre for x in ("policy", "standard", "guidance", "charter", "recommendation", "label"))
               else "national_strategy" if "strategy" in genre
               else "regulation" if any(x in genre for x in ("law", "loi", "decree", "décret", "regulation", "resolution", "directive"))
               else "")
    return f"{base[:110]}{'_' + suffixe if suffixe and suffixe not in base.lower() else ''}.md"


def _source_md(src: dict, fiches: list[dict]) -> str:
    l = [f"# {src.get('title', src['id'])}", ""]
    champs = [("Identifier", src["id"]), ("Short title", src.get("short_title")), ("Type", src.get("type")),
              ("Jurisdiction", src.get("jurisdiction")), ("Authority", src.get("authority")),
              ("Issued", src.get("date_issued")), ("In force", src.get("date_in_force")), ("Legal status", src.get("legal_status")),
              ("Official URL", src.get("url")), ("Language", src.get("language")),
              ("Verification", src.get("verification")), ("Role in MEDIMCOM IA", src.get("role")),
              ("Used for", ", ".join(src.get("used_for") or []))]
    l += [f"- **{k}:** {v}" for k, v in champs if v]
    l += ["", "Source: MEDIMCOM IA knowledge base (ShifaMiko team, ITU AI for Good Sandbox Hackathon). Summaries in plain "
          "language; short verbatim quotes only where the official text was read. The official-language text prevails.", ""]
    for f in fiches:
        l += [f"## {f.get('ref', '')} — {f.get('title', '')}".strip(" —"), "", f.get("text", "")]
        if f.get("quote"):
            l += ["", f"> \"{f['quote']}\""]
        meta = [f"provision id: {f['id']}", f"legal basis: {f.get('basis', '')}"]
        if f.get("themes"):
            meta.append("themes: " + ", ".join(f["themes"]))
        if f.get("modes"):
            meta.append("modes: " + ", ".join(f["modes"]))
        l += ["", "*" + " · ".join(meta) + "*", ""]
    return "\n".join(l).rstrip() + "\n"


def _cas_usage_md() -> str:
    return """# MEDIMCOM IA — agentic AI use case (healthcare, Cameroon)

Team ShifaMiko (Université de Yaoundé I, Cameroon) · ITU AI for Good Sandbox Hackathon.

## Problem
Deaf patients with limited literacy cannot follow a medical consultation in spoken or written language, and sign-language
interpreters are scarce. Errors in communication lead to unsafe prescriptions, invalid consent and missed emergencies.

## Scope
The consultation itself: doctor-patient communication, patient record, prescriptions and audit journal. The prototype is not
connected to institutions or other systems and sends no consultation data outside the clinic computer.

## Solution
A doctor and a deaf patient communicate through pictograms. Three autonomous agents collaborate on a shared consultation record:
- **Translator** — text ⇄ pictograms; refuses to guess (a word without a safe pictogram is shown to the doctor, never replaced
  by a wrong image); turns the patient's taps into a plain sentence for the doctor.
- **Assistant** — keeps the patient state (confirmed or not), detects missing facts and warning signs (e.g. fever and cough:
  possible contagious disease), proposes questions and sourced treatment options, checks every medicine against the patient.
- **Jurist** — 68 deterministic rules (kb/regles_cm.json) check prescriptions and messages to the patient against Cameroonian
  law and the international instruments binding Cameroon (UN CRPD, WHO IHR); verdicts BLOCKED / REVIEW / INSUFFICIENT
  EVIDENCE / COMPLIANT, each citing provisions; gap detection. Rules are data: condition on declared variables, level, legal
  force of the basis, cited provisions; evaluated in three-valued (Kleene) logic, most severe finding wins; formally verified.
The doctor always decides. Every reasoning step, action, message and verdict is written to a SHA-256 hash-chained journal,
from which a responsibility report is drawn.

## Data (ITU-T Y.3172 pipeline)
| Node | MEDIMCOM IA |
|---|---|
| SRC | Doctor's keyboard or dictation; patient's pictogram taps on a tablet; documents shown by the patient (photos of prescriptions) |
| C | Local server (Python standard library) on the clinic computer; JSON events |
| PP | Typo correction, dose normalisation, confirmed / unconfirmed facts; fictitious patients only when an online model is used |
| M | Language model (local Ollama or online API, tests only) for the assistant; deterministic rules for the jurist |
| P | Jurist rules (Cameroonian law, UN CRPD, WHO IHR); human-in-the-loop validation; formal verification of the rules |
| D | Validated pictogram messages to the patient screen; prescriptions with legal analysis and a consent question |
| SINK | Hash-chained audit journal; readable responsibility report (who proposed, what was checked, who decided) |

## Evaluation scenarios
Progressive, fragmented error scenarios (`scenarios/`): pregnancy (contraindicated drug), allergy, suspected contagious
disease (the doctor overrides the jurist; the journal establishes responsibility) — expected outcomes and safety invariants
in `evaluer_agents.py`. A second country file (United Arab Emirates, `--pays AE`) shows that the base can be swapped.
"""


def _lacunes_md(lacunes: dict) -> str:
    l = ["# MEDIMCOM IA — policy, standards and legislative gaps (healthcare AI, deaf patients)", "",
         f"{lacunes.get('name', '')} — checked on {lacunes.get('checked_on', '')}.", ""]
    for g in lacunes.get("gaps", []):
        l += [f"## {g['id']} — {g.get('title', '')}", "", f"**Domain:** {g.get('domain', '')}", "",
              f"**Situation:** {g.get('situation', '')}", "", "**Existing texts (Cameroon and instruments binding Cameroon):**"]
        l += [f"- {t.get('fiche')}: {t.get('says')}" for t in g.get("existing_texts_cm", g.get("existing_texts", []))]
        l += ["", f"**What is missing:** {g.get('missing_cm') or g.get('missing', '')}", "", "**Global examples:**"]
        l += [f"- {t.get('fiche')}: {t.get('how')}" for t in g.get("global_examples", [])]
        if g.get("medimcom_response") or g.get("medimcom"):
            l += ["", f"**MEDIMCOM IA response:** {g.get('medimcom_response') or g.get('medimcom')}"]
        l.append("")
    return "\n".join(l)


def exporter(sortie: Path = SORTIE) -> dict:
    sources = json.loads((KB / "sources.json").read_text(encoding="utf-8"))["sources"]
    fiches = defaultdict(list)
    for ligne in (KB / "fiches.jsonl").read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            f = json.loads(ligne)
            fiches[f["source"]].append(f)
    if sortie.exists():
        shutil.rmtree(sortie)
    (sortie / "AI_Strategies").mkdir(parents=True)
    (sortie / "AI_Use_Cases").mkdir(parents=True)
    lignes = []
    for src in sources:
        nom = _nom_fichier(src)
        (sortie / "AI_Strategies" / nom).write_text(_source_md(src, fiches.get(src["id"], [])), encoding="utf-8")
        lignes.append((nom, src, len(fiches.get(src["id"], []))))
    (sortie / "AI_Use_Cases" / "MEDIMCOM_IA_use_case_healthcare_Cameroon.md").write_text(_cas_usage_md(), encoding="utf-8")
    lac = json.loads((KB / "lacunes.json").read_text(encoding="utf-8"))
    (sortie / "AI_Use_Cases" / "MEDIMCOM_IA_policy_gaps.md").write_text(_lacunes_md(lac), encoding="utf-8")
    man = ["# Input Documents Manifest — MEDIMCOM IA knowledge base", "",
           "Ready for the ITU reference ingestion code (`python -m server.knowledge.ingest --dir kb/InputDocs --reset`): "
           "the pipeline recurses into subfolders and tags each document with its subfolder as `document_category`.", "",
           "Generated by `python kb/outils/exporter_inputdocs.py` from `kb/sources.json`, `kb/fiches.jsonl` and `kb/lacunes.json`.", "",
           f"## AI_Strategies/ ({len(lignes)} files)", "", "| # | Filename | Jurisdiction | Type | Provisions | Verification | Official URL |",
           "|---|---|---|---|---|---|---|"]
    for i, (nom, src, n) in enumerate(lignes, 1):
        man.append(f"| {i} | `{nom}` | {src.get('jurisdiction', '')} | {src.get('type', '')} | {n} | {src.get('verification', '')} | {src.get('url', '')} |")
    man += ["", "## AI_Use_Cases/ (2 files)", "", "| # | Filename | Description |", "|---|---|---|",
            "| 1 | `MEDIMCOM_IA_use_case_healthcare_Cameroon.md` | Use case, agents, Y.3172 pipeline, evaluation scenarios |",
            f"| 2 | `MEDIMCOM_IA_policy_gaps.md` | {len(lac.get('gaps', []))} policy, standards and legislative gaps with global examples |", ""]
    (sortie / "Inputs.md").write_text("\n".join(man), encoding="utf-8")
    return {"sources": len(lignes), "dispositions": sum(n for _, _, n in lignes)}


if __name__ == "__main__":
    r = exporter()
    print(f"kb/InputDocs/ : {r['sources']} sources, {r['dispositions']} dispositions, + cas d'usage et lacunes.")
