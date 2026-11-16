"""Exports a journal as a readable HTML page (timeline per event), for audit, the jury or the video.

    python exporter_journal.py sortie/journal.json                 # -> sortie/journal.html
    python exporter_journal.py sortie/journal.json -o audit.html

The page first says whether the journal is intact (SHA-256 fingerprints checked), then the configuration
(models, fingerprints of the rules and the base), then each event with what each agent thought, did, wrote and
decided. Filters by agent and by type. No dependency.
"""
import sys as _sys
for _flux in (_sys.stdout, _sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

import argparse
import html
import json
from pathlib import Path

from medimcom.journal import Journal
from medimcom.responsabilites import rapport

COULEURS = {"traducteur": "#2A6F97", "assistant": "#3C8A5A", "juriste": "#C2571A", "medecin": "#5B4B8A",
            "autorite_sante": "#8A3B5B", "hopital": "#2F7F7F", "cellule_crise": "#7A6A1F", "coordinateur": "#56656D"}
LIBELLES = {"raisonnement": "pense", "reflexion_modele": "réflexion du modèle", "action": "agit", "message": "écrit",
            "verdict": "verdict", "lacune": "lacune", "mesure": "mesure", "incident": "incident", "evenement_libere": "événement",
            "degradation": "repli sans IA", "filet_de_securite": "filet de sécurité", "configuration": "configuration"}
VCOUL = {"BLOQUE": "#B42318", "A_REVOIR": "#B5541C", "PREUVES_INSUFFISANTES": "#8A6D00", "CONFORME": "#1D7A46"}
e = html.escape
LANGUE = "fr"          # language of the page: the doctor's (fr, en, ar); the journal itself stays as written
FIXE = {  # fixed texts of the page
    "pense": ("thinks", "يفكّر"), "réflexion du modèle": ("model's reasoning", "تفكير النموذج"), "agit": ("acts", "يتصرّف"),
    "écrit": ("writes", "يكتب"), "verdict": ("verdict", "حكم"), "lacune": ("gap", "ثغرة"), "mesure": ("measure", "تدبير"),
    "incident": ("incident", "حادثة"), "événement": ("event", "حدث"), "repli sans IA": ("fallback without AI", "عودة دون ذكاء اصطناعي"),
    "filet de sécurité": ("safety net", "شبكة أمان"), "configuration": ("configuration", "الإعداد"),
    "Obligation : ": ("Obligation: ", "التزام: "), "décisions suivies": ("decisions followed", "قرارات متابَعة"),
    "envoyées au patient": ("sent to the patient", "أُرسلت إلى المريض"), "bloquées par le juriste": ("blocked by the legal agent", "حظرها الوكيل القانوني"),
    "décisions humaines signées": ("signed human decisions", "قرارات بشرية موقّعة"), "défaillances de l'IA": ("AI failures", "إخفاقات الذكاء الاصطناعي"),
    "actions refusées par un garde-fou": ("actions refused by a safeguard", "إجراءات رفضتها ضمانة"), "lacunes du droit": ("legal gaps", "ثغرات قانونية"),
    "événements de crise": ("crisis events", "أحداث الأزمة"), "Responsabilités et défaillances": ("Responsibilities and failures", "المسؤوليات والإخفاقات"),
    "Calculé à partir du journal chaîné ci-dessous (numéros de ligne « l. ») : rien n'est ajouté ni résumé à la main.": (
        "Computed from the chained log below (line numbers “l.”): nothing is added or summarised by hand.",
        "محسوب من السجل المتسلسل أدناه (أرقام الأسطر «l.»): لا شيء مُضاف أو مُلخَّص يدويًا."),
    "Aucun message n'atteint le patient sans la validation nommée d'un médecin ; le juriste peut bloquer, jamais envoyer.": (
        "No message reaches the patient without a doctor's named approval; the legal agent can block, never send.",
        "لا تصل أي رسالة إلى المريض دون اعتماد طبيب باسمه؛ يستطيع الوكيل القانوني الحظر ولا يرسل أبدًا."),
    "Chaîne de décision (proposé par → jugé par le juriste → décidé par)": (
        "Decision chain (proposed by → judged by the legal agent → decided by)", "سلسلة القرار (اقترحه ← حكم عليه الوكيل القانوني ← قرّره)"),
    "Objet": ("Object", "الموضوع"), "Contenu": ("Content", "المحتوى"), "Proposé par": ("Proposed by", "اقترحه"),
    "Juriste (base, textes)": ("Legal agent (basis, texts)", "الوكيل القانوني (الأساس، النصوص)"), "Responsabilité": ("Responsibility", "المسؤولية"),
    "Issue": ("Outcome", "النتيجة"), "Aucune décision.": ("No decision.", "لا قرارات."), "Défaillances de l'IA": ("AI failures", "إخفاقات الذكاء الاصطناعي"),
    "Aucune.": ("None.", "لا شيء."), "Actions des agents refusées par un garde-fou": ("Agents' actions refused by a safeguard", "إجراءات الوكلاء التي رفضتها ضمانة"),
    "Lacunes du droit (situations qu'aucun texte lu ne règle)": ("Legal gaps (situations no text read settles)", "ثغرات قانونية (حالات لا يحسمها أي نص مقروء)"),
    "Crise : mesures, incidents, refus faute de base légale": ("Crisis: measures, incidents, refusals for lack of a legal basis", "الأزمة: التدابير والحوادث والرفض لغياب أساس قانوني"),
    "Aucun événement de crise.": ("No crisis event.", "لا أحداث أزمة."), "action(s) refusée(s) — ex.": ("action(s) refused — e.g.", "إجراء(ات) مرفوضة — مثال:"),
    "Événement": ("Event", "حدث"), "Démarrage": ("Start", "البدء"), "Journal MEDIMCOM IA": ("MEDIMCOM AI log", "سجل MEDIMCOM IA"),
    "lignes chaînées par empreintes SHA-256": ("lines chained by SHA-256 fingerprints", "سطرًا متسلسلة ببصمات SHA-256"),
    "Configuration :": ("Configuration:", "الإعداد:"), "non enregistrée": ("not recorded", "غير مسجّل"), "Journal complet": ("Full log", "السجل الكامل"),
    "Vue résumée": ("Summary view", "عرض موجز"), "CONFORME": ("COMPLIANT", "مطابق"), "BLOQUE": ("BLOCKED", "محظور"),
    "A_REVOIR": ("TO REVIEW", "بحاجة إلى مراجعة"), "PREUVES_INSUFFISANTES": ("INSUFFICIENT EVIDENCE", "أدلة غير كافية"),
    "MAINTENUE": ("MAINTAINED", "مُبقًى عليه"), "LOI": ("LAW", "قانون"), "NORME": ("STANDARD", "معيار"),
    "RECOMMANDATION": ("RECOMMENDATION", "توصية"), "EXEMPLE_MONDIAL": ("GLOBAL EXAMPLE", "مثال عالمي"), "GARDE_FOU": ("SAFEGUARD", "ضمانة"),
    "envoi_patient": ("message to the patient", "رسالة إلى المريض"), "prescription": ("prescription", "وصفة"),
    "partage_donnees": ("data sharing", "مشاركة البيانات"), "traducteur": ("translator", "المترجم"), "assistant": ("assistant", "المساعد"),
    "juriste": ("legal agent", "الوكيل القانوني"), "medecin": ("doctor", "الطبيب"), "autorite_sante": ("health authority", "السلطة الصحية"),
    "hopital": ("hospital", "المستشفى"), "cellule_crise": ("crisis cell", "خلية الأزمة"), "coordinateur": ("coordinator", "المنسّق"), "patient": ("patient", "المريض"),
    "ENGAGEMENT_INTERNATIONAL": ("INTERNATIONAL COMMITMENT", "التزام دولي"), "systeme": ("system", "النظام"), "Tout afficher": ("Show all", "عرض الكل"), "Agents :": ("Agents:", "الوكلاء:"), "Types :": ("Types:", "الأنواع:"),
}


def f(texte: str) -> str:
    """A fixed text of the page, in the page's language."""
    return texte if LANGUE == "fr" else FIXE.get(texte, (texte, texte))[0 if LANGUE == "en" else 1]


def t(x) -> str:
    """A text written in the journal by the system (French), shown in the page's language."""
    from medimcom.langues import traduire
    return traduire(x if isinstance(x, str) else str(x), LANGUE)


def _court(x, n=400):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def corps_ligne(l: dict) -> str:
    c, ty = l["contenu"], l["type"]
    if not isinstance(c, dict):
        return e(_court(t(c) if isinstance(c, str) else c, 800))
    if ty == "verdict":
        v = c.get("verdict", "?")
        quoi = c.get("medicament") or c.get("objet", "")
        items = "".join(f"<li>{e(t(x.get('detail', '')))} <span class='ref'>[{e(x.get('reference_courte', ''))}]</span></li>"
                        for x in c.get("constats", []))
        obl = "".join(f"<li class='obl'>{f('Obligation : ')}{e(t(x.get('detail', '')))} <span class='ref'>[{e(x.get('reference_courte', ''))}]</span></li>"
                      for x in c.get("obligations", []))
        return (f"<b>#{c.get('decision_id')} {e(str(quoi))}</b> → <span class='v' style='color:{VCOUL.get(v, '#333')}'>{e(f(v))}</span>"
                f"<ul>{items}{obl}</ul>")
    if ty == "message":
        return f"<b>→ {e(c.get('a', ''))}</b> <span class='tag'>{e(c.get('type', ''))}</span> {e(_court(t(c.get('contenu', '')), 600))}"
    if ty == "action":
        return f"<code>{e(c.get('outil', ''))}({e(_court(c.get('arguments', {}), 160))})</code> → {e(_court(t(c.get('resultat', '')), 260))}"
    if ty == "evenement_libere":
        return f"<b>{e(c.get('description', ''))}</b>"
    if ty == "lacune":
        return f"<b>{e(str(c.get('id') or ''))} {e(t(c.get('sujet', '')))}</b><br>{e(_court(t(c.get('detail', '')), 500))}"
    if ty == "mesure":
        return f"<b>{e(t(c.get('mesure', '')))}</b> <span class='ref'>[{e(c.get('citation', ''))}]</span> — {e(t(c.get('justification', '')))}"
    if ty == "raisonnement" and isinstance(c.get("texte"), str):
        return e(_court(t(c["texte"]), 800))
    if isinstance(c, str):
        return e(_court(t(c), 800))
    return f"<code>{e(_court(c, 500))}</code>"


def _humain(h: dict) -> str:
    just = f" : « {e(str(h['justification']))} »" if h.get("justification") else ""
    return f"<div class='ref'>l.{h['ligne']} {e(str(h['par']))} {e(t(h['action']))}{just}</div>"


def html_rapport(r: dict) -> str:
    """Responsibility report (medimcom/responsabilites.py), at the top of the journal."""
    b = r["bilan"]
    cartes = "".join(f"<div class='k'><b>{v}</b><span>{e(t)}</span></div>" for t, v in (
        (f("décisions suivies"), b["decisions"]), (f("envoyées au patient"), b["envoyes"]), (f("bloquées par le juriste"), b["bloques_par_le_juriste"]),
        (f("décisions humaines signées"), b["decisions_humaines"]), (f("défaillances de l'IA"), b["defaillances"]),
        (f("actions refusées par un garde-fou"), b["actions_refusees"]), (f("lacunes du droit"), b["lacunes"]), (f("événements de crise"), b["evenements_de_crise"])))
    lignes = "".join(
        f"<tr><td>#{d['id']}</td><td>{e(f(str(d['type'])))}</td><td>{e(_court(t(str(d['texte'] or '')), 70))}</td><td>{e(f(str(d['auteur'])))}</td>"
        f"<td>{e(f(d['dernier_verdict']['verdict'])) if d['dernier_verdict'] else '—'}"
        f"<div class='ref'>{e(', '.join(f(x) for x in d['dernier_verdict']['bases'])) if d['dernier_verdict'] else ''}"
        f"{(' · ' + e(' ; '.join(d['dernier_verdict']['references']))) if d['dernier_verdict'] and d['dernier_verdict']['references'] else ''}</div></td>"
        f"<td>{e(t(d['responsabilite']))}{''.join(_humain(h) for h in d['humains'])}</td>"
        f"<td>{e(t(d['fin']) if d['fin'] else '—')}</td></tr>" for d in r["chaines"])
    defs = "".join(f"<li><span class='n'>l.{x['ligne']}</span> <b>{e(t(x['quoi']))}</b> ({e(x['agent'])}) {e(t(x['detail']))}</li>" for x in r["defaillances"][:60])
    refus = "".join(f"<li><b>{e(a)}</b> : {n} {f('action(s) refusée(s) — ex.')} {e(t(r['exemples_refus'].get(a, '')))}</li>" for a, n in r["refus_par_agent"].items())
    lac = "".join(f"<li><span class='n'>l.{x['ligne']}</span> <b>{e(str(x['id'] or ''))} {e(t(str(x['sujet'] or '')))}</b> — {e(t(x['detail']))}</li>" for x in r["lacunes"])
    cri = "".join(f"<li><span class='n'>l.{x['ligne']}</span> <b>{e(x['agent'])}</b> {e(x['type'])} : {e(t(x['detail']))}</li>" for x in r["crise"][:40])
    return f"""<section class="rapport"><h2>{f("Responsabilités et défaillances")}</h2>
<p class="ref">{f("Calculé à partir du journal chaîné ci-dessous (numéros de ligne « l. ») : rien n'est ajouté ni résumé à la main.")}
{f("Aucun message n'atteint le patient sans la validation nommée d'un médecin ; le juriste peut bloquer, jamais envoyer.")}</p>
<div class="kpi">{cartes}</div>
<h3>{f("Chaîne de décision (proposé par → jugé par le juriste → décidé par)")}</h3>
<div class="tab"><table><tr><th>#</th><th>{f("Objet")}</th><th>{f("Contenu")}</th><th>{f("Proposé par")}</th><th>{f("Juriste (base, textes)")}</th><th>{f("Responsabilité")}</th><th>{f("Issue")}</th></tr>{lignes or '<tr><td colspan=7>' + f('Aucune décision.') + '</td></tr>'}</table></div>
<h3>{f("Défaillances de l'IA")}</h3><ul>{defs or '<li>' + f('Aucune.') + '</li>'}</ul>
<h3>{f("Actions des agents refusées par un garde-fou")}</h3><ul>{refus or '<li>' + f('Aucune.') + '</li>'}</ul>
<h3>{f("Lacunes du droit (situations qu'aucun texte lu ne règle)")}</h3><ul>{lac or '<li>' + f('Aucune.') + '</li>'}</ul>
<h3>{f("Crise : mesures, incidents, refus faute de base légale")}</h3><ul>{cri or '<li>' + f('Aucun événement de crise.') + '</li>'}</ul>
</section>"""


def exporter(chemin: Path, sortie: Path, langue: str = "fr") -> str:
    global LANGUE
    LANGUE = langue if langue in ("fr", "en", "ar") else "fr"
    j = Journal.charger(chemin)
    etat = j.verifier()
    agents = sorted({l["agent"] for l in j.lignes})
    types = sorted({l["type"] for l in j.lignes})
    conf = next((l["contenu"] for l in j.lignes if l["type"] == "configuration"), None)
    blocs, courant = [], []
    for l in j.lignes:
        if l["type"] == "evenement_libere" and courant:
            blocs.append(courant)
            courant = []
        courant.append(l)
    if courant:
        blocs.append(courant)
    h = []
    for b in blocs:
        c0 = b[0]["contenu"]
        titre = c0.get("description", f("Événement")) if b[0]["type"] == "evenement_libere" and isinstance(c0, dict) else f("Démarrage")
        h.append(f"<section><h2>{e(titre)}</h2>")
        for l in b:
            if l["type"] == "evenement_libere":
                continue
            coul = COULEURS.get(l["agent"], "#444")
            h.append(f"<div class='l' data-agent='{e(l['agent'])}' data-type='{e(l['type'])}'>"
                     f"<span class='n'>{l['n']}</span><span class='a' style='background:{coul}'>{e(l['agent'])}</span>"
                     f"<span class='t'>{e(f(LIBELLES.get(l['type'], l['type'])))}</span><div class='c'>{corps_ligne(l)}</div></div>")
        h.append("</section>")
    filtres = "".join(f"<label><input type='checkbox' checked data-f='agent' value='{e(a)}'> {e(f(a))}</label>" for a in agents)
    filtres_t = "".join(f"<label><input type='checkbox' checked data-f='type' value='{e(ty)}'> {e(f(LIBELLES.get(ty, ty)))}</label>" for ty in types)
    ok = etat == "Journal intact"
    page = f"""<!doctype html><html lang="{LANGUE}" dir="{'rtl' if LANGUE == 'ar' else 'ltr'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{f("Journal MEDIMCOM IA")}</title><style>
:root{{--fond:#F7F8F9;--carte:#fff;--texte:#1E2B31;--doux:#5A6A72;--trait:#DDE3E6}}
body{{margin:0;background:var(--fond);color:var(--texte);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:16px}}
h1{{font-size:22px;margin:4px 0 8px}} h2{{font-size:15px;margin:18px 0 6px;color:#16262E;border-bottom:1px solid var(--trait);padding-bottom:4px}}
.etat{{padding:8px 12px;border-radius:8px;font-weight:600;margin:8px 0;background:{'#E6F4EC' if ok else '#FDECEA'};color:{'#1D7A46' if ok else '#B42318'}}}
.conf{{background:var(--carte);border:1px solid var(--trait);border-radius:8px;padding:8px 12px;font-size:13px}}
.filtres{{position:sticky;top:0;background:var(--fond);padding:8px 0;border-bottom:1px solid var(--trait);z-index:2}}
.filtres label{{margin-right:10px;white-space:nowrap;font-size:12.5px}}
.l{{display:grid;grid-template-columns:40px 120px 110px 1fr;gap:8px;align-items:start;background:var(--carte);border:1px solid var(--trait);border-radius:6px;padding:6px 8px;margin:4px 0}}
.n{{color:var(--doux);font-size:12px}} .a{{color:#fff;border-radius:4px;padding:1px 6px;font-size:12px;text-align:center}}
.t{{color:var(--doux);font-size:12px}} .c ul{{margin:4px 0 0 18px;padding:0}} .ref{{color:var(--doux);font-size:12px}}
.v{{font-weight:700}} .tag{{background:#EEF2F4;border-radius:4px;padding:0 5px;font-size:12px}} .obl{{color:#4A5A62}}
code{{font-size:12px;background:#EEF2F4;border-radius:4px;padding:0 3px;word-break:break-word}}
.rapport{{background:var(--carte);border:1px solid var(--trait);border-radius:8px;padding:10px 14px;margin:10px 0}}
.rapport h3{{font-size:13.5px;margin:14px 0 4px}} .kpi{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}}
.k{{background:var(--fond);border-radius:6px;padding:6px 8px}} .k b{{display:block;font-size:18px}} .k span{{font-size:12px;color:var(--doux)}}
.tab{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:12.5px}} th,td{{border-bottom:1px solid var(--trait);padding:4px 6px;text-align:left;vertical-align:top}}
@media (max-width:700px){{.l{{grid-template-columns:32px 1fr;}} .t{{grid-column:2}} .c{{grid-column:1/3}}}}
</style></head><body><main>
<h1>{f("Journal MEDIMCOM IA")}</h1>
<div class="etat">{'✔' if ok else '✘'} {e(t(etat))} — {len(j.lignes)} {f("lignes chaînées par empreintes SHA-256")} ({e(chemin.name)})</div>
<div class="conf"><b>{f("Configuration :")}</b> <code>{e(json.dumps(conf, ensure_ascii=False)) if conf else f('non enregistrée')}</code></div>
{html_rapport(rapport(j.lignes))}
<h2>{f("Journal complet")}</h2>
<div class="filtres"><div><button id="resume">{f("Vue résumée")}</button> <button id="tout">{f("Tout afficher")}</button></div>
<div><b>{f("Agents :")}</b> {filtres}</div><div><b>{f("Types :")}</b> {filtres_t}</div></div>
{''.join(h)}
</main><script>
function filtrer(){{
 const on=f=>[...document.querySelectorAll(`.filtres input[data-f="${{f}}"]:checked`)].map(x=>x.value);
 const A=on('agent'),T=on('type');
 document.querySelectorAll('.l').forEach(l=>{{l.style.display=(A.includes(l.dataset.agent)&&T.includes(l.dataset.type))?'':'none'}});
}}
document.querySelectorAll('.filtres input').forEach(i=>i.addEventListener('change',filtrer));
const DETAIL=['action','etat','decision','echange','configuration','question','suggestion_retiree'];
document.getElementById('resume').onclick=()=>{{document.querySelectorAll('.filtres input[data-f="type"]').forEach(i=>i.checked=!DETAIL.includes(i.value));filtrer();}};
document.getElementById('tout').onclick=()=>{{document.querySelectorAll('.filtres input').forEach(i=>i.checked=true);filtrer();}};
</script></body></html>"""
    sortie.write_text(page, encoding="utf-8")
    return etat


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("chemin")
    p.add_argument("-o", "--sortie", default=None)
    a = p.parse_args()
    src = Path(a.chemin)
    dst = Path(a.sortie) if a.sortie else src.with_suffix(".html")
    print(f"{exporter(src, dst)} · page written: {dst}")
