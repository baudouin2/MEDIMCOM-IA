"""Génère le rapport technique (≤ 5 pages, en anglais) et l'annexe d'analyse des lacunes, à partir de la base réelle.

    pip install playwright && python -m playwright install chromium     # une seule fois
    python outils/generer_rapport.py                                     # -> docs/soumission/*.pdf

Les chiffres (sources, dispositions, règles, tests, questions…) sont lus dans le dépôt : relancer après chaque
modification de la base ou du code, puis vérifier que le rapport tient toujours en 5 pages (le script le contrôle).
Police : Inter si elle est installée, sinon la police sans empattement du système (la mise en page peut varier).
"""
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "kb" / "outils"))
from medimcom.base import BaseConnaissances  # noqa: E402
import evaluer_recherche  # noqa: E402

OUT = REPO / "docs" / "soumission"
KB = REPO / "kb"
base = BaseConnaissances(KB)
regles = json.loads((KB / "regles_uae.json").read_text(encoding="utf-8"))
qs = [json.loads(l) for l in (KB / "questions_test.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ev = evaluer_recherche.evaluer(base, qs)
from medimcom.regles import MoteurRegles  # noqa: E402
n_regles = sum(1 for _ in MoteurRegles(KB / "regles_uae.json", base)._toutes_les_regles())
niv = {}
for s in base.sources.values():
    niv[s["verification"]] = niv.get(s["verification"], 0) + 1
roles = {}
for s in base.sources.values():
    roles[s["role"]] = roles.get(s["role"], 0) + 1
n_attendus = sum(len(json.loads(c.read_text(encoding="utf-8")).get("attendus", [])) for c in (REPO / "scenarios").glob("*.json"))
n_tests = (REPO / 'tests' / 'test_noyau.py').read_text(encoding='utf-8').count('\ndef test_')
_vf = REPO / 'sortie' / 'verification_formelle.json'
_vfj = json.loads(_vf.read_text(encoding='utf-8')) if _vf.exists() else None
n_formel = (f"{len(_vfj['AE']['proprietes'])} (UAE) and {len(_vfj['CM']['proprietes'])} (Cameroon)" if _vfj else 'about 80 per jurisdiction')
n_chunks = sum(1 for _ in (KB / "index" / "chunks.jsonl").open(encoding="utf-8"))
e = html.escape


def cc(fid):
    """Citation compacte : titre court sans la parenthèse descriptive, puis l'article."""
    import re
    f = base.fiches[fid]
    t = base.sources[f["source"]]["short_title"]
    t = re.sub(r" \((?!\d{4}\))[^)]*\)", "", t).replace("Federal ", "")
    return e(f"{t}, {f['ref']}")


CSS = """
@page { size: A4; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: 'Inter', sans-serif; color: #1E2B31; font-size: 8.5pt; line-height: 1.34; margin: 0; }
.eyebrow { color: #B5541C; font-weight: 700; font-size: 7.4pt; letter-spacing: .8pt; text-transform: uppercase; }
h1 { font-size: 17pt; margin: .6mm 0 .4mm 0; color: #16262E; letter-spacing: -.2pt; line-height: 1.15; }
.meta { font-size: 8pt; color: #4A5A62; border-bottom: 1.6pt solid #16262E; padding-bottom: 1.6mm; margin-bottom: 2.4mm; }
h2 { font-size: 10.4pt; color: #16262E; margin: 3mm 0 1.2mm 0; break-after: avoid; }
h2 span { color: #D9692A; margin-right: 1.4mm; }
h3 { font-size: 9pt; margin: 2mm 0 .8mm 0; color: #16262E; break-after: avoid; }
p { margin: 0 0 1.4mm 0; }
ul, ol { margin: 0 0 1.4mm 0; padding-left: 4.2mm; }
ol.small li { margin-bottom: .3mm; word-break: break-all; }
li { margin-bottom: .5mm; }
.summary { background: #F6F3EC; border-left: 3pt solid #D9692A; padding: 2mm 3mm; border-radius: 1.5mm; margin-bottom: 1mm; }
table { width: 100%; border-collapse: collapse; margin: .8mm 0 1.8mm 0; font-size: 7.7pt; line-height: 1.28; }
th { background: #16262E; color: #fff; text-align: left; font-weight: 600; padding: 1.1mm 1.5mm; }
td { border-bottom: .5pt solid #C9D2D6; padding: 1mm 1.5mm; vertical-align: top; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
table { break-before: avoid; }
tr:nth-child(even) td { background: #F7F9FA; }
.v { font-weight: 700; white-space: nowrap; }
.B { color: #B42318; } .R { color: #B5541C; } .P { color: #6B5B00; } .C { color: #1D7A46; }
.small { font-size: 7.3pt; color: #4A5A62; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; }
.note { font-size: 7.4pt; color: #4A5A62; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 7.2pt; background: #EEF2F4; padding: 0 .6mm; border-radius: .6mm; }
.fig { margin: 1mm 0 1.6mm 0; }
.pb { break-before: page; }
"""


def svg_archi():
    ar = 'stroke="#5A6A72" stroke-width="1.3" fill="none" marker-end="url(#a)" marker-start="url(#a)"'
    one = 'stroke="#5A6A72" stroke-width="1.3" fill="none" marker-end="url(#a)"'

    def box(x, y, w, h, t, s1="", fill="#FFFFFF", st="#9FB2BB", sw="1.2"):
        o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" stroke="{st}" stroke-width="{sw}"/>'
        o += f'<text x="{x+w/2}" y="{y+17 if s1 else y+h/2+4}" font-size="10.6" font-weight="700" fill="#16262E" text-anchor="middle">{t}</text>'
        if s1:
            o += f'<text x="{x+w/2}" y="{y+31}" font-size="8.6" fill="#33454E" text-anchor="middle">{s1}</text>'
        return o
    s = '<svg viewBox="0 0 720 200" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Inter">'
    s += '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#5A6A72"/></marker></defs>'
    s += box(0, 4, 150, 40, "Doctor", "writes, validates, decides")
    s += box(285, 4, 150, 40, "Agent 1 · Translator", "text ⇄ pictograms", fill="#E3EEF4", st="#2A6F97", sw="1.7")
    s += box(570, 4, 150, 40, "Deaf patient", "reads and answers in images")
    s += f'<path d="M152 24H283" {ar}/><path d="M437 24H568" {ar}/>'
    s += '<text x="217" y="19" font-size="8.4" fill="#5A6A72" text-anchor="middle">validates every message</text>'
    s += '<text x="502" y="19" font-size="8.4" fill="#5A6A72" text-anchor="middle">pictograms</text>'
    s += '<rect x="0" y="66" width="720" height="28" rx="7" fill="#ECE6DA" stroke="#C9BFAE" stroke-width="1"/>'
    s += '<text x="360" y="84" font-size="9.2" fill="#16262E" text-anchor="middle"><tspan font-weight="700">Shared consultation record</tspan> (versioned): exchanges · patient state · questions · suggestions · decisions · verdicts · gaps</text>'
    dash = 'stroke="#7A8A92" stroke-width="1.2" stroke-dasharray="3 3" fill="none"'
    s += f'<path d="M360 44V66" {dash}/><path d="M240 94V118" {dash}/><path d="M480 94V118" {dash}/>'
    s += box(150, 118, 180, 44, "Agent 3 · Assistant", "patient state, questions, suggestions", fill="#E6F2EA", st="#3C8A5A", sw="1.7")
    s += box(390, 118, 180, 44, "Agent 2 · Jurist", "rules engine + crisis advice", fill="#FBE9DD", st="#D9692A", sw="1.7")
    s += f'<path d="M332 140H388" {ar}/>'
    s += '<text x="360" y="182" font-size="8.4" fill="#5A6A72" text-anchor="middle">typed direct messages: request · information · alert · proposal · disagreement</text>'
    s += box(590, 122, 130, 36, "Knowledge base", f"{len(base.sources)} texts · {len(base.fiches)} provisions")
    s += f'<path d="M572 140H588" {ar}/>'
    s += box(0, 122, 130, 36, "Hash-chained journal", "every step, SHA-256")
    s += f'<path d="M148 140H132" {one}/>'
    s += '</svg>'
    return s


def verdict(v):
    k = {"BLOQUE": "B", "A_REVOIR": "R", "PREUVES_INSUFFISANTES": "P", "CONFORME": "C"}.get(v, "")
    lab = {"BLOQUE": "BLOCKED", "A_REVOIR": "REVIEW", "PREUVES_INSUFFISANTES": "INSUFFICIENT EVIDENCE", "CONFORME": "COMPLIANT"}.get(v, v)
    return f'<span class="v {k}">{lab}</span>'


def table_regles():
    rows = [
        ("Who prescribes", "Register of licensed practitioners; author must be the human doctor", "BLOQUE", ["MP24-A42-2", "ML16-A4-6", "RAI25-3.1.7.2.2"]),
        ("Medicine approval", "No marketing approval → blocked; unknown medicine → cannot be checked", "BLOQUE", ["MP24-A5-1"]),
        ("History before treatment", "Pregnancy (women 12–50), allergies, current treatments must be confirmed", "PREUVES_INSUFFISANTES", ["ML16-A4-2"]),
        ("Written prescription", "Dose and usage required", "PREUVES_INSUFFISANTES", ["ML16-A4-6"]),
        ("Pregnancy", "Medicine that may cause abortion → blocked; NSAID → review by doctor", "BLOQUE", ["ML16-A16", "FDA20-NSAID"]),
        ("Telehealth", "No controlled/narcotic medicine at a distance (Dubai); identify patient, document consent", "BLOQUE", ["DHATH-17.12.7", "ML16-A5-5", "DHATH-10"]),
        ("Consent and information", "Consent before treatment (emergency exception); explain options and importance, accessibly", "OBLIGATION", ["ML16-A5-1", "ML16-A4-5", "POD06-A7", "CRPD-A21"]),
        ("AI transparency", "Tell the patient AI assists the doctor; patient may opt out", "OBLIGATION", ["RAI25-3.1.6.1.1"]),
        ("Messages to the patient", "Nothing reaches the patient without validation by an authorised, active doctor", "BLOQUE", ["DOH18-SUPPORT", "DHA21-4.4"]),
        ("Health data location", "No storage or processing abroad; listed exceptions need written consent, encryption, copy in UAE and a named authorisation", "BLOQUE", ["ICT19-A13", "ICT19-A24", "RES51-COND", "RAI25-3.1.4.5.1"]),
        ("Secondary use of data", "Health purposes only without written approval; five legal exceptions", "BLOQUE", ["ICT19-A16"]),
        ("Communicable diseases", "Group A: notify within 24 h; confidentiality of infected persons", "OBLIGATION", ["CD14-A4", "CD14-A29"]),
    ]
    t = '<table><tr><th style="width:17%">Rule family</th><th style="width:38%">What the jurist checks</th><th style="width:13%">Strongest outcome</th><th>Sources (provision IDs in the knowledge base)</th></tr>'
    for a, b, v, f in rows:
        out = verdict(v) if v != "OBLIGATION" else '<span class="v">OBLIGATION</span>'
        t += f"<tr><td><b>{e(a)}</b></td><td>{e(b)}</td><td>{out}</td><td>{'; '.join(cc(x) for x in f)}</td></tr>"
    return t + "</table>"


def table_scenarios():
    rows = [
        ("Consultation", "Woman, 25, abdominal pain; pregnancy unknown", "CONFORME", "Assistant asks “Are you pregnant?” on its own; translator turns it into pictograms; doctor validates; jurist clears; translator sends."),
        ("Consultation", "Doctor prescribes ibuprofen", "PREUVES_INSUFFISANTES", "Jurist asks the assistant for the missing fact; the question is already with the patient."),
        ("Consultation", "Patient taps the YES pictogram", "A_REVOIR", "Translator records pregnancy = yes; jurist re-checks unasked; assistant proposes a sourced alternative; doctor decides."),
        ("Consultation", "Doctor prescribes paracetamol (from the AI suggestion)", "CONFORME", "Obligations attached (consent, explanation, accessible information); translator prepares the explanation with a consent question; gaps L01, L04."),
        ("Consultation", "External module sends a message without validation", "BLOQUE", "Blocked; once the doctor validates the translator's version it is cleared and sent (gap L05)."),
        ("Consultation", "Company asks for the list of pregnant patients", "BLOQUE", f"{cc('ICT19-A16')}; lawful path stated."),
        ("Consultation", "Local model outage: send the consultation to a foreign cloud AI?", "BLOQUE", f"{cc('ICT19-A13')}, fine under Art. 24; path: model hosted in the UAE or locally (gap L06)."),
        ("Crisis", "Tramadol prescribed by teleconsultation; doctor tries to maintain it", "BLOQUE", f"{cc('DHATH-17.12.7')}; maintaining is refused — a blocking rule has no override."),
        ("Crisis", "Suspected Group A disease; doctor notifies the authority", "OBLIGATION", f"Jurist reminds the 24-hour notification. The authority, on its own, opens an investigation ({cc('CD14-A10')}), requests surveillance data (cleared), asks the jurist about its powers and then declares an infected area ({cc('CD14-A18')})."),
        ("Crisis", "Foreign laboratory requests identified results", "A_REVOIR", "Listed exception, all conditions met: the doctor authorises it by name with a written reason."),
        ("Crisis", "Authority asks: is consent given in pictograms valid without an interpreter?", "ADVICE", "Cites UAE disability law, CRPD Art. 21, Dubai telehealth standard and the consent rule; links gap L03 (L04 already recorded)."),
        ("Crisis", "Fragment to the hospital only: a severe case is transferred", "OBLIGATION", "Hospital reserves an isolation bed (legal basis checked), asks the doctor for emergency pictograms, informs the authority (gap L09)."),
        ("Crisis", "Fragment to the crisis cell only: the press wants names", "BLOQUE", f"Cell forwards to the authority; its nominative publication is blocked ({cc('CD14-A29')}); it follows the jurist's path and publishes anonymised figures — COMPLIANT."),
        ("Crisis", "Fragment to the crisis cell only: wrong pictograms in 3 facilities", "ADVICE", "Cell logs an AI incident, asks the jurist where to report (DHA, DoH, EU AI Act Art. 73 example; gap L08), informs the authority."),
    ]
    t = '<table><tr><th style="width:10%">Scenario</th><th style="width:25%">Fragment of information released</th><th style="width:13%">Key outcome</th><th>What the agents did on their own</th></tr>'
    for a, b, v, d in rows:
        out = verdict(v) if v in ("BLOQUE", "A_REVOIR", "PREUVES_INSUFFISANTES", "CONFORME") else f'<span class="v">{v}</span>'
        t += f"<tr><td>{a}</td><td>{e(b)}</td><td>{out}</td><td>{d}</td></tr>"
    return t + "</table>"


def table_lacunes(court=True):
    t = '<table><thead><tr><th style="width:4%">ID</th><th style="width:21%">Gap</th><th style="width:27%">What UAE texts already say</th><th style="width:24%">What is missing</th><th>Global examples</th></tr></thead>'
    for l in base.lacunes.values():
        ex = "; ".join(cc(x["fiche"]) for x in l["existing_texts"]) or "No text found in the knowledge base"
        gl = "; ".join(cc(x["fiche"]) for x in l["global_examples"])
        manque = l["missing"]
        if court and len(manque) > 170:
            manque = manque[:manque.rfind(" ", 0, 165)] + "…"
        t += f"<tr><td><b>{l['id']}</b></td><td><b>{e(l['title'])}</b><br><span class='small'>{e(l['domain'])}</span></td><td>{ex}</td><td>{e(manque)}</td><td>{gl}</td></tr>"
    return t + "</table>"


REFS = ["AE-ML-2016", "AE-ICT-2019", "AE-PDPL-2021", "AE-POD-2006", "AE-CD-2014",
        "AE-DOH-RAI-2025", "AE-DHA-TH-2025", "ITU-Y3172-2019", "ITU-AIR-2026"]


def rapport():
    r = ev["rappel"]
    body = f"""
<div class="eyebrow">AI for Good Lab / Sandbox Hackathon – United Arab Emirates · ITU · Technical report</div>
<h1>MEDIMCOM IA — autonomous AI agents for safe, lawful and accessible consultations with deaf patients</h1>
<div class="meta">Team <b>ShifaMiko</b> (Baudouin Nkana Bilong, Franck Ndonkou, Fotsing Engoulou) · Faculty of Sciences, University of Yaoundé I, Cameroon · Version 1.1, 21 October 2026 · Prototype in development: official legal texts, synthetic patients only — not a medical device.</div>
<div class="summary">MEDIMCOM IA lets a doctor and a deaf patient with limited literacy communicate through pictograms. Autonomous AI agents collaborate around a shared consultation record: a <b>translator</b> (text ⇄ pictograms; its pictogram model is in development and plugs in through a fixed interface), an <b>assistant</b> (patient state, missing information, suggestions) and a <b>jurist</b> that checks every prescription, every message to the patient and every data request against a verified knowledge base of UAE law, and acts as policy and legal advisor in a crisis, where institutional agents (health authority, hospital, crisis cell) coordinate on fragmented information. <b>The doctor always decides.</b> Every reasoning step, message and verdict is written to a hash-chained journal.</div>

<h2><span>1</span>Problem</h2>
<p>Deaf patients — especially those who read little — often cannot describe symptoms or understand treatment without an interpreter, and interpreters are scarce, above all in emergencies. Critical facts get lost (pregnancy, allergies, current medicines), consent may not be informed, and instructions are misunderstood. AI can help, but only within strict rules: in the UAE an AI system supports and a human decides ({cc('DOH18-SUPPORT')}; {cc('RAI25-3.1.7.2.2')}), health data must stay in the country ({cc('ICT19-A13')}), and every decision must be traceable ({cc('RAI25-3.1.7.1.3')}). In a crisis, information arrives in fragments and rules (notification duties, emergency powers) change what is allowed.</p>

<h2><span>2</span>Solution: three autonomous agents and one human decision-maker</h2>
<div class="fig">{svg_archi()}</div>
<table><tr><th style="width:15%">Agent</th><th style="width:37%">Goal and what it decides on its own</th><th style="width:26%">Collaboration</th><th>Hard limits (enforced in its tools)</th></tr>
<tr><td><b>1 · Translator</b></td><td>Translates the assistant's questions and every compliant prescription (with a consent question) into pictograms; reports the patient's own pictogram answers (a lone YES/NO to a closed question becomes a fact); flags words with no pictogram instead of inventing.</td><td>Proposes each message to the doctor; sends only after the jurist's green light.</td><td>Its send tool refuses any message not validated by an authorised, active doctor and judged COMPLIANT, or whose prescription is no longer compliant.</td></tr>
<tr><td><b>3 · Assistant</b></td><td>Keeps the patient state reliable; spots missing facts; asks questions through the translator; suggests answers or treatments with a source; withdraws obsolete suggestions; raises urgent alerts first.</td><td>Answers the jurist's requests; consults the knowledge base before proposing.</td><td>Never talks to the patient, never prescribes, no certain diagnosis, cannot confirm a fact nobody reported; the doctor validates or ignores.</td></tr>
<tr><td><b>2 · Jurist</b></td><td>Checks every prescription, message to the patient and data-sharing request; re-checks when the patient state changes; reminds legal obligations; answers questions in a crisis; records gaps.</td><td>Explains verdicts to the doctor; requests missing facts from the assistant; proposes a lawful path.</td><td>Cannot change a verdict: verdicts come from a deterministic rules engine; the language model only explains and negotiates.</td></tr></table>
<p><b>Why these are agents, not a workflow.</b> Each agent runs its own observe → reason → act loop: it reads its messages and what changed in the shared record since its last turn, and chooses which of its tools to call — or does nothing. The coordinator only releases scenario events and stops when no agent acts any more; it never orders the agents. In the reference runs the jurist re-checks a prescription because the patient state changed, and the assistant withdraws its own suggestion once the answer arrives — nobody tells them to; with a random order of turns the outcomes are identical. Agents run on local open models with tool calling (Ollama, or any OpenAI-compatible server such as llama.cpp or vLLM; one model per agent is possible; target models <code>qwen3:8b</code>, <code>llama3.1:8b</code>) or on scripted policies; the reference runs below use the scripted policies. The loop tolerates small-model errors (tool calls written as text, mistyped arguments, repeated calls) and degrades gracefully to the scripted policy if the model server fails. In both modes the guardrails sit in the tools: a tool outside an agent's permissions is refused and logged, the assistant cannot mark a fact as confirmed unless a confirmed exchange reports it, and a coordinator safety net forces the jurist's check on any decision left unchecked.</p>

<p><b>Interface.</b> A dependency-free local web app connects the agents to two screens: the doctor's (conversation, proposals to validate or reject, prescription form, agents' alerts with sources, crisis board) and the patient's (pictograms only, optional Arabic/English/French labels, large answer palette, a button to combine two pictograms into one image, emergency button); the translator also combines pictograms when clearer (head + pain), never the negation or a dose limit, usable on a tablet; a step-by-step demo mode replays the scenarios.</p>

<h2><span>3</span>The jurist agent: reasoning separated from decision</h2>
<p>Verdicts: {verdict('CONFORME')} · {verdict('PREUVES_INSUFFISANTES')} (an unknown fact is never assumed safe) · {verdict('A_REVOIR')} (the doctor may proceed with a written justification; his name is logged) · {verdict('BLOQUE')} (no override in the system). Rules may also attach an <b>OBLIGATION</b> (consent, information, notification) or flag a <b>GAP</b>. Principle: <b>only a binding source (law, regulator standard) can block</b>; a clinical recommendation can at most require review. The {n_regles} rules (<code>kb/regles_uae.json</code>) cite provision IDs; a missing fact (consultation mode, data location, written approval) gives INSUFFICIENT EVIDENCE rather than a block; the engine rebuilds each citation (text, article, official link, verification level) from the knowledge base and refuses to start if a rule cites an unknown provision.</p>
{table_regles()}
<p><b>Crisis mode.</b> Three institutional agents — health authority, reference hospital, crisis cell — each receive only their own fragments of information and never see the patient record. They record measures only on a binding, officially verified provision that confers a power to act (checked by the tool), and every data request they make goes through the jurist. Any of them, or the doctor, can ask the jurist a question. It searches the knowledge base, answers with the applicable provisions — legislation, institutional duties, emergency powers ({cc('CD14-A18')}), international obligations ({cc('IHR-A6')}; {cc('CRPD-A11')}) and global examples — links the relevant gaps, and states that the final decision is human.</p>

<h2><span>4</span>Knowledge base</h2>
<p>Built locally in formats ready for the ITU distributed vector store: <code>sources.json</code> ({len(base.sources)} instruments with authority, dates, official URL, verification level), <code>fiches.jsonl</code> ({len(base.fiches)} provisions: article, plain summary, short quote, themes), <code>lacunes.json</code> ({len(base.lacunes)} gaps), <code>regles_uae.json</code> ({n_regles} rules), <code>questions_test.jsonl</code> ({ev['n']} test questions) and <code>index/chunks.jsonl</code> ({n_chunks} self-contained chunks with metadata).</p>
<div class="grid2"><div>
<p><b>Content.</b> UAE host-country sources ({roles.get('primary', 0)}): federal laws on medical liability, ICT in health, personal data, medical products, people of determination and communicable diseases; MOHAP Resolution 51/2021; DoH Abu Dhabi AI policy and Responsible AI Standard; DHA AI policy and telehealth standards; UAE AI Charter; National AI Strategy 2031. Global examples ({roles.get('global_example', 0)}): UN CRPD, WHO (AI ethics, LMM guidance, IHR), UNESCO, EU AI Act, Product Liability Directive, MDR, Electronic Communications Code, NHS Accessible Information Standard, MHRA AI Airlock, ISO 9186-1, AU AI Strategy. Plus ITU references and FDA/label clinical references. A second jurisdiction, <b>Cameroon</b> ({roles.get('national_cm', 0)} texts, own rule file, <code>--pays CM</code>), shows the base is transposable.</p>
</div><div>
<p><b>Verification.</b> {niv.get('official_text', 0)} sources read on the official publisher's site, {niv.get('secondary_source', 0)} through a reliable secondary source, {niv.get('to_confirm', 0)} to confirm — the level appears in every citation. Article numbers are cited only when read. Arabic texts prevail. <code>telecharger_sources.py</code> downloads the originals and records their SHA-256 on first run; <code>--verifier</code> then flags any text changed online.</p>
<p><b>Retrieval (measured).</b> Dependency-free BM25 with a French→English lexicon, on {ev['n']} questions (English and French): recall@1 = {r['rappel@1']:.2f}, recall@3 = {r['rappel@3']:.2f}, recall@5 = {r['rappel@5']:.2f}, MRR = {ev['mrr']:.2f}. The same set will compare multilingual embeddings in the sandbox.</p>
</div></div>

<h2><span>5</span>Simulated error scenarios (progressive and fragmented)</h2>
<p>Scenarios release information fragment by fragment; each agent sees only its messages. <b>Automated evaluation</b> (<code>evaluer_agents.py</code>): {n_attendus} capability and safety expectations plus 6 safety invariants per scenario (checked on the hash-chained journal where possible) — 100 % in reference mode, also with a random order of turns; a <b>chaotic model</b> calling random tools never breaks them. <b>Formal verification</b>: rules with a written semantics (Kleene logic, verdict lattice, deny by default); {n_formel} safety and utility properties hold for <i>all</i> inputs (exhaustive enumeration + Z3 SMT proofs); a runtime monitor checks 10 invariants over 1,200 adversarial runs; 8 defects found and fixed. Outcomes below come from the reference runs.</p>
{table_scenarios()}

<h2><span>6</span>Policy, strategy and standards gaps</h2>
<p>The jurist records a gap when no binding text settles a situation it meets. Each gap lists what UAE texts already say, what is missing, and global policy examples — domain-specific findings, not recommendations to one country. Details: annex <i>Gap analysis</i> and <code>kb/lacunes.json</code>.</p>
{table_lacunes(court=True)}

<h2><span>7</span>Auditability</h2>
<ul>
<li><b>Hash-chained journal.</b> Each line holds time, agent, type (event, reasoning, action, message, verdict, gap), a frozen copy of the content, the previous hash and its own SHA-256 hash. Any later change to a line or to the order is detected (<code>verifier_journal.py --falsifier 10</code> shows it live). The first line records the configuration (models, temperature, order of turns, hashes of the rules and knowledge base) for reproducibility; <code>exporter_journal.py</code> turns any journal into a filterable HTML timeline.</li>
<li><b>Reasoning traces.</b> Each agent's reasoning is logged before its actions; every tool call is logged with its arguments and result, including refused calls.</li>
<li><b>Source attribution.</b> Every verdict and obligation lists provision IDs with the official link and verification level; every assistant suggestion carries its source ID.</li>
<li><b>Named human decisions.</b> Maintaining a REVIEW decision requires an authorised, active doctor and a written justification, both logged; a BLOCKED decision cannot be maintained. Journals are saved as JSON files the facility can archive for the 25-year retention required by {cc('ICT19-A20')}.</li>
</ul>

<h2><span>8</span>Use case on the ITU-T Y.3172 pipeline, mapped to the ITU AI Readiness Framework 2.0</h2>
<p>Each pipeline node lists the concrete data or function, the host-country documents that govern it, and the readiness factor · dimension (Report 2.0, January 2026) with the metric this prototype reports. All six factors are covered (data, research, deployment support, standards, open source and code, sandbox).</p>
<table class="y3172"><tr><th style="width:7%">Node</th><th style="width:37%">MEDIMCOM IA (data, format, metadata)</th><th style="width:27%">Governing documents (knowledge base)</th><th>Readiness factor · dimension → metric</th></tr>
<tr><td>SRC</td><td>Doctor's free text (FR/EN); patient's pictogram IDs as a JSON list (e.g. VENTRE, DOULEUR, CHIFFRE:7); {len(base.fiches)} legal provisions with official URL and verification level. Synthetic patients only.</td><td>ICT in Health Law 2/2019 (data stay in the UAE); PDPL 45/2021; People of Determination Law 29/2006</td><td>Data · D1 data/model marketplace → {len(base.sources)} open sources with links; D11 AI for inclusion → text-free input</td></tr>
<tr><td>C</td><td>Patient tablet (taps, session ID, time); doctor screen; download script freezing the SHA-256 of official texts</td><td>DHA Telehealth Standards v4 (accessible channel, emergency)</td><td>Deployment support · D6 human interface → image-only mode, fr/en/ar labels</td></tr>
<tr><td>PP</td><td>Assistant builds the patient state (confirmed / unconfirmed facts); identifiers stripped from messages to institutions; {n_chunks} knowledge chunks</td><td>PDPL 45/2021; MOHAP Res. 51/2021 (transfers abroad)</td><td>Data · D10 AI and policies → data sovereignty: local processing, no transfer abroad</td></tr>
<tr><td>M</td><td>Local 8B LLMs with tool calling (Ollama / OpenAI-compatible); BM25 retrieval (recall@3 = {r['rappel@3']:.2f}); {n_regles} deterministic rules</td><td>DoH Responsible AI Standard 2025; DHA AI Policy 2021</td><td>Research; Open source · D8 collaboration with AI → capability score vs scripted baseline</td></tr>
<tr><td>P</td><td>Jurist verdicts; doctor validates every message; named override; institutions need a binding basis in their own mandate</td><td>Medical Liability Law 4/2016; UAE AI Charter (human oversight)</td><td>Standards · D10 AI and policies → policy tested in 3 sandbox scenarios; {len(base.lacunes)} gaps</td></tr>
<tr><td>D</td><td>Typed agent messages; pictograms sent only after validation and the jurist's check</td><td>DHA Telehealth Standards (consent, explanation)</td><td>D7 strategy alignment → institutions coordinate through mandates</td></tr>
<tr><td>SINK</td><td>Doctor and patient screens; hash-chained journal; crisis board</td><td>Communicable Diseases Law 14/2014 (24-hour notification)</td><td>D11 AI for inclusion → comprehension rate of pictograms (ISO 9186-1 test, to run)</td></tr>
<tr><td>MLFO</td><td>Coordinator, simulated mode, evaluation bench (6 safety invariants), {n_tests} automated tests</td><td>ITU-T Y.3172</td><td>Sandbox · D13 digital infrastructure → runs offline on one laptop</td></tr>
</table>
<p class="note">Reference links of every material proposed to the knowledge base: <code>docs/soumission/KB_reference_links.md</code>.</p>

<h2><span>9</span>Limits and next steps</h2>
<ul>
<li>No real model ran in our build environment: reference results come from scripted policies; model modes are tested with mock and chaotic models. Next: <code>evaluer_agents.py --mode ollama</code> (<code>qwen3:8b</code>, <code>llama3.1:8b</code>).</li>
<li>Clinical rules (NSAID, misoprostol) are examples from public sources: they must be validated by a physician and replaced by the UAE formulary; allergy checks use names, brand names and drug classes, not a full drug database. Practitioners and the unregistered medicine are fictitious.</li>
<li>{niv.get('secondary_source', 0)} sources are known through secondary sources (e.g. Resolution 51/2021, whose official page could not be read) and {niv.get('to_confirm', 0)} remain to confirm (Cameroon); Arabic originals are not yet ingested; the DoH and DHA AI policies are due for revision — to re-check.</li>
<li>Agent 1 uses pictograms from existing databases (46 placeholder icons in the demo); engine interface: <code>docs/technique/CONTRAT_AGENT1.md</code>. Interface: prototype security only (doctor token; on Wi-Fi any device can answer as patient). <b>No user test has been run yet</b>: the protocol, printable booklet and analysis script (comprehension test inspired by ISO 9186-1, at least 20 deaf participants with an interpreter) are ready; only measured results will be claimed.</li>
</ul>
<h2><span>10</span>Key references (all {len(base.sources)} sources with links: <code>docs/soumission/KB_reference_links.md</code>)</h2>
<ol class="small">""" + "".join(f"<li>{e(base.sources[i]['short_title'])}, {e(str(base.sources[i]['date_issued']).split(' ')[0][:7])} — {e(base.sources[i]['url'])}</li>" for i in REFS) + """</ol>
"""
    return body


def annexe():
    body = f"""
<div class="eyebrow">MEDIMCOM IA · Annex to the technical report</div>
<h1>Gap analysis — policy, strategy and standards</h1>
<div class="meta">Team ShifaMiko · Version 1.1, 21 October 2026 · Generated from <code>kb/lacunes.json</code> and <code>kb/fiches.jsonl</code> · Verification levels: official text, secondary source, to confirm.</div>
<p><b>Method.</b> The jurist agent records a gap when it meets a situation that no binding text in the knowledge base settles, or that texts settle only in general terms. Gaps were found in two ways: <b>by trigger</b> (a rule or a question leads to a provision that is silent on the point) and <b>by absence</b> (no provision found at all). For each gap we list what UAE texts already say, what is missing, and global policy examples. In line with the hackathon brief, these are domain-specific findings with global examples, not recommendations addressed to one country.</p>
<table><tr><th style="width:5%">ID</th><th style="width:20%">Domain</th><th style="width:45%">Gap</th><th>Detected in the scenarios by</th></tr>
""" + "".join(f"<tr><td><b>{l['id']}</b></td><td>{e(l['domain'])}</td><td>{e(l['title'])}</td><td>{e(DETECTE[l['id']])}</td></tr>" for l in base.lacunes.values()) + "</table>"
    for l in base.lacunes.values():
        body += f"<h3>{l['id']} · {e(l['title'])}</h3>"
        body += f"<p><b>Situation.</b> {e(l['situation'])}</p>"
        body += "<p><b>What UAE texts already say.</b></p><ul>"
        body += "".join(f"<li>{e(x['says'])} <span class='small'>— {e(base.citer(x['fiche'], 'en'))}</span></li>" for x in l["existing_texts"]) or "<li>No provision found in the knowledge base.</li>"
        body += f"</ul><p><b>What is missing.</b> {e(l['missing'])}</p><p><b>Global examples.</b></p><ul>"
        body += "".join(f"<li>{e(x['how'])} <span class='small'>— {e(base.citer(x['fiche'], 'en'))}</span></li>" for x in l["global_examples"])
        body += f"</ul><p><b>How MEDIMCOM IA handles it today.</b> {e(l['medimcom_response'])}</p>"
    return body


DETECTE = {
    "L01": "Rule IA-SUGGESTION (doctor prescribes after an AI suggestion)",
    "L02": "Absence: no software classification criteria found",
    "L03": "Rule INFORMATION-ACCESSIBLE; advisor question in the crisis",
    "L04": "Rule CONSENTEMENT-PICTO; advisor question in the crisis",
    "L05": "Rule ENVOI-DIAGNOSTIC (treatment explained in pictograms)",
    "L06": "Rules HORS-EAU-SANS-EXCEPTION and ENTRAINEMENT-IA (foreign cloud AI)",
    "L07": "Absence: no rule on agent-to-agent interaction",
    "L08": "Advisor question on an AI incident",
    "L09": "Rule URGENCE-ACCESSIBLE (emergency of a deaf patient)",
}


def pdf(body, nom, titre):
    doc = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{titre}</title><style>{CSS}</style></head><body>{body}</body></html>'
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(doc, wait_until="load")
        pg.pdf(path=str(OUT / (nom + ".pdf")), format="A4", print_background=True, display_header_footer=True,
               header_template="<span></span>",
               footer_template=f'<div style="font-family:Inter;font-size:7px;color:#6A7A82;width:100%;padding:0 13mm;display:flex;justify-content:space-between"><span>{titre}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
               margin={"top": "11mm", "bottom": "12mm", "left": "13mm", "right": "13mm"})
        b.close()


def liens_kb() -> str:
    """Liste des liens de référence de tous les documents proposés à la base (exigence du hackathon)."""
    niveaux = {"official_text": "official text", "secondary_source": "secondary source", "to_confirm": "to confirm"}
    l = ["# MEDIMCOM IA — reference links of the materials proposed to the knowledge base", "",
         f"Team ShifaMiko · generated from `kb/sources.json` · {len(base.sources)} sources · {len(base.fiches)} provisions in `kb/fiches.jsonl`.",
         "Verification level: *official text* = read on the official publisher's site; *secondary source* = known through a law firm or the press; *to confirm* = listed, not yet read.", "",
         "| ID | Title | Authority | Date | Role | Verification | Link |", "|---|---|---|---|---|---|---|"]
    for i, x in base.sources.items():
        t = x["title"].replace("|", "/")
        l.append(f"| {i} | {t} | {x.get('authority', '')} | {str(x.get('date_issued', '')).split(' ')[0]} | {x.get('role', '')} | "
                 f"{niveaux.get(x['verification'], x['verification'])} | {x['url']} |")
    return "\n".join(l) + "\n"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "KB_reference_links.md").write_text(liens_kb(), encoding="utf-8")
    pdf(rapport(), "MEDIMCOM_IA_Technical_Report", "MEDIMCOM IA — Technical report · Team ShifaMiko")
    pdf(annexe(), "MEDIMCOM_IA_Gap_Analysis", "MEDIMCOM IA — Gap analysis · Team ShifaMiko")
    try:
        from pypdf import PdfReader
        n = len(PdfReader(str(OUT / "MEDIMCOM_IA_Technical_Report.pdf")).pages)
        print(f"Rapport : {n} pages" + ("  ⚠ plus de 5 pages : raccourcir le texte" if n > 5 else " (limite : 5)"))
    except ImportError:
        print("Vérifier à la main que le rapport tient en 5 pages (pip install pypdf pour le contrôle automatique).")
    print(f"PDF écrits dans {OUT}")
