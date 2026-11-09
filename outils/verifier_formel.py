"""Vérification formelle de MEDIMCOM IA : règles du juriste, spécification, cycle de vie des décisions.

    python outils/verifier_formel.py                    # tout : énumération, preuves SMT, exploration, rapport
    python outils/verifier_formel.py --mutations        # + analyse de mutation (quelques minutes)
    python outils/verifier_formel.py --journal sortie/journal.json   # surveiller un journal existant
    python outils/verifier_formel.py --rapide           # pour l'intégration continue (exploration réduite)

Sortie : docs/technique/RAPPORT_VERIFICATION_FORMELLE.md (+ sortie/verification_formelle.json).
Code de retour 1 si une propriété est violée : la vérification bloque l'intégration continue.
Méthodes et références : docs/technique/METHODES_FORMELLES.md.
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from medimcom import formel, formel_smt  # noqa: E402
from medimcom.exploration import explorer  # noqa: E402
from medimcom.journal import Journal  # noqa: E402
from medimcom.regles import MoteurRegles  # noqa: E402
from medimcom.surveillance import PROPRIETES, surveiller  # noqa: E402

PAYS = {"AE": RACINE / "kb" / "regles_uae.json", "CM": RACINE / "kb" / "regles_cm.json"}


def _ligne(r) -> str:
    ce = ""
    if not r["ok"]:
        ce = "<br>Contre-exemple : `" + json.dumps(r["contre_exemples"][0], ensure_ascii=False)[:300] + "`"
    cas = f"{r['cas']:,}".replace(",", " ") if isinstance(r["cas"], int) else r["cas"]
    return f"| {'✅' if r['ok'] else '❌'} | `{r['id']}` | {r['titre']}{ce} | {r['methode']} | {cas} | {r.get('reference', '')} |"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rapide", action="store_true", help="exploration réduite (intégration continue)")
    p.add_argument("--mutations", action="store_true", help="analyse de mutation des règles (lent)")
    p.add_argument("--journal", help="surveiller seulement ce journal (fichier JSON)")
    p.add_argument("--pays", choices=["AE", "CM"], default="AE", help="règles utilisées avec --journal")
    p.add_argument("--sortie", default=str(RACINE / "docs" / "technique" / "RAPPORT_VERIFICATION_FORMELLE.md"))
    a = p.parse_args(argv)

    if a.journal:
        v = surveiller(Journal.charger(a.journal), MoteurRegles(PAYS[a.pays]))
        for k, x in v.items():
            print(f"{'✔' if not x else '✖'} {k} {PROPRIETES[k]}" + ("" if not x else f"\n    {x[0]}"))
        return 1 if any(v.values()) else 0

    debut, resultats, sections = time.time(), {}, []
    for pays, chemin in PAYS.items():
        m = MoteurRegles(chemin)
        print(f"[{pays}] énumération exhaustive sur le moteur réel…")
        res = formel.verifier_tout(m)
        if formel_smt.disponible():
            print(f"[{pays}] preuves SMT (Z3) et validation croisée…")
            for fam in ("partage", "envoi_patient"):
                res += formel_smt.prouver(m, fam) + [formel_smt.validation_croisee(m, fam, n=2000)]
        else:
            print("  (z3-solver absent : preuves SMT sautées ; pip install z3-solver)")
        mut = []
        if a.mutations and formel_smt.disponible():
            print(f"[{pays}] analyse de mutation…")
            mut = [formel_smt.analyse_mutations(m, fam, avec_prudence=True) for fam in ("partage", "envoi_patient")]
        n = 150 if a.rapide else 600
        print(f"[{pays}] exploration de {n} suites d'événements sur les vrais agents…")
        exp = explorer(n, 14, 2026, pays)
        resultats[pays] = {"proprietes": res, "mutations": mut, "exploration": exp}

    echecs = [(pays, r) for pays, x in resultats.items() for r in x["proprietes"] if not r["ok"]]
    echecs += [(pays, {"id": v["propriete"]}) for pays, x in resultats.items() for v in x["exploration"]["violations"]]
    md = [f"# Rapport de vérification formelle — MEDIMCOM IA", "",
          f"Généré par `outils/verifier_formel.py` le {date.today().isoformat()} en {time.time() - debut:.0f} s. "
          f"Méthodes, sémantique et références : [`METHODES_FORMELLES.md`](METHODES_FORMELLES.md).", "",
          f"**Résultat : {'toutes les propriétés sont vérifiées' if not echecs else f'{len(echecs)} propriété(s) violée(s)'}.**", ""]
    for pays, x in resultats.items():
        nom = "Émirats arabes unis (kb/regles_uae.json)" if pays == "AE" else "Cameroun (kb/regles_cm.json)"
        ok = sum(r["ok"] for r in x["proprietes"])
        total_cas = sum(r["cas"] for r in x["proprietes"] if isinstance(r["cas"], int))
        md += [f"## {nom}", "", f"{ok} propriétés sur {len(x['proprietes'])} vérifiées ; "
               f"{total_cas:,} cas examinés par énumération, plus les preuves SMT sur un domaine non borné.".replace(",", " "), "",
               "| | Propriété | Énoncé | Méthode | Cas | Référence |", "|---|---|---|---|---|---|"]
        md += [_ligne(r) for r in x["proprietes"]]
        e = x["exploration"]
        md += ["", f"**Exploration du système réel** : {e['suites']} suites, {e['evenements']} événements (dont des tentatives "
               f"d'abus), {e['lignes_de_journal']} lignes de journal, {e['envois_au_patient']} messages envoyés au patient, "
               f"{e['maintiens_acceptes']} maintiens acceptés et {e['maintiens_refuses']} refusés ; verdicts : "
               + ", ".join(f"{k} {v}" for k, v in sorted(e["verdicts"].items())) + ". "
               + ("Aucune violation des propriétés du moniteur." if not e["violations"] else
                  f"{len(e['violations'])} violation(s) : " + "; ".join(f"{v['propriete']} ({v['detail']})" for v in e["violations"])), ""]
        for mu in x["mutations"]:
            md += [f"**Analyse de mutation ({mu['famille']})** : {mu['tues']} mutants détectés sur {mu['mutants']} "
                   f"(score {mu['score']} %). Survivants : " + ("aucun." if not mu["survivants"] else "; ".join(mu["survivants"]) + "."), ""]
    md += ["## Propriétés du moniteur (journal)", "", "| | Énoncé |", "|---|---|"]
    md += [f"| `{k}` | {t} |" for k, t in PROPRIETES.items()]
    Path(a.sortie).parent.mkdir(parents=True, exist_ok=True)
    Path(a.sortie).write_text("\n".join(md) + "\n", encoding="utf-8")
    (RACINE / "sortie").mkdir(exist_ok=True)
    (RACINE / "sortie" / "verification_formelle.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1, default=str),
                                                                  encoding="utf-8")
    for pays, r in echecs:
        print(f"✖ [{pays}] {r['id']}")
    print(f"{'✔ Toutes les propriétés sont vérifiées' if not echecs else f'✖ {len(echecs)} violation(s)'} — rapport : {a.sortie}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
