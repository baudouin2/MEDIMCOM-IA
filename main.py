"""Point d'entrée : joue un scénario avec les 6 agents (traducteur, assistant, juriste, 3 institutions).

Exemples :
    python main.py                                                 # mode simulé (sans IA)
    python main.py --scenario scenarios/crise.json                 # crise
    python main.py --mode ollama --modele qwen3:8b                 # vrais agents (Ollama)
    python main.py --mode openai --url http://localhost:8080/v1 --modele qwen2.5-7b-instruct
    python main.py --ordre aleatoire --graine 3                    # ordre de passage aléatoire
Guide : docs/technique/ARCHITECTURE_AGENTS.md
"""

import sys as _sys
for _flux in (_sys.stdout, _sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
from pathlib import Path

from medimcom.session import BOITES, Config, construire  # noqa: F401  (BOITES réexporté pour les tests)

ICI = Path(__file__).parent


def lire_modeles(texte: str | None) -> dict:
    """« juriste=qwen3:8b,assistant=llama3.1:8b » -> {"juriste": "qwen3:8b", ...}"""
    return dict(x.split("=", 1) for x in texte.split(",") if "=" in x) if texte else {}


def main():
    p = argparse.ArgumentParser(description="MEDIMCOM IA – prototype multi-agents local")
    p.add_argument("--mode", choices=["simule", "ollama", "openai"], default="simule")
    p.add_argument("--modele", default="qwen3:8b", help="modèle capable d'appeler des outils")
    p.add_argument("--modeles", default=None, help="modèle par agent : juriste=qwen3:8b,assistant=llama3.1:8b")
    p.add_argument("--url", default=None, help="mode openai : adresse du serveur, ex. http://localhost:8080/v1")
    p.add_argument("--cle", default=None, help="mode openai : clé d'API (ou variable MEDIMCOM_CLE)")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--scenario", default=str(ICI / "scenarios" / "grossesse.json"))
    p.add_argument("--regles", default=None, help="fichier de règles du juriste (défaut : celui du pays choisi avec --pays)")
    p.add_argument("--langue", choices=["fr", "en"], default="fr", help="langue des constats du juriste")
    p.add_argument("--sortie", default=str(ICI / "sortie"))
    p.add_argument("--silencieux", action="store_true")
    p.add_argument("--pictogrammes", default=None,
                   help="moteur de l'agent 1 sous la forme paquet.module:Classe (défaut : lexique de démonstration)")
    p.add_argument("--sans-repli", action="store_true", help="ne pas se replier sur les politiques écrites si le modèle tombe")
    p.add_argument("--ordre", choices=["fixe", "aleatoire"], default="fixe", help="ordre de passage des agents à chaque round")
    p.add_argument("--graine", type=int, default=0)
    p.add_argument("--fournisseur", choices=["gemini", "groq", "openrouter", "mistral", "xai"], default=None,
                   help="modèle en ligne préréglé (offre gratuite possible) : gemini, groq, openrouter, mistral, xai ; "
                        "clé dans GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, MISTRAL_API_KEY ou XAI_API_KEY")
    p.add_argument("--base", default=None,
                   help="dossier de la base constituée (défaut : MEDIMCOM_IA/base_v2 puis ~/MEDIMCOM_base_v2) ; « aucune » pour s'en passer")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh"], default=None,
                   help="effort de réflexion des modèles qui raisonnent (grok-4.7…) : low = plus rapide et moins cher, pour une démo")
    p.add_argument("--agents-ia", default="tous",
                   help="agents qui utilisent le modèle, séparés par des virgules (assistant, traducteur, juriste, autorite_sante, "
                        "hopital, cellule_crise) ou « tous » ; les autres suivent leur politique écrite, instantanée et vérifiée "
                        "(défaut : tous)")
    p.add_argument("--secours", default="", help="fournisseurs de secours dans l'ordre, ex. groq,openrouter (quota épuisé ou panne)")
    p.add_argument("--pays", choices=["AE", "CM"], default="AE", help="droit appliqué par le juriste : AE (Émirats, pays hôte) ou CM (Cameroun)")
    p.add_argument("--recherche", default=None,
                   help="recherche hybride mots + sens dans la base : ollama:bge-m3 (index construit par kb/outils/construire_vecteurs.py) ou hachage")
    p.add_argument("--donnees-fictives", action="store_true",
                   help="obligatoire avec un modèle en ligne : atteste que seuls des patients fictifs sont utilisés")
    a = p.parse_args()

    cfg = Config(mode=a.mode, modele=a.modele, modeles=lire_modeles(a.modeles), url=a.url, cle=a.cle,
                 temperature=a.temperature, regles=a.regles, langue=a.langue, verbeux=not a.silencieux,
                 pictogrammes=a.pictogrammes, repli_sans_ia=not a.sans_repli, ordre=a.ordre, graine=a.graine,
                 fournisseur=a.fournisseur, secours=[x for x in a.secours.split(',') if x], effort=a.effort, base=a.base,
                 agents_ia=None if a.agents_ia.strip() in ('tous', 'all', '') else [x.strip() for x in a.agents_ia.split(',') if x.strip()], donnees_fictives=a.donnees_fictives, recherche=a.recherche, pays=a.pays)
    ctx, agents, orchestrateur = construire(cfg)
    journal = ctx.journal
    modeles = sorted({getattr(x.cerveau, "modele", "") for x in agents} - {""})
    print(f"Mode : {agents[0].cerveau.nom}" + (f" ({', '.join(modeles)})" if modeles else " — aucune IA, politiques écrites à la main"))

    scenario = json.loads(Path(a.scenario).read_text(encoding="utf-8"))
    orchestrateur.lancer(scenario)

    sortie = Path(a.sortie)
    journal.sauver(sortie / "journal.json")
    (sortie / "dossier_final.txt").write_text(ctx.dossier.resume(), encoding="utf-8")
    print("\n=== Bilan ===")
    print("  verdicts du juriste (dans l'ordre, revérifications comprises) :")
    for v in ctx.dossier.verdicts:
        objet = v.get("medicament") or v["objet"]
        print(f"    #{v['decision_id']} {objet:<22} → {v['verdict']}")
    print("  état final des décisions :")
    for d in ctx.dossier.decisions.values():
        quoi = d.get("medicament") or d["type"]
        par = f" (par {d['maintien']['par']} : « {d['maintien']['justification'][:60]} »)" if d.get("maintien") else ""
        print(f"    #{d['id']} {quoi:<22} → {d['statut']}{par}")
    for m in ctx.crise.mesures:
        print(f"  mesure ({m['par']}) : {m['mesure']} [{m['citation']}]")
    for i in ctx.crise.incidents:
        print(f"  incident ({i['par']}, {i['gravite']}) : {i['description'][:90]}")
    for l in ctx.dossier.lacunes:
        print(f"  lacune {l['id'] or '-'} : {l['sujet']}")
    print(f"  messages échangés : {len(ctx.messagerie.historique)} · lignes de journal : {len(journal.lignes)}")
    print(f"  vérification du journal : {journal.verifier()}")
    print(f"  fichiers : {sortie / 'journal.json'} · {sortie / 'dossier_final.txt'}")
    print("  page lisible du journal : python exporter_journal.py " + str(sortie / "journal.json"))
    replis = sum(1 for l in journal.lignes if l["type"] == "degradation")
    if a.mode != "simule" and replis:
        print(f"  ⚠ {replis} tour(s) joué(s) par les politiques écrites : le modèle n'a pas répondu (serveur lancé ? modèle téléchargé ?)")
        return 2
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
