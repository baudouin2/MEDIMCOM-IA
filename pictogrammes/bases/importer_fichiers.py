"""Ajoute au manifeste les pictogrammes déposés à la main (Tawasol, Mulberry, Sclera…).

    1. Télécharger l'image depuis le site de la base (respecter sa licence).
    2. La nommer avec l'identifiant MEDIMCOM et la déposer dans images/<base>/ :
         pictogrammes/bases/images/tawasol/GORGE.png
         pictogrammes/bases/images/mulberry/DOS.svg
    3. python pictogrammes/bases/importer_fichiers.py
       (option --url GORGE=https://… pour garder le lien de la page d'origine)

Contrôles : identifiant connu du vocabulaire, base déclarée dans bases.json et autorisée, format PNG, JPEG ou SVG
sûr (formes et texte seulement). SantéBD est refusée tant que l'accord écrit n'est pas noté dans bases.json.
Un fichier importé à la main remplace l'image ARASAAC du même identifiant.
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
