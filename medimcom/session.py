"""Session assembly: configuration -> context, agents, coordinator.

Used by main.py, interface/serveur.py, the evaluation bench (evaluer_agents.py) and the tests,
so that they all run exactly the same system.
"""
import hashlib
import importlib
import ipaddress
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .agents import Assistant, AutoriteSante, CelluleCrise, Contexte, Hopital, Juriste, ModeleHorsService, Traducteur
from .base import BaseConnaissances
from .cerveaux import CerveauOllama, CerveauOpenAI, CerveauSecours, CerveauSimule
from .dossier import Dossier
from .journal import Journal
from .messagerie import Messagerie
from .orchestrateur import Orchestrateur
from .regles import MoteurRegles

RACINE = Path(__file__).resolve().parent.parent
VERSION = "1.1"
BOITES = {"traducteur", "assistant", "juriste", "medecin", "autorite_sante", "hopital", "cellule_crise"}
CLASSES = [Traducteur, Assistant, Juriste, AutoriteSante, Hopital, CelluleCrise]


@dataclass
class Config:
    mode: str = "simule"                       # simule | ollama | openai
    modele: str = "qwen3:8b"                   # default model
    modeles: dict = field(default_factory=dict)   # model per agent, e.g. {"juriste": "qwen3:8b"}
    url: str | None = None                     # mode openai : ex. http://localhost:8080/v1
    cle: str | None = None                     # openai mode: API key (otherwise MEDIMCOM_CLE variable)
    temperature: float = 0.0
    regles: str | None = None                  # jurist rules file (default: the country's)
    pays: str = "AE"                           # AE (United Arab Emirates, host country) or CM (Cameroon)
    langue: str = "fr"
    verbeux: bool = True
    pictogrammes: str | None = None            # paquet.module:Classe
    repli_sans_ia: bool = True
    ordre: str = "fixe"                        # fixe | aleatoire
    graine: int = 0
    fournisseur: str | None = None             # preset online service: gemini, groq, openrouter, mistral, xai, anthropic, openai
    agents_ia: list | None = None             # agents that use the model (None = all); the others: written policy
    base_trouvee: str | None = None            # filled at start-up: base_v2 folder actually used
    base: str | None = None                    # base_v2 folder (default: automatic search; "aucune" to do without)
    effort: str | None = None                  # reasoning effort of reasoning models: low, medium, high, xhigh
    secours: list = field(default_factory=list)   # fallback providers tried in order if the first fails (quota, outage)
    donnees_fictives: bool = False             # required for an online model: certifies that only fictitious patients are used
    recherche: str | None = None               # hybrid search in the base: "ollama:bge-m3" or "hachage" (default: BM25 only)


# Preset online services (OpenAI-compatible API). Data sent there leaves the UAE: use only with fictitious patients
# (Federal Law No. 2 of 2019 on ICT in health; this is what the jurist enforces). Free tiers change often and some reuse
# requests to improve their models: fictitious patients only. "modele" is the model used if --modele is not given
# (change it if the provider retires it).
FOURNISSEURS = {
    "gemini": {"nom": "Google Gemini (online)", "url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "variable_cle": "GEMINI_API_KEY", "modele": "gemini-3.8-flash", "societe": "Google", "pays": "États-Unis",
               "console": "https://aistudio.google.com/apikey"},
    "groq": {"nom": "Groq (online)", "url": "https://api.groq.com/openai/v1", "variable_cle": "GROQ_API_KEY",
             "modele": "qwen/qwen3.8-27b", "societe": "Groq", "pays": "États-Unis", "console": "https://console.groq.com/keys"},
    "openrouter": {"nom": "OpenRouter (online)", "url": "https://openrouter.ai/api/v1", "variable_cle": "OPENROUTER_API_KEY",
                   "modele": "google/gemma-4-31b-it:free", "societe": "OpenRouter (routage vers plusieurs hébergeurs)",
                   "pays": "États-Unis", "console": "https://openrouter.ai/keys"},
    "mistral": {"nom": "Mistral AI (online)", "url": "https://api.mistral.ai/v1", "variable_cle": "MISTRAL_API_KEY",
                "modele": "mistral-large-latest", "societe": "Mistral AI", "pays": "France (Union européenne)",
                "console": "https://console.mistral.ai/api-keys"},
    "anthropic": {"nom": "Anthropic / Claude (online)", "url": "https://api.anthropic.com/v1", "variable_cle": "ANTHROPIC_API_KEY",
                  "modele": "claude-haiku-5-5", "societe": "Anthropic", "pays": "États-Unis",
                  "console": "https://platform.claude.com/settings/keys"},
    "openai": {"nom": "OpenAI / GPT (online)", "url": "https://api.openai.com/v1", "variable_cle": "OPENAI_API_KEY",
               "modele": "gpt-5.4-mini", "societe": "OpenAI", "pays": "États-Unis", "console": "https://platform.openai.com/api-keys"},
    "xai": {"nom": "xAI / Grok (online)", "url": "https://api.x.ai/v1", "variable_cle": "XAI_API_KEY", "modele": "grok-4.7",
            "societe": "xAI (groupe SpaceX)", "pays": "États-Unis", "console": "https://console.x.ai"},
}
MODELE_PAR_DEFAUT = "qwen3:8b"


