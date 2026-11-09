"""Analysis of the pictogram comprehension tests (see docs/pictogrammes/PROTOCOLE_TESTS.md).

    python pictogrammes/analyse_tests.py reponses.csv                     # default key: pictogrammes/test/cle_livret.csv
    python pictogrammes/analyse_tests.py reponses.csv --seuil-accepte 0.85

Judges' codes: C = correct, P = partly correct, F = wrong, N = "I don't know" / no answer.
Output: a table per item (rate of correct answers, 95 % confidence interval, decision), the agreement
between the two judges (Cohen's kappa), and the answers on which the judges disagree.
Disagreement: the judges meet and write the chosen code in the code_consensus column; the answer is then
counted with this code (kappa is still computed on the independent codes). Without consensus, it is not counted.
The decision thresholds are a TEAM CHOICE (configurable), not those of a standard. With fewer than 20 answers
for an item, the decision is marked "provisional" (wide confidence interval).
"""
import sys as _sys
for _flux in (_sys.stdout, _sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

CODES = {"C", "P", "F", "N"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - marge), min(1.0, centre + marge)


def kappa(paires: list[tuple[str, str]]) -> float | None:
    if not paires:
        return None
    n = len(paires)
    po = sum(a == b for a, b in paires) / n
    c1, c2 = Counter(a for a, _ in paires), Counter(b for _, b in paires)
    pe = sum(c1[c] * c2[c] for c in CODES) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def analyser(reponses: list[dict], cle: dict, seuil_accepte=0.8, seuil_revoir=0.5, n_minimum=10, n_ferme=20) -> dict:
    par_item, paires, desaccords, erreurs = defaultdict(list), [], [], []
    for i, r in enumerate(reponses, 2):
        j1, j2 = (r.get("code_juge1") or "").strip().upper(), (r.get("code_juge2") or "").strip().upper()
        if r.get("item") not in cle:
            erreurs.append(f"ligne {i} : item inconnu « {r.get('item')} »")
            continue
        if j1 not in CODES or (j2 and j2 not in CODES):
            erreurs.append(f"ligne {i} : code invalide ({j1!r}, {j2!r}) ; codes permis : C, P, F, N")
            continue
        if j2:
            paires.append((j1, j2))
            if j1 != j2:
                consensus = (r.get("code_consensus") or "").strip().upper()
                if consensus and consensus not in CODES:
                    erreurs.append(f"ligne {i} : code_consensus invalide ({consensus!r})")
                desaccords.append({"ligne": i, "participant": r.get("participant"), "item": r["item"], "juge1": j1, "juge2": j2,
                                   "consensus": consensus if consensus in CODES else "", "reponse": r.get("reponse_transcrite", "")})
                if consensus not in CODES:
                    continue                               # to settle: not counted until there is a consensus
                j1 = consensus
        par_item[r["item"]].append(j1)
    items = []
    for item, info in cle.items():
        codes = par_item.get(item, [])
        n, c = len(codes), codes.count("C")
        bas, haut = wilson(c, n)
        taux = c / n if n else 0.0
        decision = ("pas assez de réponses" if n < n_minimum else "accepté" if taux >= seuil_accepte
                    else "à revoir" if taux >= seuil_revoir else "à remplacer")
        if n_minimum <= n < n_ferme:
            decision += " (provisoire)"
        items.append({"item": item, "pictogramme": info["pictogramme"], "sens_attendu": info["sens_attendu"], "n": n,
                      "correct": round(taux, 3), "correct_ou_partiel": round((c + codes.count("P")) / n, 3) if n else 0.0,
                      "ne_sait_pas": round(codes.count("N") / n, 3) if n else 0.0,
                      "ic95": [round(bas, 3), round(haut, 3)], "decision": decision})
    return {"seuils": {"accepte": seuil_accepte, "a_revoir": seuil_revoir, "n_minimum": n_minimum, "n_ferme": n_ferme}, "kappa_juges": None if not paires else round(kappa(paires), 3),
            "participants": len({r.get("participant") for r in reponses}), "items": items, "desaccords": desaccords, "erreurs": erreurs}


def rapport_md(res: dict) -> str:
    l = [f"# Résultats des tests de compréhension\n",
         f"Participants : {res['participants']} · accord entre juges (kappa) : {res['kappa_juges']} · "
         f"seuils de l'équipe : accepté ≥ {res['seuils']['accepte']:.0%}, à revoir ≥ {res['seuils']['a_revoir']:.0%} ; "
         f"décision « provisoire » sous {res['seuils']['n_ferme']} réponses, aucune sous {res['seuils']['n_minimum']}.\n",
         "| Item | Pictogramme | Sens attendu | n | Correct | IC 95 % | Correct ou partiel | Ne sait pas | Décision |",
         "|---|---|---|---|---|---|---|---|---|"]
    for x in sorted(res["items"], key=lambda x: x["correct"]):
        l.append(f"| {x['item']} | {x['pictogramme']} | {x['sens_attendu']} | {x['n']} | {x['correct']:.0%} | "
                 f"{x['ic95'][0]:.0%}–{x['ic95'][1]:.0%} | {x['correct_ou_partiel']:.0%} | {x['ne_sait_pas']:.0%} | {x['decision']} |")
    if res["desaccords"]:
        l.append("\n## Désaccords entre juges (comptés seulement avec un code_consensus)\n")
        l += [f"- ligne {d['ligne']} · {d['participant']} · {d['item']} : {d['juge1']} / {d['juge2']} → "
              f"{d['consensus'] or 'À TRANCHER (non compté)'} — {d['reponse']}" for d in res["desaccords"]]
    if res["erreurs"]:
        l.append("\n## Lignes ignorées\n")
        l += [f"- {e}" for e in res["erreurs"]]
    return "\n".join(l) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("reponses")
    p.add_argument("--cle", default=str(Path(__file__).parent / "test" / "cle_livret.csv"))
    p.add_argument("--seuil-accepte", type=float, default=0.8)
    p.add_argument("--seuil-revoir", type=float, default=0.5)
    p.add_argument("--sortie", default=None, help="dossier de sortie (défaut : à côté du fichier de réponses)")
    a = p.parse_args(argv)
    with open(a.cle, encoding="utf-8") as f:
        cle = {r["item"]: r for r in csv.DictReader(f)}
    with open(a.reponses, encoding="utf-8-sig") as f:
        reponses = list(csv.DictReader(f))
    res = analyser(reponses, cle, a.seuil_accepte, a.seuil_revoir)
    sortie = Path(a.sortie) if a.sortie else Path(a.reponses).parent
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "resultats_tests.md").write_text(rapport_md(res), encoding="utf-8")
    (sortie / "resultats_tests.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(rapport_md(res))
    return 0


if __name__ == "__main__":
    _sys.exit(main())
