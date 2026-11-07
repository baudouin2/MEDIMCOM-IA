"""Fiche de présentation du projet (1 page A4, en français), générée à partir des chiffres réels du dépôt.

    python outils/generer_fiche.py          # -> docs/equipe/MEDIMCOM_IA_Fiche_projet.pdf

Nécessite : pip install playwright pypdf && python -m playwright install chromium
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "kb" / "outils"))
from medimcom.base import BaseConnaissances  # noqa: E402
from medimcom.bibliotheque import CATALOGUE  # noqa: E402
from medimcom.regles import MoteurRegles  # noqa: E402
import evaluer_recherche  # noqa: E402

KB = REPO / "kb"
base = BaseConnaissances(KB)
qs = [json.loads(l) for l in (KB / "questions_test.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ev = evaluer_recherche.evaluer(base, qs)
n_regles = sum(1 for _ in MoteurRegles(KB / "regles_uae.json", base)._toutes_les_regles())
n_tests = (REPO / "tests" / "test_noyau.py").read_text(encoding="utf-8").count("\ndef test_")
n_attendus = sum(len(json.loads(c.read_text(encoding="utf-8")).get("attendus", [])) for c in (REPO / "scenarios").glob("*.json"))
n_scen = len(list((REPO / "scenarios").glob("*.json")))
niv = {}
for s in base.sources.values():
    niv[s["verification"]] = niv.get(s["verification"], 0) + 1
r3 = ev["rappel"]["rappel@3"]
SORTIE = REPO / "docs" / "equipe" / "MEDIMCOM_IA_Fiche_projet.pdf"

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; color: #1B2730; font-size: 8.4pt; line-height: 1.34; }
.page { padding: 8.5mm 13mm 5mm 13mm; }
.entete { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1.4pt solid #12324A; padding-bottom: 2.2mm; }
.surtitre { font-size: 7.2pt; letter-spacing: .7pt; text-transform: uppercase; color: #3C6E91; font-weight: 600; }
h1 { font-size: 17pt; margin: 1mm 0 .6mm; color: #12324A; letter-spacing: -.2pt; }
.soustitre { font-size: 9.6pt; color: #33454F; }
.meta { text-align: right; font-size: 7.6pt; color: #4A5A64; line-height: 1.45; white-space: nowrap; padding-left: 6mm; }
.meta b { color: #12324A; }
h2 { font-size: 8.8pt; color: #12324A; text-transform: uppercase; letter-spacing: .5pt; margin: 2.7mm 0 1mm; padding-bottom: .5mm; border-bottom: .5pt solid #C9D3DA; }
p { margin: 0 0 1.2mm; }
ul { margin: 0 0 1mm; padding-left: 4mm; } li { margin-bottom: .6mm; }
.deux { display: grid; grid-template-columns: 1fr 1fr; gap: 0 6mm; }
table { width: 100%; border-collapse: collapse; font-size: 7.8pt; margin-top: .6mm; }
th { text-align: left; color: #12324A; font-weight: 600; border-bottom: .8pt solid #12324A; padding: .7mm 1.2mm; }
td { border-bottom: .4pt solid #D9E1E6; padding: .6mm 1.2mm; vertical-align: top; }
.chiffres { display: grid; grid-template-columns: repeat(6, 1fr); gap: 2mm; margin: 1.2mm 0 .4mm; }
.chiffres div { border: .5pt solid #C9D3DA; border-radius: 1.2mm; padding: 1mm 1.4mm; }
.chiffres b { display: block; font-size: 12pt; color: #12324A; line-height: 1.1; }
.chiffres span { font-size: 6.9pt; color: #4A5A64; }
.encadre { background: #F2F5F7; border-left: 2pt solid #12324A; padding: 1.6mm 2.4mm; margin: 2.4mm 0 1mm; }
.statut { margin-top: 1.2mm; font-size: 8pt; color: #12324A; }
.schema { margin: 1.2mm auto .2mm; width: 88%; }
.pied { margin-top: 2.6mm; padding-top: 1.4mm; border-top: .5pt solid #C9D3DA; font-size: 6.9pt; color: #5A6A72; display: flex; justify-content: space-between; }
"""


