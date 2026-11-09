# MEDIMCOM IA — policy, standards and legislative gaps (healthcare AI, deaf patients)

MEDIMCOM IA - policy and standards gap catalogue — checked on 2026-10-16.

## L01 — Who answers for an AI suggestion that a clinician validated?

**Domain:** Liability and accountability

**Situation:** The assistant agent proposes an alternative treatment; the doctor accepts it; it later proves wrong.

**Existing texts:**
- ML16-A6: Defines the practitioner's medical error; silent on AI-generated suggestions.
- DOH18-SUPPORT: A human makes the final decision and is responsible for actions taken by the technology.
- DHA21-4.2: Accountability for outcomes must be agreed; developers accountable to end users; appeals procedure.

**What is missing:** No binding rule allocating liability between clinician, software developer and facility when a validated AI suggestion causes harm, and no rule on the evidential value of AI logs in a dispute.

**Global examples:**
- PLD24-SW: Software is a product; disclosure of evidence and presumption of defect ease the claimant's burden.
- AIA-A14: Oversight duties include awareness of automation bias and the ability to override.

**MEDIMCOM IA response:** Every AI suggestion carries its author agent, sources and status; overriding an A_REVOIR verdict requires a named doctor; the hash-chained journal can be produced as evidence.

## L02 — When is a decision-support or communication assistant a medical device?

**Domain:** Regulatory status of software

**Situation:** MEDIMCOM translates, suggests and checks; none of its agents prescribes, but its outputs influence decisions.

**Existing texts:**
- MP24-A1-EQ: Medical equipment includes operating software and AI-based products.
- RAI25-3.3.1.2.2: Risk classes; high-risk systems need conformity assessment (Abu Dhabi).

**What is missing:** The decree-law text read does not set criteria separating regulated decision-support software from non-device tools (communication aids, compliance checkers); executive regulations or EDE guidance on software to be checked.

**Global examples:**
- FDA26-CDS: Four criteria; the clinician must be able to review the basis of each recommendation.
- MDR-R11: Decision-support software is at least class IIa.
- MHRA-AIRLOCK: Regulatory sandbox to test AI medical devices before rules are final.

**MEDIMCOM IA response:** Designed to meet the 'reviewable basis' test: every suggestion and verdict shows its source text; the doctor decides.

## L03 — No operational standard for meeting deaf patients' communication needs in care

**Domain:** Accessible health communication

**Situation:** A deaf patient with limited literacy consults without a sign-language interpreter.

**Existing texts:**
- POD06-A7: Right to information and expression through sign language and other means.
- DHATH-14.1.5: Telehealth must make provision for People of Determination; language easily understood (Dubai).
- CRPD-A21: Accept and facilitate augmentative and alternative communication in official interactions.

**What is missing:** No federal operational standard requiring providers to identify, record and flag a patient's communication need, nor rules on which alternative means (pictograms, easy-read, sign avatars) are acceptable in a clinical encounter.

**Global examples:**
- NHS-AIS: Identify, record, flag, share and meet communication needs - a legal requirement in England since 2016.

**MEDIMCOM IA response:** The communication need is stored in the patient state and travels with the record; the translator agent adapts every message; the doctor validates each pictogram sequence.

## L04 — Is consent given through pictograms valid informed consent?

**Domain:** Informed consent

**Situation:** The patient agrees to a treatment by selecting pictograms.

**Existing texts:**
- ML16-A5-1: No treatment without consent, except emergencies.
- ML16-A8-1c: Written consent for surgery.
- DHATH-10: Consent documented at each encounter; electronic consent accepted (Dubai telehealth).

**What is missing:** No provision recognises consent expressed through augmentative and alternative communication, defines how comprehension is checked, or how such consent is documented.

**Global examples:**
- CRPD-A12: Support in exercising legal capacity.
- CRPD-A25: Care of the same quality on the basis of free and informed consent.
- CRPD-A21: Alternative communication accepted in official interactions.

