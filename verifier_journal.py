"""Vérifie qu'un journal n'a pas été modifié.

    python verifier_journal.py sortie/journal.json
    python verifier_journal.py sortie/journal.json --falsifier 10   # démo : modifie la ligne 10 puis vérifie
"""

import sys as _sys
for _flux in (_sys.stdout, _sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

import argparse

from medimcom.journal import Journal

p = argparse.ArgumentParser()
p.add_argument("chemin")
p.add_argument("--falsifier", type=int, help="numéro de ligne à modifier (démonstration)")
a = p.parse_args()

j = Journal.charger(a.chemin)
print(f"{len(j.lignes)} lignes · {j.verifier()}")
if a.falsifier:
    j.lignes[a.falsifier - 1]["contenu"] = "TEXTE MODIFIÉ APRÈS COUP"
    print(f"Après modification de la ligne {a.falsifier} : {j.verifier()}")
