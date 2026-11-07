"""Prépare le matériel du test de compréhension des pictogrammes (voir docs/pictogrammes/PROTOCOLE_TESTS.md).

    python pictogrammes/livret.py               # -> pictogrammes/test/cle_livret.csv et reponses_modele.csv
    python pictogrammes/livret.py --pdf         # + docs/pictogrammes/Livret_test_pictogrammes.pdf (playwright + chromium)

Le livret montre chaque pictogramme seul, sous un numéro d'item (jamais son nom), dans un ordre tiré au
hasard mais fixe (graine), avec la situation à signer par l'animateur. La clé (item -> pictogramme)
reste chez l'animateur.
"""
import argparse
import csv
import random
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import re  # noqa: E402

from medimcom.bibliotheque import CATALOGUE, svg as _svg  # noqa: E402


def svg(ident: str) -> str:
    """Pictogramme SANS son nom (ni titre, ni étiquette d'accessibilité) : le livret ne doit pas souffler la réponse."""
    return re.sub(r'<title>.*?</title>', "", re.sub(r' aria-label="[^"]*"', "", _svg(ident)))

CONTEXTES = {
    "reponse": "Vous êtes chez le médecin. Il vous montre cette image, ou vous la lui montrez.",
    "personne": "Vous êtes chez le médecin. Cette image parle d'une personne.",
    "corps": "Vous êtes chez le médecin. Cette image parle du corps.",
    "symptome": "Vous êtes chez le médecin. Cette image parle de ce que vous ressentez.",
    "soin": "Vous êtes chez le médecin ou à l'hôpital. Cette image parle des soins.",
    "temps": "Le médecin explique quand prendre un médicament.",
    "nombre": "Le médecin explique combien de médicaments prendre.",
}
# Phrases complètes (séquences) à tester aussi : sens attendu -> pictogrammes
SEQUENCES = [
    ("Êtes-vous enceinte ?", ["VOUS", "ENCEINTE", "QUESTION"]),
    ("Avez-vous mal au ventre ?", ["VOUS", "VENTRE", "DOULEUR", "QUESTION"]),
    ("Avez-vous de la fièvre ?", ["VOUS", "FIEVRE", "QUESTION"]),
    ("Avez-vous des allergies ?", ["VOUS", "ALLERGIE", "QUESTION"]),
    ("Prenez 1 comprimé le matin et le soir.", ["PRENDRE", "CHIFFRE:1", "COMPRIME", "MATIN", "SOIR"]),
    ("Ne prenez pas ce médicament.", ["PRENDRE", "NE_PAS", "MEDICAMENT"]),
    ("Pendant 3 jours.", ["CHIFFRE:3", "JOUR"]),
    ("Buvez beaucoup d'eau.", ["BOIRE", "PLUS", "EAU"]),
    ("Vous devez aller à l'hôpital.", ["VOUS", "HOPITAL"]),
    ("Êtes-vous d'accord ?", ["VOUS", "ACCORD", "QUESTION"]),
]


def plan(graine: int = 2026):
    ids = list(CATALOGUE)
    random.Random(graine).shuffle(ids)
    return [{"item": f"P{i + 1:02d}", "pictogramme": p, "categorie": CATALOGUE[p][0], "sens_attendu": CATALOGUE[p][1]}
            for i, p in enumerate(ids)] + [{"item": f"S{i + 1:02d}", "pictogramme": " ".join(seq), "categorie": "sequence",
                                            "sens_attendu": sens} for i, (sens, seq) in enumerate(SEQUENCES)]


