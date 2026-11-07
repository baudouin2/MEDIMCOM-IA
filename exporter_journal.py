"""Exporte un journal en page HTML lisible (frise par événement), pour l'audit, le jury ou la vidéo.

    python exporter_journal.py sortie/journal.json                 # -> sortie/journal.html
    python exporter_journal.py sortie/journal.json -o audit.html

La page indique d'abord si le journal est intact (vérification des empreintes SHA-256), puis la
configuration (modèles, empreintes des règles et de la base), puis chaque événement avec ce que
chaque agent a pensé, fait, écrit et décidé. Filtres par agent et par type. Aucune dépendance.
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

COULEURS = {"traducteur": "#2A6F97", "assistant": "#3C8A5A", "juriste": "#C2571A", "medecin": "#5B4B8A",
            "autorite_sante": "#8A3B5B", "hopital": "#2F7F7F", "cellule_crise": "#7A6A1F", "coordinateur": "#56656D"}
LIBELLES = {"raisonnement": "pense", "reflexion_modele": "réflexion du modèle", "action": "agit", "message": "écrit",
            "verdict": "verdict", "lacune": "lacune", "mesure": "mesure", "incident": "incident", "evenement_libere": "événement",
            "degradation": "repli sans IA", "filet_de_securite": "filet de sécurité", "configuration": "configuration"}
VCOUL = {"BLOQUE": "#B42318", "A_REVOIR": "#B5541C", "PREUVES_INSUFFISANTES": "#8A6D00", "CONFORME": "#1D7A46"}
e = html.escape


def _court(x, n=400):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def corps_ligne(l: dict) -> str:
    c, t = l["contenu"], l["type"]
    if not isinstance(c, dict):
        return e(_court(c, 800))
    if t == "verdict":
        v = c.get("verdict", "?")
        quoi = c.get("medicament") or c.get("objet", "")
        items = "".join(f"<li>{e(x.get('detail', ''))} <span class='ref'>[{e(x.get('reference_courte', ''))}]</span></li>"
                        for x in c.get("constats", []))
        obl = "".join(f"<li class='obl'>Obligation : {e(x.get('detail', ''))} <span class='ref'>[{e(x.get('reference_courte', ''))}]</span></li>"
                      for x in c.get("obligations", []))
        return (f"<b>#{c.get('decision_id')} {e(str(quoi))}</b> → <span class='v' style='color:{VCOUL.get(v, '#333')}'>{e(v)}</span>"
                f"<ul>{items}{obl}</ul>")
    if t == "message":
        return f"<b>→ {e(c.get('a', ''))}</b> <span class='tag'>{e(c.get('type', ''))}</span> {e(_court(c.get('contenu', ''), 600))}"
    if t == "action":
        return f"<code>{e(c.get('outil', ''))}({e(_court(c.get('arguments', {}), 160))})</code> → {e(_court(c.get('resultat', ''), 260))}"
    if t == "evenement_libere":
        return f"<b>{e(c.get('description', ''))}</b>"
    if t == "lacune":
        return f"<b>{e(str(c.get('id') or ''))} {e(c.get('sujet', ''))}</b><br>{e(_court(c.get('detail', ''), 500))}"
    if t == "mesure":
        return f"<b>{e(c.get('mesure', ''))}</b> <span class='ref'>[{e(c.get('citation', ''))}]</span> — {e(c.get('justification', ''))}"
    if isinstance(c, str):
        return e(_court(c, 800))
    return f"<code>{e(_court(c, 500))}</code>"


def exporter(chemin: Path, sortie: Path) -> str:
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
        titre = c0.get("description", "Événement") if b[0]["type"] == "evenement_libere" and isinstance(c0, dict) else "Démarrage"
        h.append(f"<section><h2>{e(titre)}</h2>")
        for l in b:
            if l["type"] == "evenement_libere":
                continue
            coul = COULEURS.get(l["agent"], "#444")
            h.append(f"<div class='l' data-agent='{e(l['agent'])}' data-type='{e(l['type'])}'>"
                     f"<span class='n'>{l['n']}</span><span class='a' style='background:{coul}'>{e(l['agent'])}</span>"
                     f"<span class='t'>{e(LIBELLES.get(l['type'], l['type']))}</span><div class='c'>{corps_ligne(l)}</div></div>")
        h.append("</section>")
    filtres = "".join(f"<label><input type='checkbox' checked data-f='agent' value='{e(a)}'> {e(a)}</label>" for a in agents)
    filtres_t = "".join(f"<label><input type='checkbox' checked data-f='type' value='{e(t)}'> {e(LIBELLES.get(t, t))}</label>" for t in types)
    ok = etat == "Journal intact"
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Journal MEDIMCOM IA</title><style>
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
@media (max-width:700px){{.l{{grid-template-columns:32px 1fr;}} .t{{grid-column:2}} .c{{grid-column:1/3}}}}
</style></head><body><main>
<h1>Journal MEDIMCOM IA</h1>
<div class="etat">{'✔' if ok else '✘'} {e(etat)} — {len(j.lignes)} lignes chaînées par empreintes SHA-256 ({e(chemin.name)})</div>
<div class="conf"><b>Configuration :</b> <code>{e(json.dumps(conf, ensure_ascii=False)) if conf else 'non enregistrée'}</code></div>
<div class="filtres"><div><button id="resume">Vue résumée</button> <button id="tout">Tout afficher</button></div>
<div><b>Agents :</b> {filtres}</div><div><b>Types :</b> {filtres_t}</div></div>
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
    print(f"{exporter(src, dst)} · page écrite : {dst}")
