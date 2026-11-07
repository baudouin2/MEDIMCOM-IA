"""Mesure la qualité de la recherche dans la base (rappel@k et MRR) sur kb/questions_test.jsonl.

    python kb/outils/evaluer_recherche.py            # résumé (BM25, recherche par mots)
    python kb/outils/evaluer_recherche.py --details  # chaque question
    python kb/outils/evaluer_recherche.py --comparer --encodeur ollama:bge-m3   # BM25 vs vecteurs vs hybride
"""
import argparse
import json

from _chemin import KB
from medimcom.base import BaseConnaissances


def evaluer(base, questions, ks=(1, 3, 5), methode=None):
    res = {"n": len(questions), "rappel": {k: 0 for k in ks}, "mrr": 0.0, "echecs": [], "par_langue": {}}
    for q in questions:
        trouves = [r["fiche"] for r in base.chercher(q["question"], k=max(ks), methode=methode)]
        rang = next((i + 1 for i, f in enumerate(trouves) if f in q["attendu"]), None)
        lg = res["par_langue"].setdefault(q["langue"], {"n": 0, "rappel@3": 0})
        lg["n"] += 1
        for k in ks:
            if rang and rang <= k:
                res["rappel"][k] += 1
        if rang and rang <= 3:
            lg["rappel@3"] += 1
        res["mrr"] += 1 / rang if rang else 0
        if not rang or rang > 3:
            res["echecs"].append({"id": q["id"], "question": q["question"], "attendu": q["attendu"], "obtenu": trouves[:3], "rang": rang})
    n = res["n"]
    res["rappel"] = {f"rappel@{k}": round(v / n, 3) for k, v in res["rappel"].items()}
    res["mrr"] = round(res["mrr"] / n, 3)
    for lg in res["par_langue"].values():
        lg["rappel@3"] = round(lg["rappel@3"] / lg["n"], 3)
    return res


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--details", action="store_true")
    p.add_argument("--comparer", action="store_true", help="comparer BM25, vecteurs et hybride")
    p.add_argument("--encodeur", default="ollama:bge-m3", help="index à utiliser avec --comparer (ollama:<modèle> ou hachage)")
    a = p.parse_args()
    base = BaseConnaissances(KB)
    qs = [json.loads(l) for l in (KB / "questions_test.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.comparer:
        from medimcom.vecteurs import IndexVectoriel, encodeur
        enc = encodeur(a.encodeur)
        chemin = KB / "index" / f"vecteurs_{enc.nom}.jsonl"
        if not chemin.exists():
            raise SystemExit(f"Index absent : {chemin}. Le construire : python kb/outils/construire_vecteurs.py --encodeur {a.encodeur}")
        base.brancher_vecteurs(IndexVectoriel.charger(chemin), enc)
        print(f"{len(qs)} questions · encodeur {enc.nom}")
        print("| Méthode | rappel@1 | rappel@3 | rappel@5 | MRR |\n|---|---|---|---|---|")
        for m in ("bm25", "vecteurs", "hybride"):
            r = evaluer(base, qs, methode=m)
            print(f"| {m} | {r['rappel']['rappel@1']} | {r['rappel']['rappel@3']} | {r['rappel']['rappel@5']} | {r['mrr']} |")
        raise SystemExit(0)
    r = evaluer(base, qs)
    print(f"{r['n']} questions · " + " · ".join(f"{k} = {v}" for k, v in r["rappel"].items()) + f" · MRR = {r['mrr']}")
    for lg, v in r["par_langue"].items():
        print(f"  {lg} : {v['n']} questions, rappel@3 = {v['rappel@3']}")
    if a.details or r["echecs"]:
        print("Hors des 3 premiers :")
        for e in r["echecs"]:
            print(f"  {e['id']} rang={e['rang']} attendu={e['attendu']} obtenu={e['obtenu']} — {e['question']}")