def ecrire_csv(dossier: Path, items):
    dossier.mkdir(parents=True, exist_ok=True)
    with open(dossier / "cle_livret.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["item", "pictogramme", "categorie", "sens_attendu"])
        w.writeheader()
        w.writerows(items)
    with open(dossier / "reponses_modele.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["participant", "item", "reponse_transcrite", "code_juge1", "code_juge2", "code_consensus", "remarque"])
        w.writerow(["PART-001", "P01", "(ce que la personne a signé, transcrit par l'interprète)", "C", "C", "", ""])
        w.writerow(["PART-001", "P02", "(exemple de désaccord tranché ensemble)", "C", "P", "P", "juges réunis le …"])


def html_livret(items) -> str:
    def page_item(it):
        if it["categorie"] == "sequence":
            images = "".join(f'<div class="s">{svg(p)}</div>' for p in it["pictogramme"].split())
            contexte = "Le médecin vous envoie ce message."
        else:
            images = f'<div class="g">{svg(it["pictogramme"])}</div>'
            contexte = CONTEXTES[it["categorie"]]
        return (f'<section class="page"><div class="haut"><b>Item {it["item"]}</b><span>Participant : ________</span></div>'
                f'<div class="contexte">À signer par l\'animateur : « {contexte} Que veut dire cette image ? »</div>'
                f'<div class="centre">{images}</div></section>')
    consentement = "".join(f'<div class="cs">{svg(p)}</div>' for p in ("MOI", "COMPRENDRE", "QUESTION"))
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Livret de test</title><style>
@page {{ size: A4; margin: 12mm; }}
body {{ font-family: Inter, Arial, sans-serif; color: #1E2B31; margin: 0; }}
.page {{ break-after: page; height: 270mm; display: flex; flex-direction: column; }}
.haut {{ display: flex; justify-content: space-between; font-size: 12pt; }}
.contexte {{ font-size: 9.5pt; color: #56656D; margin-top: 3mm; }}
.centre {{ flex: 1; display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 6mm; }}
.g svg {{ width: 120mm; height: 120mm; }} .s svg {{ width: 42mm; height: 42mm; }} .cs svg {{ width: 34mm; height: 34mm; }}
h1 {{ font-size: 18pt; }} li {{ margin-bottom: 2mm; }} table {{ border-collapse: collapse; width: 100%; font-size: 9pt; }}
td, th {{ border: 1px solid #C9D2D6; padding: 1.5mm; text-align: left; }}
</style></head><body>
<section class="page"><h1>Livret de test des pictogrammes MEDIMCOM IA</h1>
<p>Pour l'animateur (protocole complet : docs/pictogrammes/PROTOCOLE_TESTS.md).</p>
<ol>
<li>Recueillir le consentement en langue des signes, avec l'interprète (page suivante).</li>
<li>Pour chaque item : signer la phrase de contexte, montrer la page, demander « que veut dire cette image ? ».</li>
<li>Ne jamais dire le sens ni corriger. Ne pas montrer la clé. « Je ne sais pas » est une réponse acceptée.</li>
<li>L'interprète transcrit la réponse mot pour mot dans le fichier de réponses.</li>
<li>La personne peut arrêter à tout moment, sans justification.</li>
</ol>
<p>{len([i for i in items if i['categorie'] != 'sequence'])} pictogrammes seuls (P01…) puis {len(SEQUENCES)} messages (S01…). Durée visée : 45 minutes, avec des pauses.</p></section>
<section class="page"><h1>Consentement (à signer, puis à montrer)</h1>
<div class="centre">{consentement}</div>
<p>« Nous testons des images pour aider les personnes sourdes chez le médecin. Ce n'est pas un examen de vous : c'est un test des images.
Vous pouvez arrêter quand vous voulez. Votre nom n'est pas écrit. Êtes-vous d'accord ? »</p>
<div class="centre"><div class="cs">{svg("OUI")}</div><div class="cs">{svg("NON")}</div><div class="cs">{svg("STOP")}</div></div>
<p>Accord : OUI ☐ NON ☐ — Code participant : ________ — Date : ________ — Animateur : ________ — Interprète : ________</p></section>
{''.join(page_item(it) for it in items)}
</body></html>"""


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", action="store_true")
    p.add_argument("--graine", type=int, default=2026)
    a = p.parse_args()
    items = plan(a.graine)
    dossier = Path(__file__).parent / "test"
    ecrire_csv(dossier, items)
    print(f"{len(items)} items · clé : {dossier / 'cle_livret.csv'} · modèle de réponses : {dossier / 'reponses_modele.csv'}")
    if a.pdf:
        from playwright.sync_api import sync_playwright
        sortie = RACINE / "docs" / "pictogrammes" / "Livret_test_pictogrammes.pdf"
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page()
            page.set_content(html_livret(items), wait_until="load")
            page.pdf(path=str(sortie), format="A4", print_background=True)
            b.close()
        print(f"Livret : {sortie}")
