"""Entry point (terminal): plays a scenario with the 6 agents (translator, assistant, jurist, 3 institutions).

Examples:
    python main.py                                                 # simulated mode (no AI)
    python main.py --scenario scenarios/crise.json                 # crisis
    python main.py --mode ollama --modele qwen3:8b                 # real agents (Ollama)
    python main.py --mode openai --url http://localhost:8080/v1 --modele qwen2.5-7b-instruct
    python main.py --ordre aleatoire --graine 3                    # random order of play
Guide: docs/technique/ARCHITECTURE_AGENTS.md
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
    p = argparse.ArgumentParser(description="MEDIMCOM IA – local multi-agent prototype")
    p.add_argument("--mode", choices=["simule", "ollama", "openai"], default="simule")
    p.add_argument("--modele", default="qwen3:8b", help="model able to call tools")
    p.add_argument("--modeles", default=None, help="model per agent: juriste=qwen3:8b,assistant=llama3.1:8b")
    p.add_argument("--url", default=None, help="openai mode: server address, e.g. http://localhost:8080/v1")
    p.add_argument("--cle", default=None, help="openai mode: API key (or MEDIMCOM_CLE variable)")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--scenario", default=str(ICI / "scenarios" / "grossesse.json"))
    p.add_argument("--regles", default=None, help="jurist rules file (default: the one of the country chosen with --pays)")
    p.add_argument("--langue", choices=["fr", "en"], default="fr", help="language of the jurist's findings")
    p.add_argument("--sortie", default=str(ICI / "sortie"))
    p.add_argument("--silencieux", action="store_true")
    p.add_argument("--pictogrammes", default=None,
                   help="agent 1 engine as package.module:Class (default: demo lexicon)")
    p.add_argument("--sans-repli", action="store_true", help="do not fall back on the written policies if the model fails")
    p.add_argument("--ordre", choices=["fixe", "aleatoire"], default="fixe", help="order of play of the agents at each round")
    p.add_argument("--graine", type=int, default=0)
    p.add_argument("--fournisseur", choices=["gemini", "groq", "openrouter", "mistral", "xai", "anthropic", "openai"], default=None,
                   help="preset online model (free tiers possible): gemini, groq, openrouter, mistral, xai, anthropic, openai; "
                        "key in CLE_API.txt or in GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, MISTRAL_API_KEY, XAI_API_KEY…")
    p.add_argument("--base", default=None,
                   help="folder of the built base (default: MEDIMCOM_IA/base_v2 then ~/MEDIMCOM_base_v2); 'aucune' to do without")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh"], default=None,
                   help="reasoning effort of reasoning models (grok-4.7…): low = faster and cheaper, for a demo")
    p.add_argument("--agents-ia", default="tous",
                   help="agents that use the model, comma-separated (assistant, traducteur, juriste, autorite_sante, "
                        "hopital, cellule_crise) or 'tous' (all); the others follow their written, instant and verified policy "
                        "(default: tous)")
    p.add_argument("--secours", default="", help="fallback providers in order, e.g. groq,openrouter (quota exhausted or outage)")
    p.add_argument("--pays", choices=["AE", "CM"], default="AE", help="law applied by the jurist: AE (United Arab Emirates, host country) or CM (Cameroon)")
    p.add_argument("--recherche", default=None,
                   help="hybrid word + meaning search in the base: ollama:bge-m3 (index built by kb/outils/construire_vecteurs.py) or hachage")
    p.add_argument("--donnees-fictives", action="store_true",
                   help="required with an online model: certifies that only fictitious patients are used")
    a = p.parse_args()

    cfg = Config(mode=a.mode, modele=a.modele, modeles=lire_modeles(a.modeles), url=a.url, cle=a.cle,
                 temperature=a.temperature, regles=a.regles, langue=a.langue, verbeux=not a.silencieux,
                 pictogrammes=a.pictogrammes, repli_sans_ia=not a.sans_repli, ordre=a.ordre, graine=a.graine,
                 fournisseur=a.fournisseur, secours=[x for x in a.secours.split(',') if x], effort=a.effort, base=a.base,
                 agents_ia=None if a.agents_ia.strip() in ('tous', 'all', '') else [x.strip() for x in a.agents_ia.split(',') if x.strip()], donnees_fictives=a.donnees_fictives, recherche=a.recherche, pays=a.pays)
    ctx, agents, orchestrateur = construire(cfg)
    journal = ctx.journal
    modeles = sorted({getattr(x.cerveau, "modele", "") for x in agents} - {""})
    print(f"Mode: {agents[0].cerveau.nom}" + (f" ({', '.join(modeles)})" if modeles else " — no AI, hand-written policies"))

    scenario = json.loads(Path(a.scenario).read_text(encoding="utf-8"))
    orchestrateur.lancer(scenario)

    sortie = Path(a.sortie)
    journal.sauver(sortie / "journal.json")
    (sortie / "dossier_final.txt").write_text(ctx.dossier.resume(), encoding="utf-8")
    print("\n=== Summary ===")
    print("  jurist verdicts (in order, re-checks included):")
    for v in ctx.dossier.verdicts:
        objet = v.get("medicament") or v["objet"]
        print(f"    #{v['decision_id']} {objet:<22} → {v['verdict']}")
    print("  final state of the decisions:")
    for d in ctx.dossier.decisions.values():
        quoi = d.get("medicament") or d["type"]
        par = f" (par {d['maintien']['par']} : « {d['maintien']['justification'][:60]} »)" if d.get("maintien") else ""
        print(f"    #{d['id']} {quoi:<22} → {d['statut']}{par}")
    for m in ctx.crise.mesures:
        print(f"  measure ({m['par']}): {m['mesure']} [{m['citation']}]")
    for i in ctx.crise.incidents:
        print(f"  incident ({i['par']}, {i['gravite']}): {i['description'][:90]}")
    for l in ctx.dossier.lacunes:
        print(f"  gap {l['id'] or '-'}: {l['sujet']}")
    print(f"  messages exchanged: {len(ctx.messagerie.historique)} · journal lines: {len(journal.lignes)}")
    print(f"  journal check: {journal.verifier()}")
    print(f"  files: {sortie / 'journal.json'} · {sortie / 'dossier_final.txt'}")
    print("  readable journal page: python exporter_journal.py " + str(sortie / "journal.json"))
    replis = sum(1 for l in journal.lignes if l["type"] == "degradation")
    if a.mode != "simule" and replis:
        print(f"  ⚠ {replis} turn(s) played by the written policies: the model did not answer (server started? model downloaded?)")
        return 2
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
