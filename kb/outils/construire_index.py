"""Exporte la base en morceaux prêts pour une base vectorielle (Chroma, FAISS, base distribuée de l'UIT).

    python kb/outils/construire_index.py   ->  kb/index/chunks.jsonl

Chaque ligne : {"id", "text", "metadata"}. Le texte combine titre, disposition et source,
pour que chaque morceau soit compréhensible seul. Les métadonnées gardent la
traçabilité (source, article, lien officiel, niveau de vérification).
"""
import json

from _chemin import KB
from medimcom.base import BaseConnaissances


def morceaux(base):
    for f in base.fiches.values():
        s = base.sources[f["source"]]
        texte = (f"{f['title']}. {f['text']}"
                 + (f' Quote: "{f["quote"]}".' if f.get("quote") else "")
                 + f" Source: {s['title']}, {f['ref']}.")
        yield {"id": f["id"], "text": texte, "metadata": {
            "source_id": s["id"], "source_title": s["short_title"], "reference": f["ref"], "url": s["url"],
            "jurisdiction": s["jurisdiction"], "verification": s["verification"], "basis": f["basis"],
            "role": s["role"], "themes": ", ".join(f["themes"]), "modes": ", ".join(f["modes"])}}
    for l in base.lacunes.values():
        texte = (f"Policy gap {l['id']} ({l['domain']}): {l['title']}. Situation: {l['situation']} "
                 f"Missing: {l['missing']} MEDIMCOM response: {l['medimcom_response']}")
        yield {"id": l["id"], "text": texte, "metadata": {"source_id": "lacunes", "reference": l["id"], "url": "",
               "jurisdiction": "AE + global examples", "verification": "analysis", "basis": "LACUNE",
               "role": "gap", "themes": l["domain"], "modes": "consultation, crise"}}


if __name__ == "__main__":
    sortie = KB / "index" / "chunks.jsonl"
    sortie.parent.mkdir(exist_ok=True)
    lignes = list(morceaux(BaseConnaissances(KB)))
    sortie.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lignes), encoding="utf-8")
    print(f"{len(lignes)} morceaux écrits dans {sortie}")
