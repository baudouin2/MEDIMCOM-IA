"""Mesure ce que la base_v2 apporte aux agents, sur la partie « test » des jeux de 05_jeux_entrainement (jamais vue
pour régler le système). Aucune IA, aucun réseau : chiffres reproductibles, à citer dans le rapport.

    python outils/evaluer_base_v2.py                       # base trouvée automatiquement (base_v2/ ou ~/MEDIMCOM_base_v2)
    python outils/evaluer_base_v2.py --base D:/MEDIMCOM_base_v2
    python outils/evaluer_base_v2.py --recherche fastembed:e5   # + comparaison mots-clés / sens / hybride

1. Traduction texte -> pictogrammes (agent 1) : phrases_pictogrammes.jsonl ; précision, rappel, F1 sur les notions,
   rappel « atteignable » (notions dont une image existe), négations conservées.
2. Recherche dans les textes officiels (juriste) : juridique_recherche.jsonl ; le bon article est-il dans les k premiers ?
3. Recherche dans les fiches de l'OMS (assistant) : references_qr.jsonl ; la bonne section est-elle dans les k premiers ?
Résultats : <base>/06_evaluation/resultats.json et RESULTATS.md
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from medimcom.base_v2 import Corpus, LexiqueBaseV2, charger_pictogrammes, trouver_base  # noqa: E402

EQUIVALENTS = {"AVOIR_MAL": "DOULEUR"}


def lire(f: Path, split: str | None = "test") -> list[dict]:
    """split=None : tous les exemples. La recherche n'est jamais entraînée sur ces jeux (BM25 sans apprentissage) :
    l'évaluer sur toutes les paires est donc légitime et donne un chiffre plus stable quand le jeu est petit."""
    if not f.exists():
        return []
    lignes = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [x for x in lignes if split is None or x.get("split") == split]


def _ensemble(ids) -> set:
    sortie = set()
    for p in ids:
        for x in p.split("+"):
            if not x.startswith(("CHIFFRE:", "DOSE:", "MEDICAMENT:")):
                sortie.add(EQUIVALENTS.get(x, x))
    return sortie


def eval_traduction(base: Path, lexique: LexiqueBaseV2) -> dict:
    ex = lire(base / "05_jeux_entrainement" / "phrases_pictogrammes.jsonl")
    vp = fp = fn = fn_atteignable = exacts = 0
    neg_total = neg_ok = 0
    for e in ex:
        or_ = _ensemble(e["notions"])
        pred = _ensemble(lexique.traduire(e["fr"])["pictogrammes"])
        vp += len(or_ & pred); fp += len(pred - or_); fn += len(or_ - pred)
        fn_atteignable += len({x for x in or_ - pred if lexique._disponible(x)})
        exacts += or_ == pred
        if "NE_PAS" in or_:
            neg_total += 1
            neg_ok += "NE_PAS" in pred
    p = vp / (vp + fp) if vp + fp else 0
    r = vp / (vp + fn) if vp + fn else 0
    ra = vp / (vp + fn_atteignable) if vp + fn_atteignable else 0
    return {"exemples": len(ex), "precision": round(p, 3), "rappel": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0,
            "rappel_atteignable": round(ra, 3), "phrases_exactes": round(exacts / len(ex), 3) if ex else 0,
            "negations_conservees": f"{neg_ok}/{neg_total}"}


def _rang(resultats, ok) -> int | None:
    for i, r in enumerate(resultats, 1):
        if ok(r):
            return i
    return None