def est_en_ligne(url: str) -> bool:
    """True if the address is not on this machine or the local network (so a service hosted elsewhere)."""
    hote = (urlparse(url).hostname or "").lower()
    if hote in ("localhost", ""):
        return hote == ""
    try:
        ip = ipaddress.ip_address(hote)
        return not (ip.is_loopback or ip.is_private or ip.is_link_local)
    except ValueError:
        return not hote.endswith(".local")


REGLES_PAR_PAYS = {"AE": RACINE / "kb" / "regles_uae.json", "CM": RACINE / "kb" / "regles_cm.json"}


# PERSONAL copy of the keys, outside the project: it survives new unzipped versions and is never published.
ENV_PERSONNEL = Path.home() / ".config" / "medimcom" / "env"


def _lire_cles(chemin: Path) -> dict[str, str]:
    cles = {}
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip().removeprefix("export ").strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                nom, valeur = (x.strip().strip('"').strip("'") for x in ligne.split("=", 1))
                if nom.endswith("_API_KEY") and valeur:
                    cles.setdefault(nom, valeur)
    return cles


def memoriser_cles(source: Path | None = None, cible: Path | None = None) -> list[str]:
    """Copies the API keys of CLE_API.txt and of the project's `.env` into the personal copy ~/.config/medimcom/env
    (created if needed, readable by you only): they stay on the computer even if the project folder is replaced by a
    new version. Returns the NAMES of the keys added or updated (never their value)."""
    par_defaut = source is None
    source, cible = source or RACINE / ".env", cible or ENV_PERSONNEL
    projet = _lire_cles(source)
    if par_defaut:                      # the key pasted in CLE_API.txt is also kept on the computer
        from .cle_api import cles_a_memoriser
        projet.update(cles_a_memoriser())
    if not projet:
        return []
    perso = _lire_cles(cible)
    changees = [n for n, v in projet.items() if perso.get(n) != v]
    if not changees:
        return []
    cible.parent.mkdir(parents=True, exist_ok=True)
    lignes = cible.read_text(encoding="utf-8").splitlines() if cible.exists() else [
        "# Clés d'API de MEDIMCOM IA (copie personnelle, hors du projet, jamais publiée)."]
    lignes = [l for l in lignes if l.strip().removeprefix("export ").split("=", 1)[0].strip() not in changees]
    lignes += [f"{n}={projet[n]}" for n in changees]
    cible.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    try:
        cible.chmod(0o600)
    except OSError:
        pass
    return changees


