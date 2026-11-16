"""Adds to the manifest the pictograms dropped by hand (Tawasol, Mulberry, Sclera…).

    1. Download the image from the database's website (respect its licence).
    2. Name it with the MEDIMCOM identifier and drop it in images/<base>/:
         pictogrammes/bases/images/tawasol/GORGE.png
         pictogrammes/bases/images/mulberry/DOS.svg
    3. python pictogrammes/bases/importer_fichiers.py
       (option --url GORGE=https://… to keep the link of the original page)

Checks: identifier known in the vocabulary, base declared in bases.json and allowed, safe PNG, JPEG or SVG
format (shapes and text only). SantéBD is refused as long as the written agreement is not noted in bases.json.
A file imported by hand replaces the ARASAAC image of the same identifier.
"""
import argparse
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent.parent))
from medimcom.bibliotheque import _svg_sur  # noqa: E402

SIGNATURES = {".png": b"\x89PNG", ".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8"}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--url", nargs="*", default=[], help="IDENTIFIANT=lien de la page d'origine")
    a = p.parse_args(argv)
    bases = json.loads((ICI / "bases.json").read_text(encoding="utf-8"))["bases"]
    voc = {x["id"] for x in json.loads((ICI / "vocabulaire_medical.json").read_text(encoding="utf-8"))["vocabulaire"]}
    f_man = ICI / "manifeste_externe.json"
    manifeste = json.loads(f_man.read_text(encoding="utf-8")) if f_man.exists() else {"pictogrammes": {}}
    liens = dict(x.split("=", 1) for x in a.url)
    ok, refus = 0, []
    for dossier in sorted((ICI / "images").glob("*")):
        nom = dossier.name
        if nom == "arasaac" or not dossier.is_dir():
            continue
        b = bases.get(nom)
        for f in sorted(dossier.iterdir()):
            ident, ext = f.stem.upper(), f.suffix.lower()
            if b is None:
                refus.append(f"{f.name} : base « {nom} » inconnue (la déclarer dans bases.json)")
            elif b.get("autorisation_ecrite_requise") and not b.get("autorisation_ecrite_obtenue"):
                refus.append(f"{f.name} : {b['nom']} exige un accord écrit de l'éditeur (noter « autorisation_ecrite_obtenue »)")
            elif ident not in voc:
                refus.append(f"{f.name} : identifiant {ident} absent de vocabulaire_medical.json")
            elif ext == ".svg" and not _svg_sur(f.read_text(encoding="utf-8", errors="replace")):
                refus.append(f"{f.name} : SVG refusé (script, lien externe ou élément non autorisé)")
            elif ext in SIGNATURES and not f.read_bytes().startswith(SIGNATURES[ext]):
                refus.append(f"{f.name} : ce n'est pas un vrai fichier {ext}")
            elif ext not in SIGNATURES and ext != ".svg":
                refus.append(f"{f.name} : format non accepté (PNG, JPEG ou SVG)")
            else:
                manifeste["pictogrammes"][ident] = {"base": nom, "source_id": f.name, "fichier": f.relative_to(ICI).as_posix(),
                                                    "url": liens.get(ident, b["url"]), "auteur": b["nom"], "licence": b["licence"],
                                                    "attribution": b["attribution"], "choisi_par": "équipe (import manuel)"}
                ok += 1
    f_man.write_text(json.dumps(manifeste, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{ok} image(s) importée(s) ; manifeste : {len(manifeste['pictogrammes'])} pictogrammes")
    for r in refus:
        print("  ✖ " + r)
    return 1 if refus else 0


if __name__ == "__main__":
    sys.exit(main())
