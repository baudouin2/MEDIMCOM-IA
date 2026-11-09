"""Mesure de la latence EN CONDITION RÉELLE, depuis votre machine et votre connexion, avec le vrai modèle en ligne.

    python outils/mesurer_latence.py --fournisseur xai --effort low --donnees-fictives

Deux mesures :
1. Connexion : 4 appels courts au modèle, d'abord en refaisant la connexion à chaque fois (ancien comportement),
   puis en la gardant ouverte (nouveau). La différence = le temps gagné par appel grâce à la connexion gardée.
2. Consultation : un patient fictif ; le médecin pose une question, valide, le patient répond. On mesure le temps
   que voit le médecin pour chaque clic, et le temps que met l'assistant (Grok) à réfléchir en arrière-plan.

Coût : une dizaine d'appels au modèle (quelques centimes). Aucune donnée réelle : uniquement un patient fictif.
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RACINE), str(RACINE / "interface")]
from medimcom.cerveaux import CerveauSecours  # noqa: E402
from medimcom.session import Config, creer_cerveau, preparer  # noqa: E402


def _attendre(cond, limite):
    t0 = time.time()
    while not cond():
        if time.time() - t0 > limite:
            return None
        time.sleep(0.02)
    return time.time() - t0


def mesurer_connexion(cfg, n=4):
    c = creer_cerveau(cfg, cfg.modele)
    c = c.cerveaux[0] if isinstance(c, CerveauSecours) else c
    msg = [{"role": "user", "content": "Réponds seulement : ok"}]
    nouvelles, gardee = [], []
    for _ in range(n):
        if c._connexion is not None:
            c._connexion.close()
        c._connexion = None                      # ancien comportement : nouvelle connexion à chaque appel
        t0 = time.time()
        c.chat(msg, [])
        nouvelles.append(time.time() - t0)
    for _ in range(n):
        t0 = time.time()
        c.chat(msg, [])
        gardee.append(time.time() - t0)
    return nouvelles, gardee


def mesurer_consultation(cfg):
    from serveur import Application
    app = Application(cfg, asynchrone=True)
    d = app.ctx.dossier
    r = {}
    app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous mal au ventre ?", "contenu_type": "question"})
    r["Message du médecin -> pictogrammes à valider"] = _attendre(
        lambda: any(x["statut"] == "attente_validation" for x in d.decisions.values()), 30)
    prop = next((x for x in d.decisions.values() if x["statut"] == "attente_validation"), None)
    if prop is None:
        return r, app
    _attendre(lambda: app.reflexion_en_cours, 5)          # le médecin valide PENDANT que l'assistant interroge le modèle
    app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": prop["id"]})
    r["Validation -> envoyé au patient"] = _attendre(lambda: prop["statut"] == "envoye", 30)
    app.evenement({"type": "reponse_patient", "auteur": "patient", "pictogrammes": ["OUI"]})
    r["Réponse du patient -> traitée"] = _attendre(lambda: app.en_cours == 0, 30)
    fin = _attendre(lambda: app.en_cours == 0 and not app.reflexion_en_cours and not app._a_reflechir, 300)
    r["Assistant : fin de sa réflexion (arrière-plan)"] = fin
    return r, app


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fournisseur", default="xai")
    p.add_argument("--effort", default="low")
    p.add_argument("--modele", default=None)
    p.add_argument("--donnees-fictives", action="store_true")
    a = p.parse_args(argv)
    cfg = Config(fournisseur=a.fournisseur, effort=a.effort, verbeux=False, agents_ia=["assistant"],
                 donnees_fictives=a.donnees_fictives, **({"modele": a.modele} if a.modele else {}))
    preparer(cfg)
    print(f"Modèle : {cfg.modele} chez {cfg.fournisseur} (effort {cfg.effort})\n")

    print("1. Connexion au modèle (4 appels très courts chacun)")
    nouvelles, gardee = mesurer_connexion(cfg)
    m1, m2 = statistics.median(nouvelles), statistics.median(gardee[1:] or gardee)
    print(f"   nouvelle connexion à chaque appel : {', '.join(f'{x:.2f}' for x in nouvelles)} s  (médiane {m1:.2f} s)")
    print(f"   connexion gardée ouverte          : {', '.join(f'{x:.2f}' for x in gardee)} s  (médiane {m2:.2f} s)")
    print(f"   -> gain par appel : {m1 - m2:+.2f} s\n")

    print("2. Consultation fictive (ce que voit le médecin)")
    r, app = mesurer_consultation(cfg)
    for k, v in r.items():
        print(f"   {k:48s} {'jamais (délai dépassé)' if v is None else f'{v:.2f} s'}")
    durees = [l["contenu"]["duree_s"] for l in app.ctx.journal.lignes if l["type"] == "appel_modele"]
    if durees:
        print(f"   appels de l'assistant au modèle : {len(durees)} ; durées : {', '.join(f'{x:.1f}' for x in durees)} s")
    reportes = sum(1 for l in app.ctx.journal.lignes if l["type"] in ("reflexion_reportee", "reflexion_abregee"))
    print(f"   fois où l'assistant a cédé la place à un clic : {reportes}")
    if app.derniere_erreur:
        print(f"   ⚠ erreur : {app.derniere_erreur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