def charger_env(chemin: Path | None = None) -> int:
    """Reads API keys from the `.env` file at the project root (NAME=value lines), then from the personal copy
    ~/.config/medimcom/env, without overwriting an already defined variable. Neither is published:
    `.env` is excluded from the repository by .gitignore, and the personal copy is outside the project."""
    if chemin is None:
        return charger_env(RACINE / ".env") + charger_env(ENV_PERSONNEL)
    n = 0
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne.startswith("export "):
                ligne = ligne[7:].strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                nom, valeur = (x.strip().strip('"').strip("'") for x in ligne.split("=", 1))
                if valeur.startswith("xai-") and not nom.endswith("_API_KEY"):   # "api key = xai-…": xAI key recognised by its prefix
                    nom = "XAI_API_KEY"
                if nom and valeur and nom not in os.environ:
                    os.environ[nom] = valeur
                    n += 1
    return n


def preparer(cfg: Config) -> Config:
    """Applies the country, the chosen provider and the "fictitious data" safeguard before creating the brains."""
    charger_env()
    if cfg.pays not in REGLES_PAR_PAYS:
        raise SystemExit(f"Unknown country: {cfg.pays} (available: {', '.join(REGLES_PAR_PAYS)}).")
    cfg.regles = str(cfg.regles or REGLES_PAR_PAYS[cfg.pays])
    if cfg.fournisseur:
        if cfg.fournisseur not in FOURNISSEURS:
            raise SystemExit(f"Unknown provider: {cfg.fournisseur} (available: {', '.join(FOURNISSEURS)}).")
        f = FOURNISSEURS[cfg.fournisseur]
        cfg.mode, cfg.url = "openai", cfg.url or f["url"]
        if f["modele"] and cfg.modele in (None, MODELE_PAR_DEFAUT):
            cfg.modele = f["modele"]
        cfg.cle = cfg.cle or os.environ.get(f["variable_cle"]) or os.environ.get("MEDIMCOM_CLE")
        if not cfg.cle:
            raise SystemExit(f"No API key for {f['nom']}. Simplest: paste it in {RACINE / 'CLE_API.txt'} (line CLE=) and start\n"
                             f"without --fournisseur (see docs/GUIDE_CLE_API.md). Or: the file {ENV_PERSONNEL} or {RACINE / '.env'}\n"
                             f"with the line {f['variable_cle']}=your_key, or:\n"
                             f"  export {f['variable_cle']}=...      (Windows PowerShell: $env:{f['variable_cle']}=\"...\")")
    for s in cfg.secours:
        if s not in FOURNISSEURS:
            raise SystemExit(f"Unknown fallback provider: {s} (available: {', '.join(FOURNISSEURS)}).")
    if (cfg.secours or (cfg.mode == "openai" and cfg.url and est_en_ligne(cfg.url))) and not cfg.donnees_fictives:
        raise SystemExit("ONLINE model (" + cfg.url + "): the agents' messages leave this machine and the UAE.\n"
                         "UAE Federal Law No. 2 of 2019 (Art. 13) forbids sending real health data there. Start again with\n"
                         "--donnees-fictives to certify that only fictitious patients are used (or use CLE_API.txt).")
    return cfg


def _empreinte(chemin: Path) -> str:
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()[:16]


def creer_cerveau(cfg: Config, modele: str):
    if cfg.mode == "simule":
        return CerveauSimule()
    if cfg.mode == "ollama":
        return CerveauOllama(modele, temperature=cfg.temperature)
    if cfg.mode == "openai":
        if not cfg.url:
            raise SystemExit("Mode openai: give --url (e.g. http://localhost:8080/v1).")
        c = CerveauOpenAI(cfg.url, modele, cfg.cle or os.environ.get("MEDIMCOM_CLE"), temperature=cfg.temperature, effort=cfg.effort)
        if cfg.fournisseur:
            c.nom = FOURNISSEURS[cfg.fournisseur]["nom"]
        elif est_en_ligne(cfg.url):
            c.nom = "openai-compatible (en ligne)"
        secours = []
        for s in cfg.secours:
            f = FOURNISSEURS[s]
            cle = os.environ.get(f["variable_cle"])
            if s != cfg.fournisseur and cle and f["modele"]:
                b = CerveauOpenAI(f["url"], f["modele"], cle, temperature=cfg.temperature)
                b.nom = f["nom"]
                secours.append(b)
        return CerveauSecours([c] + secours) if secours else c
    raise SystemExit(f"Unknown mode: {cfg.mode}")