**MEDIMCOM IA response:** Consent is recorded with its means of expression, a comprehension check (teach-back with pictograms) and the doctor's attestation, all in the journal.

## L05 — No validation standard for medical pictograms

**Domain:** Standards

**Situation:** Pictograms are generated or chosen by a model and shown to patients.

**Existing texts:**

**What is missing:** No UAE standard found on testing the comprehensibility of health pictograms or of AI-generated images used to inform patients.

**Global examples:**
- ISO9186: Standard method for testing what proportion of people understand a symbol.

**MEDIMCOM IA response:** Pictogram library tested with deaf users following the ISO 9186-1 method before use; every sequence validated by the doctor.

## L06 — Strict health-data localisation versus cloud AI and international sandboxes

**Domain:** Data governance and innovation

**Situation:** A model or vector store hosted outside the UAE (e.g. an international sandbox) would process consultation content.

**Existing texts:**
- ICT19-A13: No storage or processing of health data outside the State, except by resolution.
- RES51-EXC: Listed exceptions (research, foreign labs, insurers, etc.) - none explicitly for AI inference or model training.
- RAI25-3.1.4.5.1: Compute and storage in the UAE (Abu Dhabi).

**What is missing:** No explicit pathway for AI testing in cross-border or international sandboxes, and no statement on whether synthetic or de-identified data falls outside the localisation rule.

**Global examples:**
- AIA-A57-59: Sandboxes with strict conditions; anonymised or synthetic data preferred.
- MHRA-AIRLOCK: National sandbox for AI medical devices.

**MEDIMCOM IA response:** Local models only; synthetic data in the prototype; the jurist blocks any outbound transfer without an exception and its conditions.

## L07 — Oversight rules do not address multi-agent systems

**Domain:** Human oversight and traceability

**Situation:** Several AI agents exchange messages and act on a shared record before a human sees the result.

**Existing texts:**
- RAI25-3.1.7.1.3: All decisions logged and traceable to a responsible party.
- DHA21-4.4: AI supervised by end users and can be overridden.
- DHA21-4.3.1: Failures traced, diagnosed and controlled.

**What is missing:** No requirement on agent-to-agent communication, limits of agent autonomy, tool permissions, or tamper-evident logs.

**Global examples:**
- AIA-A12: Automatic logging over the lifetime of the system.
- AIA-A14: Effective human oversight including automation bias.

**MEDIMCOM IA response:** Typed messages between agents, per-agent tool permissions, deterministic verdicts, SHA-256 chained journal.

## L08 — No unified channel for AI incidents in health across emirates

**Domain:** Crisis coordination

**Situation:** During a crisis an AI component fails or gives harmful output in several facilities.

**Existing texts:**
- DHA21-4.8: Report AI incidents to DHA (Dubai).
- RAI25-3.1.7.1.2.3: Report adverse outcomes to governance bodies (Abu Dhabi).
- CD14-A4: 24-hour notification model exists for communicable diseases.

**What is missing:** Incident reporting duties are emirate-specific; no federal time limit or shared format for AI incidents found in the knowledge base.

**Global examples:**
- AIA-A73: Serious incidents reported within 15 days, shorter for widespread or fatal ones.
- IHR-A6: Time-bound notification through a single national focal point.

**MEDIMCOM IA response:** The journal exports an incident record (what, when, which agent, which sources); the jurist reminds the time limits that do exist.

## L09 — Emergency protocols do not guarantee equivalent access for deaf people

**Domain:** Accessible emergency communication

**Situation:** In an emergency the usual voice channels and interpreters are unavailable.

**Existing texts:**
- DHATH-12.4: Tested emergency protocols in telehealth, no accessibility requirement.
- POD06-A7: General right to communicate through other means.
- CRPD-A11: Protection in situations of risk.

**What is missing:** No requirement found that health emergency protocols provide equivalent non-voice access for deaf patients.

**Global examples:**
- EECC-A109-5: Equivalent access to emergency services for end-users with disabilities.

**MEDIMCOM IA response:** Emergency pictogram set always available offline; urgent alerts are prioritised by the assistant agent.
