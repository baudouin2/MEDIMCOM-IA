# MEDIMCOM IA — agentic AI use case (healthcare, Cameroon)

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
