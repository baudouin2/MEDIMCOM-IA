"""Banc d'évaluation des agents : joue les scénarios et vérifie leurs « attendus ».

    python evaluer_agents.py                                   # mode simulé (référence : tout doit passer)
    python evaluer_agents.py --mode ollama --modele qwen3:8b --repetitions 3
    python evaluer_agents.py --mode openai --url http://localhost:8080/v1 --modele qwen2.5-7b-instruct
    python evaluer_agents.py --ordre aleatoire --repetitions 5 # l'ordre de passage des agents change à chaque run

Sortie : un tableau à l'écran, sortie/evaluation.json et sortie/evaluation.md.
Codes de retour : 0 tout va bien ; 1 un invariant de SÉCURITÉ a échoué ; 2 la mesure n'est pas valable
(le modèle n'a pas répondu : replis sur les politiques écrites ou runs interrompus).
"""
import sys as _sys
for _flux in (_sys.stdout, _sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

import argparse
import io
import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

from main import lire_modeles
from medimcom.evaluation import evaluer
from medimcom.session import Config, construire

ICI = Path(__file__).parent


def jouer(cfg: Config, chemin: Path, bavard: bool):
    ctx, agents, orchestrateur = construire(cfg)
    scenario = json.loads(chemin.read_text(encoding="utf-8"))
    debut = time.time()
    if bavard:
        orchestrateur.lancer(scenario)
    else:
        with redirect_stdout(io.StringIO()):
            orchestrateur.lancer(scenario)
    duree = time.time() - debut
    degradations = sum(1 for l in ctx.journal.lignes if l["type"] == "degradation")
    filets = sum(1 for l in ctx.journal.lignes if l["type"] == "filet_de_securite")
    return evaluer(scenario, ctx), duree, degradations, filets, ctx


def main(argv=None):
    p = argparse.ArgumentParser(description="Banc d'évaluation des agents MEDIMCOM IA")
    p.add_argument("--mode", choices=["simule", "ollama", "openai"], default="simule")
    p.add_argument("--modele", default="qwen3:8b")
    p.add_argument("--modeles", default=None)
    p.add_argument("--url", default=None)
    p.add_argument("--cle", default=None)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--scenarios", nargs="*", default=None, help="fichiers de scénario (défaut : tous ceux qui ont des attendus)")
    p.add_argument("--repetitions", type=int, default=1)
    p.add_argument("--ordre", choices=["fixe", "aleatoire"], default="fixe")
    p.add_argument("--sans-repli", action="store_true", help="mesurer le modèle seul, sans repli sur les politiques écrites")
    p.add_argument("--sortie", default=str(ICI / "sortie"))
    p.add_argument("--bavard", action="store_true")
    p.add_argument("--fournisseur", choices=["xai"], default=None,
                   help="modèle en ligne préréglé : xai (Grok) ; clé dans la variable XAI_API_KEY")
    p.add_argument("--pays", choices=["AE", "CM"], default="AE", help="droit appliqué par le juriste : AE (Émirats, pays hôte) ou CM (Cameroun)")
    p.add_argument("--recherche", default=None,
                   help="recherche hybride mots + sens dans la base : ollama:bge-m3 (index construit par kb/outils/construire_vecteurs.py) ou hachage")
    p.add_argument("--donnees-fictives", action="store_true",
                   help="obligatoire avec un modèle en ligne : atteste que seuls des patients fictifs sont utilisés")
    a = p.parse_args(argv)

    chemins = [Path(x) for x in a.scenarios] if a.scenarios else sorted(
        c for c in (ICI / "scenarios").glob("*.json") if "attendus" in json.loads(c.read_text(encoding="utf-8")))
    resultats, lignes = {}, []
    total = len(chemins) * a.repetitions
    for chemin in chemins:
        attendus = json.loads(chemin.read_text(encoding="utf-8")).get("attendus", [])
        for r in range(a.repetitions):
            n = len(lignes) + 1
            print(f"[{n}/{total}] {chemin.stem} · run {r + 1} …", file=sys.stderr, flush=True)
            cfg = Config(mode=a.mode, modele=a.modele, modeles=lire_modeles(a.modeles), url=a.url, cle=a.cle,
                         temperature=a.temperature, verbeux=a.bavard, repli_sans_ia=not a.sans_repli,
                         ordre=a.ordre, graine=r + 1, fournisseur=a.fournisseur, donnees_fictives=a.donnees_fictives, recherche=a.recherche, pays=a.pays)
            try:
                res, duree, degr, filets, _ = jouer(cfg, chemin, a.bavard)
                erreur = None
            except Exception as e:     # serveur arrêté, délai dépassé… : run « non mesuré », on continue
                erreur = f"{e.__class__.__name__}: {str(e)[:200]}"
                res, duree, degr, filets = [], 0.0, 0, 0
            print(f"        {sum(x['ok'] for x in res)}/{len(res)} attendus · {duree:.0f} s · replis {degr}"
                  + (f" · ERREUR {erreur}" if erreur else ""), file=sys.stderr, flush=True)
            lignes.append({"scenario": chemin.stem, "run": r + 1, "duree_s": round(duree, 1), "degradations": degr,
                           "filets_de_securite": filets, "erreur": erreur, "resultats": res})
            for x in res:
                cle = (chemin.stem, x["id"])
                e = resultats.setdefault(cle, {"scenario": chemin.stem, "id": x["id"], "categorie": x["categorie"],
                                               "description": x["description"], "reussites": 0, "essais": 0, "details": []})
                e["essais"] += 1
                e["reussites"] += int(x["ok"])
                if not x["ok"]:
                    e["details"].append(f"run {r + 1} : {x['detail']}")

    # Tableau
    tableau = ["| Scénario | Attendu | Catégorie | Réussite | Description |", "|---|---|---|---|---|"]
    for e in resultats.values():
        taux = f"{e['reussites']}/{e['essais']}"
        tableau.append(f"| {e['scenario']} | {e['id']} | {e['categorie']} | {taux} | {e['description']} |")
    secu = [e for e in resultats.values() if e["categorie"] == "securite"]
    capa = [e for e in resultats.values() if e["categorie"] == "capacite"]
    mesure = bool(secu)
    taux_secu = sum(e["reussites"] for e in secu) / max(1, sum(e["essais"] for e in secu))
    taux_capa = sum(e["reussites"] for e in capa) / max(1, sum(e["essais"] for e in capa))
    replis = sum(l["degradations"] for l in lignes)
    erreurs = sum(1 for l in lignes if l.get("erreur"))
    capa_valide = mesure and (a.mode == "simule" or replis == 0)
    resume = (f"Mode {a.mode}" + (f" ({a.modele})" if a.mode != "simule" else "") + f", ordre {a.ordre}, "
              f"{a.repetitions} répétition(s) : sécurité " + (f"{taux_secu:.0%}" if mesure else "NON MESURÉE") + ", capacité "
              + (f"{taux_capa:.0%}" if capa_valide else "NON MESURÉE") + ". "
              f"Replis sur politique écrite : {replis} ; runs interrompus : {erreurs} ; "
              f"filets de sécurité déclenchés : {sum(l['filets_de_securite'] for l in lignes)}.")
    if replis:
        resume += (" ATTENTION : le modèle n'a pas répondu à chaque tour (vérifier que le serveur du modèle tourne — Ollama : "
                   "« ollama list » — et que le modèle est téléchargé) ; les politiques écrites ont pris le relais, donc la "
                   "capacité du modèle n'est pas mesurée. Relancer avec --sans-repli pour mesurer le modèle seul.")
    if erreurs:
        resume += (f" ATTENTION : {erreurs} run(s) interrompu(s) par une erreur du modèle ou du serveur ; ils ne sont pas comptés "
                   "(vérifier que le serveur tourne et que le modèle est téléchargé).")
    echecs = [f"- {e['scenario']} {e['id']} : " + " | ".join(e["details"][:3]) for e in resultats.values() if e["details"]]

    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "evaluation.json").write_text(json.dumps({"resume": resume, "attendus": list(resultats.values()), "runs": lignes},
                                                       ensure_ascii=False, indent=2), encoding="utf-8")
    (sortie / "evaluation.md").write_text("# Évaluation des agents\n\n" + resume + "\n\n" + "\n".join(tableau)
                                          + ("\n\n## Échecs\n\n" + "\n".join(echecs) if echecs else "") + "\n", encoding="utf-8")
    print("\n".join(tableau))
    print("\n" + resume)
    if echecs:
        print("Échecs :\n" + "\n".join(echecs))
    for l in lignes:
        if l.get("erreur"):
            print(f"Run interrompu, non compté : {l['scenario']} run {l['run']} — {l['erreur']}")
    print(f"Fichiers : {sortie / 'evaluation.md'} · {sortie / 'evaluation.json'}")
    if mesure and taux_secu < 1:
        return 1
    return 2 if (not capa_valide or erreurs) else 0


if __name__ == "__main__":
    sys.exit(main())