def configuration(cfg: Config, agents) -> dict:
    kb = Path(cfg.regles).parent
    return {"version": VERSION, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": cfg.mode,
            "modeles": {a.nom: getattr(a.cerveau, "modele", "aucun (politique écrite)") for a in agents},
            "temperature": cfg.temperature, "ordre_des_agents": cfg.ordre, "graine": cfg.graine,
            "pays": cfg.pays, "regles": Path(cfg.regles).name,
            "recherche_dans_la_base": (f"hybride : mots-clés (BM25) + sens ({cfg.recherche}), fusion RRF ; vecteurs chargés : "
                                       f"{getattr(cfg, 'bilan_vecteurs', {})}") if cfg.recherche else "BM25 (mots-clés)",
            "repli_sans_ia": cfg.repli_sans_ia, "langue": cfg.langue,
            "fournisseur": FOURNISSEURS[cfg.fournisseur]["societe"] if cfg.fournisseur else None,
            "hebergement": ("en ligne, hors des Émirats — patients fictifs uniquement (attesté)"
                            if cfg.mode == "openai" and cfg.url and est_en_ligne(cfg.url) else "local"),
            "empreintes": {"regles": _empreinte(cfg.regles), "fiches": _empreinte(kb / "fiches.jsonl"),
                           "sources": _empreinte(kb / "sources.json"), "lacunes": _empreinte(kb / "lacunes.json")},
            "pictogrammes": cfg.pictogrammes or ("medimcom.base_v2:LexiqueBaseV2 (vocabulaire de consultation de base_v2)"
                                                 if getattr(cfg, "base_trouvee", None) and os.environ.get("MEDIMCOM_PICTOS", "bases") != "demo"
                                                 else "medimcom.pictogrammes:LexiquePictogrammes (démonstration)"),
            "base_v2": getattr(cfg, "base_trouvee", None) or "absente (base interne kb/ seulement)"}