def schema() -> str:
    """Schéma de l'architecture : qui parle à qui."""
    N, F, A, T = "#12324A", "#FFFFFF", "#E8EFF5", "#33454F"

    def boite(x, y, w, h, titre, sous="", fond=A, epais=1):
        o = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fond}" stroke="{N}" stroke-width="{epais}"/>'
        ty = y + (17 if sous else h / 2 + 4)
        o += f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-size="10.5" font-weight="700" fill="{N}">{titre}</text>'
        if sous:
            o += f'<text x="{x + w / 2}" y="{y + 31}" text-anchor="middle" font-size="8.6" fill="{T}">{sous}</text>'
        return o

    def fleche(x1, y1, x2, y2, txt="", tx=None, ty=None, tirets=False):
        d = ' stroke-dasharray="4 3"' if tirets else ""
        o = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{N}" stroke-width="1.1" marker-end="url(#f)"{d}/>'
        if txt:
            o += f'<text x="{tx if tx is not None else (x1 + x2) / 2}" y="{ty if ty is not None else (y1 + y2) / 2 - 4}" text-anchor="middle" font-size="8.2" fill="{T}">{txt}</text>'
        return o

    s = ('<svg viewBox="0 0 720 258" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="Inter, Arial, sans-serif">'
         f'<defs><marker id="f" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
         f'<path d="M0,0 L8,4 L0,8 z" fill="{N}"/></marker></defs>')
    s += boite(8, 8, 150, 46, "Médecin", "écrit, valide, décide", F, 1.8)
    s += boite(285, 8, 150, 46, "Agent 1 · Traducteur", "texte ⇄ pictogrammes")
    s += boite(562, 8, 150, 46, "Patient sourd", "lit et répond en images", F, 1.8)
    s += fleche(158, 31, 283, 31, "valide chaque envoi", ty=25)
    s += fleche(435, 25, 560, 25, "pictogrammes", ty=19)
    s += fleche(560, 41, 437, 41, "réponses en pictogrammes", ty=52)
    s += f'<rect x="8" y="92" width="704" height="36" rx="5" fill="#F2F5F7" stroke="{N}" stroke-width="1"/>'
    s += f'<text x="360" y="108" text-anchor="middle" font-size="10.2" font-weight="700" fill="{N}">Dossier de consultation partagé</text>'
    s += f'<text x="360" y="121" text-anchor="middle" font-size="8.4" fill="{T}">état du patient · questions · suggestions · décisions · verdicts — un coordinateur y libère les événements, sans donner d’ordre</text>'
    s += fleche(360, 56, 360, 90, tirets=False) + fleche(360, 90, 360, 58)
    s += boite(110, 160, 180, 46, "Agent 3 · Assistant", "état du patient, suggestions")
    s += boite(430, 160, 180, 46, "Agent 2 · Juriste", "contrôle légal et conseil")
    s += fleche(200, 130, 200, 158) + fleche(200, 158, 200, 132)
    s += fleche(520, 130, 520, 158) + fleche(520, 158, 520, 132)
    s += fleche(292, 183, 428, 183, "messages directs", ty=177) + fleche(428, 189, 294, 189)
    s += boite(626, 160, 86, 46, "Droit des EAU", "base vérifiée", F)
    s += fleche(612, 183, 624, 183)
    s += f'<path d="M110 183 H40 V56" fill="none" stroke="{N}" stroke-width="1.1" marker-end="url(#f)"/>'
    s += f'<text x="44" y="150" font-size="8.2" fill="{T}">suggestions :</text><text x="44" y="160" font-size="8.2" fill="{T}">valide ou ignore</text>'
    s += f'<path d="M520 92 V74 H120 V58" fill="none" stroke="{N}" stroke-width="1.1" stroke-dasharray="4 3" marker-end="url(#f)"/>'
    s += f'<text x="230" y="70" text-anchor="middle" font-size="8.2" fill="{T}">verdicts sourcés : conforme · à revoir · bloqué</text>'
    s += boite(8, 222, 300, 30, "Journal infalsifiable (empreintes SHA-256)", fond="#F2F5F7")
    s += boite(380, 222, 332, 30, "Crise : autorité de santé · hôpital · cellule de crise", fond=F)
    s += fleche(520, 208, 520, 220, tirets=True)
    return s + "</svg>"


def html() -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>MEDIMCOM IA · Fiche projet</title><style>{CSS}</style></head>
<body><div class="page">
<div class="entete">
  <div>
    <div class="surtitre">ITU AI for Good Lab / Sandbox Hackathon – Émirats arabes unis · Fiche projet</div>
    <h1>MEDIMCOM IA</h1>
    <div class="soustitre">Des agents d'IA autonomes pour des consultations médicales sûres, légales et accessibles aux patients sourds</div>
    <div class="statut"><b>Statut :</b> prototype en cours de développement</div>
  </div>
  <div class="meta"><b>Équipe ShifaMiko</b><br>Baudouin Nkana Bilong (coordination)<br>Franck Ndonkou · Fotsing Engoulou<br>Faculté des sciences<br>Université de Yaoundé I</div>
</div>

<h2>1. Problème</h2>
<p>Sans interprète en langue des signes, une personne sourde, surtout si elle lit peu, ne peut ni décrire ses symptômes ni comprendre le traitement prescrit. Des informations critiques se perdent (grossesse, allergies, traitements en cours), le consentement n'est pas éclairé, les consignes sont mal comprises, et les interprètes manquent, surtout dans l'urgence. L'IA peut aider, mais seulement dans un cadre strict : elle assiste, le médecin décide, et les données de santé restent protégées.</p>

<h2>2. Solution</h2>
<p>Le médecin écrit ; le patient lit et répond en <b>pictogrammes</b>. Trois agents d'IA autonomes collaborent autour d'un <b>dossier de consultation partagé</b> : chacun observe le dossier, raisonne et agit avec ses propres outils, et les agents se parlent directement. Rien n'atteint le patient sans la validation du médecin et le contrôle du juriste.</p>
<div class="schema">{schema()}</div>

<h2>3. Les agents</h2>
<table>
<tr><th style="width:15%">Agent</th><th style="width:29%">But</th><th style="width:30%">Ce qu'il décide seul</th><th>Limites (imposées dans ses outils)</th></tr>
<tr><td><b>1 · Traducteur</b></td><td>Que le médecin et le patient se comprennent vraiment</td><td>Comment traduire, quand combiner des pictogrammes en une seule image, quand faire confirmer le patient</td><td>Aucun envoi sans validation du médecin et feu vert du juriste</td></tr>
<tr><td><b>2 · Juriste</b></td><td>Que rien d'illégal ou de dangereux n'atteigne le patient</td><td>Quand revérifier une décision ; quelle obligation rappeler (consentement, déclaration) ; quelle lacune du droit signaler</td><td>Verdicts par règles fixes, toujours avec la source ; ne décide pas à la place du médecin</td></tr>
<tr><td><b>3 · Assistant</b></td><td>Un état du patient fiable et complet</td><td>Ce qui manque, quelle question faire poser, quoi suggérer, quand retirer une suggestion</td><td>Ne parle jamais au patient ; ne prescrit pas ; le médecin valide ou ignore</td></tr>
<tr><td><b>Institutions</b> (crise)</td><td>Répondre à une crise sanitaire ; la cellule de crise coordonne l'autorité de santé et l'hôpital</td><td>Quelle mesure prendre dans leur mandat, quelle information demander</td><td>Pas d'accès au dossier du patient ; une mesure exige une base légale contraignante</td></tr>
<tr><td><b>Coordinateur</b></td><td>Faire avancer la consultation ou la crise</td><td>Libère les événements un à un ; arrête quand plus aucun agent n'agit</td><td>Ne donne aucun ordre et ne décide rien : chaque agent choisit lui-même d'agir</td></tr>
</table>

<div class="deux"><div>
<h2>4. Avantages</h2>
<ul>
<li><b>Autonomie du patient</b> : il communique sans interprète ni proche, et garde sa confidentialité.</li>
<li><b>Sécurité</b> : double contrôle (médecin et juriste) avant tout envoi ; une information inconnue n'est jamais supposée sans danger.</li>
<li><b>Conformité vérifiable</b> : chaque verdict cite la disposition légale, son lien officiel et son niveau de vérification.</li>
<li><b>Traçabilité</b> : raisonnements, messages et décisions sont enregistrés dans un journal qui révèle toute modification.</li>
<li><b>Sobriété et souveraineté</b> : modèles ouverts exécutés en local, sans transfert de données de santé.</li>
<li><b>Transposable</b> : la base juridique se remplace pour un autre pays sans changer les agents.</li>
</ul>
</div><div>
<h2>5. Cadre légal, éthique et UIT</h2>
<ul>
<li>Base de connaissances vérifiée : droit des Émirats (responsabilité médicale, TIC en santé, données personnelles, personnes en situation de handicap, maladies transmissibles, normes IA du DoH et de la DHA) et exemples internationaux (ONU, OMS, UE, NHS, ISO).</li>
<li><b>Textes juridiques officiels</b> ; <b>patients fictifs</b> pour les tests (aucune donnée de santé réelle) ; <b>pictogrammes issus de bases existantes</b>.</li>
<li>Cas d'usage décrit selon le pipeline <b>UIT-T Y.3172</b> et relié au <b>cadre UIT de préparation à l'IA 2.0</b>, notamment la dimension <i>IA pour l'inclusion</i>.</li>
<li>Lacunes du droit identifiées et illustrées par des exemples mondiaux.</li>
</ul>
</div></div>


</div></body></html>"""


if __name__ == "__main__":
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(html(), wait_until="load")
        pg.pdf(path=str(SORTIE), format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    from pypdf import PdfReader
    n = len(PdfReader(str(SORTIE)).pages)
    print(f"Fiche : {n} page(s){'  ⚠ doit tenir sur 1 page' if n > 1 else ''} -> {SORTIE}")
