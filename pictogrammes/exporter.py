"""Exporte la bibliothèque de pictogrammes : fichiers SVG, manifeste et planche PDF.

    python pictogrammes/exporter.py            # -> pictogrammes/svg/*.svg, pictogrammes/manifeste.json
    python pictogrammes/exporter.py --pdf      # + docs/pictogrammes/Planche_pictogrammes.pdf (nécessite playwright + chromium)

Les dessins sont dans medimcom/bibliotheque.py : c'est là qu'on les corrige après les tests.
"""
import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from medimcom.bibliotheque import CADRES, CATALOGUE, libelle, svg  # noqa: E402

CATEGORIES = {"reponse": "Réponses", "personne": "Personnes", "corps": "Corps", "symptome": "Symptômes",
              "soin": "Soins", "temps": "Temps", "nombre": "Nombres"}


def exporter(dossier: Path) -> dict:
    (dossier / "svg").mkdir(parents=True, exist_ok=True)
    entrees = []
    for ident, (cat, fr, en, ar, _) in CATALOGUE.items():
        (dossier / "svg" / f"{ident}.svg").write_text(svg(ident), encoding="utf-8")
        entrees.append({"id": ident, "categorie": cat, "fichier": f"svg/{ident}.svg",
                        "libelles": {"fr": fr, "en": en, "ar": ar}, "statut": "a_tester"})
    manifeste = {"nom": "Bibliothèque de pictogrammes MEDIMCOM IA (équipe ShifaMiko)", "version": "1.0",
                 "licence": "Icônes de démonstration générées par code pour le prototype ; les pictogrammes définitifs viennent de bases existantes, sous leurs licences.",
                 "statut": "À tester avec des personnes sourdes (docs/pictogrammes/PROTOCOLE_TESTS.md) ; libellés arabes à faire relire.",
                 "parametres": ["CHIFFRE:<n>", "DOSE:<valeur>", "MEDICAMENT:<nom>"], "pictogrammes": entrees}
    (dossier / "manifeste.json").write_text(json.dumps(manifeste, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifeste


def planche_html() -> str:
    blocs = []
    for cat, titre in CATEGORIES.items():
        ids = [i for i, v in CATALOGUE.items() if v[0] == cat]
        if cat == "nombre":
            ids += ["CHIFFRE:3"]
        if cat == "soin":
            ids += ["DOSE:500mg", "MEDICAMENT:paracetamol"]
        cases = "".join(f'<div class="c">{svg(i)}<b>{i}</b><span>{libelle(i, "fr")} · {libelle(i, "en")}</span>'
                        f'<span dir="rtl">{libelle(i, "ar")}</span></div>' for i in ids)
        blocs.append(f'<h2 style="border-color:{CADRES[cat]}">{titre}</h2><div class="g">{cases}</div>')
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Pictogrammes MEDIMCOM IA</title><style>
@page {{ size: A4 landscape; margin: 10mm; }}
body {{ font-family: Inter, Arial, sans-serif; color: #1E2B31; margin: 0; }}
h1 {{ font-size: 18pt; margin: 0 0 1mm; }} .sous {{ font-size: 9pt; color: #56656D; margin-bottom: 3mm; }}
h2 {{ font-size: 11pt; margin: 3mm 0 1.5mm; border-left: 5px solid; padding-left: 2mm; break-after: avoid; }}
.g {{ display: grid; grid-template-columns: repeat(10, 1fr); gap: 2mm; }}
.c {{ text-align: center; font-size: 7pt; break-inside: avoid; }} .c svg {{ width: 24mm; height: 24mm; display: block; margin: 0 auto; }}
.c b {{ display: block; font-size: 7pt; }} .c span {{ display: block; color: #56656D; }}
</style></head><body>
<h1>Bibliothèque de pictogrammes MEDIMCOM IA — version 1.0</h1>
<div class="sous">Icônes de démonstration du prototype (les pictogrammes définitifs viennent de bases existantes). Statut : à tester avec des personnes sourdes (protocole : docs/pictogrammes/PROTOCOLE_TESTS.md). Libellés arabes à faire relire par un locuteur natif. Couleur du cadre = catégorie.</div>
{''.join(blocs)}</body></html>"""


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", action="store_true")
    a = p.parse_args()
    m = exporter(Path(__file__).parent)
    print(f"{len(m['pictogrammes'])} pictogrammes exportés dans {Path(__file__).parent / 'svg'}")
    if a.pdf:
        from playwright.sync_api import sync_playwright
        sortie = RACINE / "docs" / "pictogrammes" / "Planche_pictogrammes.pdf"
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page()
            page.set_content(planche_html(), wait_until="load")
            page.pdf(path=str(sortie), landscape=True, format="A4", print_background=True)
            b.close()
        print(f"Planche : {sortie}")
