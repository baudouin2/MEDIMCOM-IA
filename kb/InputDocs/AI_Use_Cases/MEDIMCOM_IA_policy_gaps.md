# MEDIMCOM IA — policy, standards and legislative gaps (healthcare AI, deaf patients)

MEDIMCOM IA - policy and standards gap catalogue — checked on 2026-10-16.

## L01 — Who answers for an AI suggestion that a clinician validated?

**Domain:** Liability and accountability

**Situation:** The assistant agent proposes an alternative treatment; the doctor accepts it; it later proves wrong.

**Existing texts (Cameroon and instruments binding Cameroon):**
- CM90-A16-17: Only a registered physician diagnoses and prescribes, and answers for it; silent on AI suggestions.
- WHO21-PRINC: Accountability is a guiding principle for AI in health (non-binding).

**What is missing:** No Cameroonian text allocates liability between clinician, software developer and facility when a validated AI suggestion causes harm, and none says what evidential value AI logs have in a dispute.

**Global examples:**
- PLD24-SW: Software is a product; disclosure of evidence and presumption of defect ease the claimant's burden.
- AIA-A14: Oversight duties include awareness of automation bias and the ability to override.

**MEDIMCOM IA response:** Every AI suggestion carries its author agent, sources and status; overriding an A_REVOIR verdict requires a named doctor; the hash-chained journal can be produced as evidence.

## L02 — When is a decision-support or communication assistant a medical device?

**Domain:** Regulatory status of software

**Situation:** MEDIMCOM translates, suggests and checks; none of its agents prescribes, but its outputs influence decisions.

**Existing texts (Cameroon and instruments binding Cameroon):**
- CM-PHARM: Pharmacy and medicines law (to be read): no software classification criteria found.

**What is missing:** No criteria distinguish regulated decision-support software from communication aids and compliance checkers.

**Global examples:**
- FDA26-CDS: Four criteria; the clinician must be able to review the basis of each recommendation.
- MDR-R11: Decision-support software is at least class IIa.
- MHRA-AIRLOCK: Regulatory sandbox to test AI medical devices before rules are final.

**MEDIMCOM IA response:** Designed to meet the 'reviewable basis' test: every suggestion and verdict shows its source text; the doctor decides.

## L03 — No operational standard for meeting deaf patients' communication needs in care

**Domain:** Accessible health communication

**Situation:** A deaf patient with limited literacy consults without a sign-language interpreter.

**Existing texts (Cameroon and instruments binding Cameroon):**
- CM10-A3: Deaf persons are persons with a sensory disability.
- CM10-A32: Access of persons with disabilities to information technologies.
- CRPD-A21: Accessible information and alternative communication (binding on Cameroon).

**What is missing:** No operational standard requires providers to identify, record and meet a patient's communication need; the 2010 law does not mention sign language.

**Global examples:**
- NHS-AIS: Identify, record, flag, share and meet communication needs - a legal requirement in England since 2016.

**MEDIMCOM IA response:** The communication need is stored in the patient state and travels with the record; the translator agent adapts every message; the doctor validates each pictogram sequence.

## L04 — Is consent given through pictograms valid informed consent?

**Domain:** Informed consent

**Situation:** The patient agrees to a treatment by selecting pictograms.

**Existing texts (Cameroon and instruments binding Cameroon):**
- CM-DEONTO: Free and informed consent and patient information (articles to confirm).
- CRPD-A12: Legal capacity and support in exercising it.
- CRPD-A25: Care on the basis of free and informed consent.

**What is missing:** Consent through alternative communication (pictograms) is not recognised, and no rule says how comprehension must be checked or documented.

**Global examples:**
- CRPD-A12: Support in exercising legal capacity.
- CRPD-A25: Care of the same quality on the basis of free and informed consent.
- CRPD-A21: Alternative communication accepted in official interactions.

**MEDIMCOM IA response:** Consent is recorded with its means of expression, a comprehension check (teach-back with pictograms) and the doctor's attestation, all in the journal.

## L05 — No validation standard for medical pictograms

**Domain:** Standards

**Situation:** Pictograms are generated or chosen by a model and shown to patients.

**Existing texts (Cameroon and instruments binding Cameroon):**

**What is missing:** No standard on testing health pictograms or AI-generated images shown to patients.

