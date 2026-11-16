"""Builds the pictogram base from ARASAAC (Internet access required; licence CC BY-NC-SA).

    python pictogrammes/bases/telecharger_arasaac.py                 # the whole medical vocabulary
    python pictogrammes/bases/telecharger_arasaac.py --ids GORGE DOS # only some identifiers
    python pictogrammes/bases/telecharger_arasaac.py --hors-ligne    # rebuild the manifest and the sheet without network

For each identifier of vocabulaire_medical.json:
1. searches ARASAAC pictograms with the French words, then English (6 candidates at most);
2. keeps the first one, unless the team chose another in choix_arasaac.json ({"GORGE": 12345});
3. downloads the chosen image into images/arasaac/<IDENTIFIER>.png;
4. writes candidats_arasaac.json, manifeste_externe.json (base, author, licence, link) and planche_candidats.html.

Open planche_candidats.html to compare the candidates, note the right numbers in choix_arasaac.json, run again.
The final choice of pictograms belongs to the team, then to tests with deaf people.
"""
import argparse
import html
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ICI = Path(__file__).resolve().parent
API = "https://api.arasaac.org/v1/pictograms"
IMAGE = "https://static.arasaac.org/pictograms/{n}/{n}_300.png"
PAGE = "https://arasaac.org/pictograms/fr/{n}"


def _get(url: str, binaire: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": "MEDIMCOM-IA (hackathon UIT, usage non commercial)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = r.read()
    return d if binaire else json.loads(d.decode("utf-8"))


def chercher(mot: str, langue: str) -> list[dict]:
    """ARASAAC candidates for a word: first the "best search", then the broad search."""
    vus, sortie = set(), []
    for chemin in ("bestsearch", "search"):
        try:
            res = _get(f"{API}/{langue}/{chemin}/{urllib.parse.quote(mot)}")
        except Exception:
            continue
        for x in res if isinstance(res, list) else []:
            n = x.get("_id", x.get("id"))
            if n is None or n in vus:
                continue
            vus.add(n)
            mots = [k.get("keyword", "") for k in x.get("keywords", []) if isinstance(k, dict)]
            sortie.append({"arasaac_id": n, "mots": mots[:4], "recherche": f"{langue}:{mot}"})
    return sortie


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--ids", nargs="*", help="identifiants à traiter (défaut : tout le vocabulaire)")
    p.add_argument("--hors-ligne", action="store_true", help="ne rien télécharger : refaire manifeste et planche")
    p.add_argument("--pause", type=float, default=0.3, help="pause entre deux requêtes (secondes)")
    a = p.parse_args(argv)
    base = json.loads((ICI / "bases.json").read_text(encoding="utf-8"))["bases"]["arasaac"]
    voc = {x["id"]: x for x in json.loads((ICI / "vocabulaire_medical.json").read_text(encoding="utf-8"))["vocabulaire"]}
    f_cand, f_choix, f_man = ICI / "candidats_arasaac.json", ICI / "choix_arasaac.json", ICI / "manifeste_externe.json"
    candidats = json.loads(f_cand.read_text(encoding="utf-8")) if f_cand.exists() else {}
    choix = json.loads(f_choix.read_text(encoding="utf-8")) if f_choix.exists() else {}
    manifeste = json.loads(f_man.read_text(encoding="utf-8")) if f_man.exists() else {"pictogrammes": {}}
    (ICI / "images" / "arasaac").mkdir(parents=True, exist_ok=True)

    ids = a.ids or list(voc)
    inconnus = [i for i in ids if i not in voc]
    if inconnus:
        raise SystemExit(f"Identifiants absents du vocabulaire : {', '.join(inconnus)}")
    sans = []
    for i in ids:
        if not a.hors_ligne:
            liste = []
            for langue in ("fr", "en"):
                for mot in voc[i]["recherche"][langue]:
                    liste += [c for c in chercher(mot, langue) if c["arasaac_id"] not in {x["arasaac_id"] for x in liste}]
                    time.sleep(a.pause)
                if len(liste) >= 6:
                    break
            candidats[i] = liste[:6]
        retenu = choix.get(i) or (candidats.get(i) or [{}])[0].get("arasaac_id")
        if not retenu:
            sans.append(i)
            continue
        fichier = Path("images") / "arasaac" / f"{i}.png"
        if not a.hors_ligne:
            try:
                (ICI / fichier).write_bytes(_get(IMAGE.format(n=retenu), binaire=True))
            except Exception as e:
                print(f"  ✖ {i} : image {retenu} non téléchargée ({e})")
                continue
        if (ICI / fichier).exists():
            manifeste["pictogrammes"][i] = {"base": "arasaac", "source_id": retenu, "fichier": fichier.as_posix(),
                                            "url": PAGE.format(n=retenu), "auteur": "Sergio Palao", "licence": base["licence"],
                                            "attribution": base["attribution"], "choisi_par": "équipe" if i in choix else "premier résultat"}
            print(f"  ✔ {i:<15} ARASAAC n° {retenu}" + ("  (choix de l'équipe)" if i in choix else ""))
    f_cand.write_text(json.dumps(candidats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    f_man.write_text(json.dumps(manifeste, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ecrire_planche(voc, candidats, manifeste)
    print(f"{len(manifeste['pictogrammes'])} pictogrammes dans le manifeste ; sans résultat : {', '.join(sans) or 'aucun'}")
    print(f"Planche des candidats : {ICI / 'planche_candidats.html'} ; choix de l'équipe : {f_choix}")
    return 0


def ecrire_planche(voc, candidats, manifeste):
    lignes = []
    for i, x in voc.items():
        retenu = manifeste["pictogrammes"].get(i, {}).get("source_id")
        cases = "".join(
            f'<figure class="{"ok" if c["arasaac_id"] == retenu else ""}"><img loading="lazy" src="{IMAGE.format(n=c["arasaac_id"])}" alt="">'
            f'<figcaption>n° {c["arasaac_id"]}<br>{html.escape(", ".join(c["mots"][:2]))}</figcaption></figure>'
            for c in candidats.get(i, []))
        lignes.append(f'<tr><th>{i}<br><small>{html.escape(x["fr"])} · {html.escape(x["en"])}</small></th><td>{cases or "—"}</td></tr>')
    (ICI / "planche_candidats.html").write_text(f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Candidats ARASAAC</title><style>body{{font:14px system-ui;margin:16px;background:#fff;color:#1E2B31}}
table{{border-collapse:collapse}}th{{text-align:left;padding:6px;width:150px;vertical-align:top}}td{{padding:6px}}
figure{{display:inline-block;margin:0 6px 6px 0;text-align:center;width:110px;border:2px solid #ddd;border-radius:8px;padding:4px}}
figure.ok{{border-color:#2E9B5F}}img{{width:96px;height:96px}}figcaption{{font-size:11px;color:#5A6A72}}tr{{border-top:1px solid #eee}}</style></head>
<body><h1>Candidats ARASAAC par pictogramme</h1><p>Cadre vert = image retenue. Pour en choisir une autre, l'écrire dans
<code>choix_arasaac.json</code> (ex. <code>{{"GORGE": 12345}}</code>) puis relancer le script.
Pictogrammes : Sergio Palao, ARASAAC (https://arasaac.org), CC BY-NC-SA, Gouvernement d'Aragon.</p>
<table>{"".join(lignes)}</table></body></html>""", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