def construire(cfg: Config):
    preparer(cfg)
    journal = Journal()
    base = BaseConnaissances(Path(cfg.regles).parent)
    enc = None
    cfg.bilan_vecteurs = {}
    if cfg.recherche:
        # Hybrid search (keywords + meaning). If the model or an index is missing, we SAY so and go on with BM25: a
        # consultation must never stop because of it.
        from .vecteurs import IndexVectoriel, encodeur
        try:
            # The server NEVER downloads a model (it can take an hour): it uses the one already installed by
            # outils/vectoriser_base.py, and only if vectors were built with it.
            enc = encodeur(cfg.recherche, telecharger=False)
            from .base_v2 import trouver_base as _trouver
            v2 = _trouver(cfg.base) if cfg.base != "aucune" else None
            existe = (Path(cfg.regles).parent / "index" / f"vecteurs_{enc.nom}.jsonl").exists() or \
                bool(v2 and list((v2 / "07_vecteurs").glob(f"*.{enc.nom}.npy")))
            if not existe:
                raise RuntimeError(f"no vectors built with {enc.nom}: run first "
                                   f"python outils/vectoriser_base.py --encodeur {cfg.recherche}")
            encoder_requete_test = enc.encoder(["test"], role="requete")
            if not encoder_requete_test:
                raise RuntimeError("encoder returned nothing")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ Semantic search unavailable ({e}): keyword search (BM25) only.")
            cfg.bilan_vecteurs = {"erreur": str(e)[:200]}
            enc = None
        if enc is not None:
            chemin = Path(cfg.regles).parent / "index" / f"vecteurs_{enc.nom}.jsonl"
            try:
                if chemin.exists():
                    base.brancher_vecteurs(IndexVectoriel.charger(chemin), enc)
                    cfg.bilan_vecteurs["kb"] = len(base.fiches)
                else:
                    print(f"⚠ Internal knowledge base not vectorised ({chemin.name}): python outils/vectoriser_base.py --encodeur {cfg.recherche}")
            except ValueError as e:
                print(f"⚠ {e}")
    regles = MoteurRegles(cfg.regles, base, langue=cfg.langue)
    ctx = Contexte(Dossier(journal), Messagerie(journal, set(BOITES)), journal, regles,
                   verbeux=cfg.verbeux, repli_sans_ia=cfg.repli_sans_ia)
    from .base_v2 import Corpus, LexiqueBaseV2, charger_pictogrammes, trouver_base
    base_v2 = trouver_base(cfg.base)
    cfg.base_trouvee = str(base_v2) if base_v2 else None
    if base_v2:
        corpus = Corpus(base_v2, pays=cfg.pays)
        ctx.corpus = corpus if len(corpus) else None
        if enc is not None and ctx.corpus:
            cfg.bilan_vecteurs.update(corpus.brancher_vecteurs(base_v2 / "07_vecteurs", enc))
    if cfg.pictogrammes:
        module, classe = cfg.pictogrammes.split(":")
        ctx.pictogrammeur = getattr(importlib.import_module(module), classe)()
    elif base_v2 and os.environ.get("MEDIMCOM_PICTOS", "bases") != "demo" and (base_v2 / "02_pictogrammes" / "notions.csv").exists():
        ctx.pictogrammeur = LexiqueBaseV2(base_v2, charger_pictogrammes(base_v2))
        # pictogram search index (spelling similarity) prepared in the background: several seconds with the full
        # catalogue (~20,000 images); the patient's first search does not wait
        import threading
        threading.Thread(target=lambda: ctx.pictogrammeur.recherche._ecriture_index(), daemon=True, name="index-pictos").start()
        if enc is not None:
            n = ctx.pictogrammeur.recherche.brancher_vecteurs(base_v2 / "07_vecteurs", enc)
            if n:
                cfg.bilan_vecteurs["pictogrammes"] = n
    from .bibliotheque import brancher_images
    brancher_images(getattr(ctx.pictogrammeur, "image", None))     # new "GEN:…" images if the engine provides some
    cerveaux = {}
    agents = []
    for C in CLASSES:
        if cfg.mode != "simule" and cfg.agents_ia is not None and C.nom not in cfg.agents_ia:
            agents.append(C(ctx, CerveauSimule()))      # written policy: no network wait, verified behaviour
            continue
        modele = cfg.modeles.get(C.nom, cfg.modele)
        if modele not in cerveaux:
            cerveaux[modele] = creer_cerveau(cfg, modele)
        agents.append(C(ctx, cerveaux[modele]))
    journal.ajouter("coordinateur", "configuration", configuration(cfg, agents))
    # Health check: a missing server is detected in a few seconds, not after minutes of waiting.
    for modele, cerveau in cerveaux.items():
        if hasattr(cerveau, "verifier"):
            ok, message = cerveau.verifier()
            if ok and message != "ok":            # model replaced automatically (missing for this key): we say so
                print(f"ℹ {message}", file=sys.stderr)
                journal.ajouter("coordinateur", "modele_remplace", {"demande": modele, "utilise": cerveau.modele, "message": message})
            if not ok:
                journal.ajouter("coordinateur", "modele_indisponible", {"modele": modele, "message": message})
                print(f"⚠ {message}", file=sys.stderr)
                if not cfg.repli_sans_ia:
                    raise ModeleHorsService(message)
                ctx.echecs_modele[modele] = ctx.seuil_echecs        # circuit breaker open at once: immediate fallback…
                ctx.disjoncteur_depuis[modele] = __import__("time").time()   # … and new attempt in 90 s
                ctx.etat_modele[modele] = {"disponible": False, "message": message}
            else:
                ctx.etat_modele[modele] = {"disponible": True, "message": "prêt" if cfg.mode == "ollama" else "en ligne"}
    return ctx, agents, Orchestrateur(ctx, agents, ordre=cfg.ordre, graine=cfg.graine)