**Global examples:**
- ISO9186: Standard method for testing what proportion of people understand a symbol.

**MEDIMCOM IA response:** Pictogram library tested with deaf users following the ISO 9186-1 method before use; every sequence validated by the doctor.

## L06 — Strict health-data localisation versus cloud AI and international sandboxes

**Domain:** Data governance and innovation

**Situation:** A model or vector store hosted outside the country (e.g. an international sandbox) would process consultation content.

**Existing texts (Cameroon and instruments binding Cameroon):**
- CM24-SENSIBLES: Health data are sensitive data.
- CM24-TRANSFERT: Transfers of personal data outside Cameroon are subject to conditions and authorisation.

**What is missing:** No pathway for testing AI in international or cross-border sandboxes, and no statement on whether synthetic or de-identified data fall outside the transfer rules.

**Global examples:**
- AIA-A57-59: Sandboxes with strict conditions; anonymised or synthetic data preferred.
- MHRA-AIRLOCK: National sandbox for AI medical devices.

**MEDIMCOM IA response:** Local models only; synthetic data in the prototype; the jurist blocks any outbound transfer without an exception and its conditions.

## L07 — Oversight rules do not address multi-agent systems

**Domain:** Human oversight and traceability

**Situation:** Several AI agents exchange messages and act on a shared record before a human sees the result.

**Existing texts (Cameroon and instruments binding Cameroon):**
- WHO21-PRINC: WHO principles: human autonomy, transparency, accountability (non-binding).
- AU-AI: African Union continental AI strategy (non-binding).

**What is missing:** No Cameroonian text on AI in health; nothing on agent-to-agent communication, agent autonomy, tool permissions or tamper-evident logs.

**Global examples:**
- AIA-A12: Automatic logging over the lifetime of the system.
- AIA-A14: Effective human oversight including automation bias.

**MEDIMCOM IA response:** Typed messages between agents, per-agent tool permissions, deterministic verdicts, SHA-256 chained journal.

## L08 — No unified channel for AI incidents in health

**Domain:** Crisis coordination

**Situation:** During a crisis an AI component fails or gives harmful output in several facilities.

**Existing texts (Cameroon and instruments binding Cameroon):**
- IHR-A6: Time-bound notification model exists for public health events.

**What is missing:** No duty, time limit or channel to report an AI incident in health.

**Global examples:**
- AIA-A73: Serious incidents reported within 15 days, shorter for widespread or fatal ones.
- IHR-A6: Time-bound notification through a single national focal point.

**MEDIMCOM IA response:** The journal exports an incident record (what, when, which agent, which sources); the jurist reminds the time limits that do exist.

## L09 — Emergency protocols do not guarantee equivalent access for deaf people

**Domain:** Accessible emergency communication

**Situation:** In an emergency the usual voice channels and interpreters are unavailable.

**Existing texts (Cameroon and instruments binding Cameroon):**
- CRPD-A11: Situations of risk and humanitarian emergencies (binding on Cameroon).

**What is missing:** Emergency protocols do not require equivalent non-voice access for deaf people.

**Global examples:**
- EECC-A109-5: Equivalent access to emergency services for end-users with disabilities.

**MEDIMCOM IA response:** Emergency pictogram set always available offline; urgent alerts are prioritised by the assistant agent.

## L10 — Who answers when a clinician overrides an AI warning of a suspected epidemic disease?

**Domain:** Public health and accountability

**Situation:** The assistant flags a possible epidemic-prone disease; the doctor confirms the suspicion but lets the patient go home without notification or isolation; contacts are later infected.

**Existing texts (Cameroon and instruments binding Cameroon):**
- IHR-A6: States notify WHO within 24 hours of assessment; national notification duties are left to each State.
- CM90-A16-17: The registered physician answers for diagnosis and treatment.

**What is missing:** No national text read sets the clinician's notification duty, time limit and channel, nor the weight of an AI warning and of its override when responsibility for onward transmission is established.

**Global examples:**
- IHR-A6: Time-bound notification through a single national focal point.
- AIA-A14: Human oversight: the user may override the system, and the override is traceable.

**MEDIMCOM IA response:** The override needs a written justification under the doctor's name; the hash-chained journal shows who warned, on which basis, who decided and when, so responsibility can be established afterwards.
