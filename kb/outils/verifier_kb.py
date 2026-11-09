"""Contrôle la cohérence de la base : manifeste, fiches, lacunes, règles et questions de test.

    python kb/outils/verifier_kb.py
"""
import json
import sys

from _chemin import KB
from medimcom.base import BaseConnaissances
from medimcom.regles import MoteurRegles


def controler():
    base = BaseConnaissances(KB)
    p = base.problemes()
    from medimcom.formel import bonne_formation
    for fichier in ("regles_uae.json", "regles_cm.json"):
        moteur = MoteurRegles(KB / fichier, base)
        p += [f"{fichier} : référence inconnue {x}" for x in sorted(moteur.references_inconnues())]
        # typage des règles (signature), blocage seulement sur une loi lue du bon pays (rapide ; le reste : verifier_formel.py)
        p += [f"{fichier} : {r['id']} {c}" for r in bonne_formation(moteur) for c in r["contre_exemples"]]
    spec = json.loads((KB / "specification_formelle.json").read_text(encoding="utf-8"))
    p += [f"spécification {e['id']} : fiche inconnue {f}" for e in spec["exigences"] for f in e["fiches"] if f not in base.fiches]
    for l in (KB / "questions_test.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            q = json.loads(l)
            p += [f"question {q['id']} : fiche attendue inconnue {f}" for f in q["attendu"] if f not in base.fiches]
    utilisees = {f["source"] for f in base.fiches.values()}
    p += [f"source {s} sans aucune fiche" for s in base.sources if s not in utilisees]
    return base, p


if __name__ == "__main__":
    base, p = controler()
    niveaux = {}
    for s in base.sources.values():
        niveaux[s["verification"]] = niveaux.get(s["verification"], 0) + 1
    print(f"{len(base.sources)} sources ({niveaux}) · {len(base.fiches)} fiches · {len(base.lacunes)} lacunes")
    print("\n".join(p) if p else "Base cohérente.")
    sys.exit(1 if p else 0)