def eval_recherche(exemples, corpus: Corpus, requete, juste, type_, methode: str | None = None) -> dict:
    rangs = [_rang(corpus.chercher(requete(e), k=10, type_=type_, methode=methode), lambda r, e=e: juste(e, r)) for e in exemples]
    n = len(rangs)
    rappel = lambda k: round(sum(1 for r in rangs if r and r <= k) / n, 3) if n else 0  # noqa: E731
    return {"exemples": n, "rappel@1": rappel(1), "rappel@3": rappel(3), "rappel@5": rappel(5), "rappel@10": rappel(10),
            "MRR": round(sum(1 / r for r in rangs if r) / n, 3) if n else 0}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base", default=None)
    p.add_argument("--recherche", default=None, help="encodeur des vecteurs (ex. fastembed:e5) : compare BM25, sens et hybride")
    a = p.parse_args(argv)
    base = trouver_base(a.base)
    if not base:
        print("Base introuvable : la placer dans MEDIMCOM_IA/base_v2 ou préciser --base.")
        return 1
    print(f"Base : {base}")
    lexique = LexiqueBaseV2(base, charger_pictogrammes(base))
    corpus = Corpus(base)
    d = base / "05_jeux_entrainement"
    r = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "base": str(base),
         "pictogrammes_disponibles": sum(1 for n in lexique.notions.values() if n.get("image")), "morceaux_indexes": len(corpus),
         "traduction": eval_traduction(base, lexique),
         "recherche_juridique": eval_recherche(lire(d / "juridique_recherche.jsonl", None), corpus, lambda e: e["requete"],
                                               lambda e, r: r["extrait"].split("~")[0] == e["positif_id"], "texte_officiel"),
         "recherche_oms": eval_recherche(lire(d / "references_qr.jsonl", None), corpus, lambda e: e["question"],
                                         lambda e, r: r["extrait"] == e["id"][3:], "reference_medicale")}
    sortie = base / "06_evaluation"
    sortie.mkdir(exist_ok=True)
    (sortie / "resultats.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    t, j, o = r["traduction"], r["recherche_juridique"], r["recherche_oms"]
    par_langue = {}
    for lg in ("fr", "en", "ar"):
        ex = [e for e in lire(d / "references_qr.jsonl", None) if e.get("langue") == lg]
        if ex:
            par_langue[lg] = eval_recherche(ex, corpus, lambda e: e["question"], lambda e, r: r["extrait"] == e["id"][3:], "reference_medicale")
    r["recherche_oms_par_langue"] = par_langue
    comparaison = ""
    if a.recherche:
        from medimcom.vecteurs import encodeur
        enc = encodeur(a.recherche)
        bilan = corpus.brancher_vecteurs(base / "07_vecteurs", enc)
        if not bilan:
            print(f"Aucun vecteur {enc.nom} dans {base / '07_vecteurs'} : lancer outils/vectoriser_base.py --encodeur {a.recherche}")
        else:
            r["comparaison_methodes"] = {}
            lignes = []
            for m in ("bm25", "vecteurs", "hybride"):
                jj = eval_recherche(lire(d / "juridique_recherche.jsonl", None), corpus, lambda e: e["requete"],
                                    lambda e, x: x["extrait"].split("~")[0] == e["positif_id"], "texte_officiel", m)
                oo = eval_recherche(lire(d / "references_qr.jsonl", None), corpus, lambda e: e["question"],
                                    lambda e, x: x["extrait"] == e["id"][3:], "reference_medicale", m)
                r["comparaison_methodes"][m] = {"juridique": jj, "oms": oo}
                nom = {"bm25": "Mots-clés (BM25)", "vecteurs": f"Sens seul ({enc.nom})", "hybride": "Hybride (RRF)"}[m]
                lignes.append(f"| {nom} | {jj['rappel@1']} · {jj['rappel@5']} · {jj['MRR']} | {oo['rappel@1']} · {oo['rappel@5']} · {oo['MRR']} |")
            comparaison = ("\n## Mots-clés, sens ou hybride ?\n\n| Méthode | Juridique : 1er · 5 premiers · MRR | OMS : 1er · 5 premiers · MRR |\n"
                           "|---|---|---|\n" + "\n".join(lignes) + "\n")
    (sortie / "resultats.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    detail_langues = " ; ".join(f"{lg} : 5 premiers {v['rappel@5']} ({v['exemples']})" for lg, v in par_langue.items())
    md = f"""# Évaluation de la base_v2 — {r['date'][:10]}

Traduction : partie « test » des phrases (jamais utilisée pour régler le système). Recherche : toutes les paires (la recherche
BM25 n'apprend rien de ces jeux). Sans IA, sans réseau : reproductible.

| Mesure | Résultat |
|---|---|
| Pictogrammes utilisables | {r['pictogrammes_disponibles']} notions avec image |
| Morceaux indexés pour la recherche | {r['morceaux_indexes']} |
| **Traduction texte → pictogrammes** ({t['exemples']} phrases) | précision {t['precision']} · rappel {t['rappel']} · F1 {t['f1']} · rappel sur les notions illustrées {t['rappel_atteignable']} · phrases exactes {t['phrases_exactes']} · négations conservées {t['negations_conservees']} |
| **Recherche juridique** ({j['exemples']} requêtes) | bon article au 1er rang {j['rappel@1']} · dans les 3 premiers {j['rappel@3']} · dans les 5 premiers {j['rappel@5']} · MRR {j['MRR']} |
| **Recherche dans les fiches OMS** ({o['exemples']} questions) | 1er rang {o['rappel@1']} · 3 premiers {o['rappel@3']} · 5 premiers {o['rappel@5']} · MRR {o['MRR']} · par langue : {detail_langues} |

Limites : les phrases de test sont générées par gabarit (formulations simples) ; les requêtes juridiques viennent des
dispositions du juriste rapprochées des articles par leur numéro ; un 0 signifie souvent que le jeu de test est vide
(document non téléchargé ou pictogrammes manquants) : lire les effectifs.
""" + comparaison
    (sortie / "RESULTATS.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
