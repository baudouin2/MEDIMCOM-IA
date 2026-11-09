# MEDIMCOM IA — agentic AI use case (healthcare, UAE)

Team ShifaMiko (Université de Yaoundé I) · ITU AI for Good Lab Hackathon – United Arab Emirates.

## Problem
Deaf patients with limited literacy cannot follow a medical consultation in spoken or written language. Errors in
communication lead to unsafe prescriptions, invalid consent and missed emergencies.

## Solution
A doctor and a deaf patient communicate through pictograms. Autonomous agents collaborate on a shared consultation record:
- **Translator** — text ⇄ pictograms; refuses to guess (a word without a safe pictogram is shown to the doctor, never replaced
  by a wrong image); reads context (instruction, question, narrative) and corrects typing and dictation errors.
- **Assistant** — keeps the patient state (confirmed or not), detects missing facts, proposes questions and sourced treatment
  options, checks every medicine against the patient (pregnancy, allergies, age, current treatments).
- **Jurist** — deterministic checks of prescriptions, messages to the patient and data requests against UAE law and regulator
  standards (verdicts BLOCKED / TO REVIEW / INSUFFICIENT EVIDENCE / COMPLIANT, each citing provisions); crisis advisor; gap detection.
- **Institutional agents** (crisis scenario) — health authority, hospital, crisis cell: fragmented information, own mandates,
  no access to the patient record, measures only with a checked binding legal basis.
The doctor always decides. Every reasoning step, action, message and verdict is written to a SHA-256 hash-chained journal.

## Data (ITU-T Y.3172 pipeline)
| Node | MEDIMCOM IA |
|---|---|
| SRC | Doctor's keyboard or dictation; patient's pictogram taps on a tablet; documents (photos of prescriptions, receipts) |
| C | Local server (Python standard library) on the clinic computer; JSON events |
| PP | Context reading, typo correction, pictogram translation; fictitious patients only when an online model is used |
| M | Language model (local Ollama or online API) for the assistant; deterministic rules for the jurist |
| P | Jurist rules (UAE law, DoH/DHA/MOHAP standards); human-in-the-loop validation; formal verification of the rules |
| D | Validated pictogram messages to the patient screen; prescriptions with legal analysis |
| SINK | Hash-chained audit journal; readable responsibility report (who proposed, what was checked, who decided) |

## Evaluation scenarios
Progressive, fragmented error scenarios (`scenarios/`): pregnancy (contraindicated drug), allergy, crisis (communicable
disease, teleconsultation, institutions) — expected outcomes and safety invariants in `evaluer_agents.py`.
