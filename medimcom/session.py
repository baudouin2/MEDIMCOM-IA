"""Assemblage d'une session : configuration -> contexte, agents, coordinateur.

Utilisé par main.py, par le banc d'évaluation (evaluer_agents.py) et par les tests,
pour que tous lancent exactement le même système.
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
    modele: str = "qwen3:8b"                   # modèle par défaut
    modeles: dict = field(default_factory=dict)   # modèle par agent, ex. {"juriste": "qwen3:8b"}
    url: str | None = None                     # mode openai : ex. http://localhost:8080/v1
    cle: str | None = None                     # mode openai : clé d'API (sinon variable MEDIMCOM_CLE)
    temperature: float = 0.0
    regles: str | None = None                  # fichier de règles du juriste (défaut : celui du pays)
    pays: str = "AE"                           # AE (Émirats, pays hôte) ou CM (Cameroun)
    langue: str = "fr"
    verbeux: bool = True
    pictogrammes: str | None = None            # paquet.module:Classe
    repli_sans_ia: bool = True
    ordre: str = "fixe"                        # fixe | aleatoire
    graine: int = 0
    fournisseur: str | None = None             # service en ligne préréglé : gemini, groq, openrouter, mistral, xai
    agents_ia: list | None = None             # agents qui utilisent le modèle (None = tous) ; les autres : politique écrite
    base_trouvee: str | None = None            # rempli au démarrage : dossier base_v2 effectivement utilisé
    base: str | None = None                    # dossier base_v2 (défaut : recherche automatique ; « aucune » pour s'en passer)
    effort: str | None = None                  # effort de réflexion des modèles qui raisonnent : low, medium, high, xhigh
    secours: list = field(default_factory=list)   # fournisseurs de secours essayés dans l'ordre si le premier échoue (quota, panne)
    donnees_fictives: bool = False             # obligatoire pour un modèle en ligne : on atteste n'utiliser que des patients fictifs
    recherche: str | None = None               # recherche hybride dans la base : « ollama:bge-m3 » ou « hachage » (défaut : BM25 seul)


# Services en ligne préréglés (API compatible OpenAI). Les données y partent hors des Émirats : à n'utiliser
# qu'avec des patients fictifs (loi fédérale n° 2/2019 sur les TIC en santé ; c'est ce que le juriste fait respecter).
# Les offres gratuites changent souvent et certaines réutilisent les requêtes pour améliorer leurs modèles : patients fictifs
# seulement. « modele » est le modèle utilisé si --modele n'est pas précisé (le changer si le fournisseur le retire).
FOURNISSEURS = {
    "gemini": {"nom": "Google Gemini (en ligne)", "url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "variable_cle": "GEMINI_API_KEY", "modele": "gemini-3.8-flash", "societe": "Google", "pays": "États-Unis",
               "console": "https://aistudio.google.com/apikey"},
    "groq": {"nom": "Groq (en ligne)", "url": "https://api.groq.com/openai/v1", "variable_cle": "GROQ_API_KEY",
             "modele": "qwen/qwen3.8-27b", "societe": "Groq", "pays": "États-Unis", "console": "https://console.groq.com/keys"},
    "openrouter": {"nom": "OpenRouter (en ligne)", "url": "https://openrouter.ai/api/v1", "variable_cle": "OPENROUTER_API_KEY",
                   "modele": "google/gemma-4-31b-it:free", "societe": "OpenRouter (routage vers plusieurs hébergeurs)",
                   "pays": "États-Unis", "console": "https://openrouter.ai/keys"},
    "mistral": {"nom": "Mistral AI (en ligne)", "url": "https://api.mistral.ai/v1", "variable_cle": "MISTRAL_API_KEY",
                "modele": "mistral-large-latest", "societe": "Mistral AI", "pays": "France (Union européenne)",
                "console": "https://console.mistral.ai/api-keys"},
    "xai": {"nom": "xAI / Grok (en ligne)", "url": "https://api.x.ai/v1", "variable_cle": "XAI_API_KEY", "modele": "grok-4.7",
            "societe": "xAI (groupe SpaceX)", "pays": "États-Unis", "console": "https://console.x.ai"},
}
MODELE_PAR_DEFAUT = "qwen3:8b"


def est_en_ligne(url: str) -> bool:
    """Vrai si l'adresse n'est pas sur cette machine ou le réseau local (donc un service hébergé ailleurs)."""
    hote = (urlparse(url).hostname or "").lower()
    if hote in ("localhost", ""):
        return hote == ""
    try:
        ip = ipaddress.ip_address(hote)
        return not (ip.is_loopback or ip.is_private or ip.is_link_local)
    except ValueError:
        return not hote.endswith(".local")


REGLES_PAR_PAYS = {"AE": RACINE / "kb" / "regles_uae.json", "CM": RACINE / "kb" / "regles_cm.json"}


# Copie PERSONNELLE des clés, hors du projet : elle survit aux nouvelles versions décompressées et n'est jamais publiée.
ENV_PERSONNEL = Path.home() / ".config" / "medimcom" / "env"


def charger_env(chemin: Path | None = None) -> int:
    """Lit les clés d'API dans le fichier `.env` à la racine du projet (lignes NOM=valeur), puis dans la copie
    personnelle ~/.config/medimcom/env, sans écraser une variable déjà définie. Ni l'un ni l'autre n'est publié :
    `.env` est exclu du dépôt par .gitignore, et la copie personnelle est hors du projet."""
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
                if valeur.startswith("xai-") and not nom.endswith("_API_KEY"):   # « api key = xai-… » : clé xAI reconnue à son préfixe
                    nom = "XAI_API_KEY"
                if nom and valeur and nom not in os.environ:
                    os.environ[nom] = valeur
                    n += 1
    return n


def preparer(cfg: Config) -> Config:
    """Applique le pays, le fournisseur choisi et le garde-fou « données fictives » avant de créer les cerveaux."""
    charger_env()
    if cfg.pays not in REGLES_PAR_PAYS:
        raise SystemExit(f"Pays inconnu : {cfg.pays} (disponibles : {', '.join(REGLES_PAR_PAYS)}).")
    cfg.regles = str(cfg.regles or REGLES_PAR_PAYS[cfg.pays])
    if cfg.fournisseur:
        if cfg.fournisseur not in FOURNISSEURS:
            raise SystemExit(f"Fournisseur inconnu : {cfg.fournisseur} (disponibles : {', '.join(FOURNISSEURS)}).")
        f = FOURNISSEURS[cfg.fournisseur]
        cfg.mode, cfg.url = "openai", cfg.url or f["url"]
        if f["modele"] and cfg.modele in (None, MODELE_PAR_DEFAUT):
            cfg.modele = f["modele"]
        cfg.cle = cfg.cle or os.environ.get(f["variable_cle"]) or os.environ.get("MEDIMCOM_CLE")
        if not cfg.cle:
            raise SystemExit(f"Clé d'API manquante pour {f['nom']}. Le plus simple : créer le fichier {ENV_PERSONNEL} (gardé d'une version à l'autre) ou {RACINE / '.env'}\n"
                             f"contenant la ligne {f['variable_cle']}=votre_clé (modèle : .env.exemple). Sinon :\n"
                             f"  export {f['variable_cle']}=...      (Windows PowerShell : $env:{f['variable_cle']}=\"...\")")
    for s in cfg.secours:
        if s not in FOURNISSEURS:
            raise SystemExit(f"Fournisseur de secours inconnu : {s} (disponibles : {', '.join(FOURNISSEURS)}).")
    if (cfg.secours or (cfg.mode == "openai" and cfg.url and est_en_ligne(cfg.url))) and not cfg.donnees_fictives:
        raise SystemExit("Modèle EN LIGNE (" + cfg.url + ") : les messages des agents quittent cette machine et les Émirats.\n"
                         "La loi fédérale n° 2/2019 interdit d'y envoyer de vraies données de santé. Relancer avec\n"
                         "--donnees-fictives pour attester que seuls des patients fictifs sont utilisés.")
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
            raise SystemExit("Mode openai : préciser --url (ex. http://localhost:8080/v1).")
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
    raise SystemExit(f"Mode inconnu : {cfg.mode}")


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
        # Recherche hybride (mots-clés + sens). Si le modèle ou un index manque, on le DIT et on continue en BM25 :
        # une consultation ne doit jamais s'arrêter pour cela.
        from .vecteurs import IndexVectoriel, encodeur
        try:
            # Le serveur ne télécharge JAMAIS de modèle (cela peut prendre une heure) : il utilise celui déjà installé
            # par outils/vectoriser_base.py, et seulement si des vecteurs ont été construits avec lui.
            enc = encodeur(cfg.recherche, telecharger=False)
            from .base_v2 import trouver_base as _trouver
            v2 = _trouver(cfg.base) if cfg.base != "aucune" else None
            existe = (Path(cfg.regles).parent / "index" / f"vecteurs_{enc.nom}.jsonl").exists() or \
                bool(v2 and list((v2 / "07_vecteurs").glob(f"*.{enc.nom}.npy")))
            if not existe:
                raise RuntimeError(f"aucun vecteur construit avec {enc.nom} : lancer d'abord "
                                   f"python outils/vectoriser_base.py --encodeur {cfg.recherche}")
            encoder_requete_test = enc.encoder(["test"], role="requete")
            if not encoder_requete_test:
                raise RuntimeError("encodeur muet")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ Recherche par le sens indisponible ({e}) : recherche par mots-clés (BM25) seulement.")
            cfg.bilan_vecteurs = {"erreur": str(e)[:200]}
            enc = None
        if enc is not None:
            chemin = Path(cfg.regles).parent / "index" / f"vecteurs_{enc.nom}.jsonl"
            try:
                if chemin.exists():
                    base.brancher_vecteurs(IndexVectoriel.charger(chemin), enc)
                    cfg.bilan_vecteurs["kb"] = len(base.fiches)
                else:
                    print(f"⚠ Base interne non vectorisée ({chemin.name}) : python outils/vectoriser_base.py --encodeur {cfg.recherche}")
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
        # index de recherche des pictogrammes (ressemblance d'écriture) préparé en arrière-plan : plusieurs secondes avec
        # le catalogue complet (~20 000 images) ; la première recherche du patient n'attend pas
        import threading
        threading.Thread(target=lambda: ctx.pictogrammeur.recherche._ecriture_index(), daemon=True, name="index-pictos").start()
        if enc is not None:
            n = ctx.pictogrammeur.recherche.brancher_vecteurs(base_v2 / "07_vecteurs", enc)
            if n:
                cfg.bilan_vecteurs["pictogrammes"] = n
    from .bibliotheque import brancher_images
    brancher_images(getattr(ctx.pictogrammeur, "image", None))     # images nouvelles « GEN:… » si le moteur en fournit
    cerveaux = {}
    agents = []
    for C in CLASSES:
        if cfg.mode != "simule" and cfg.agents_ia is not None and C.nom not in cfg.agents_ia:
            agents.append(C(ctx, CerveauSimule()))      # politique écrite : aucune attente réseau, comportement vérifié
            continue
        modele = cfg.modeles.get(C.nom, cfg.modele)
        if modele not in cerveaux:
            cerveaux[modele] = creer_cerveau(cfg, modele)
        agents.append(C(ctx, cerveaux[modele]))
    journal.ajouter("coordinateur", "configuration", configuration(cfg, agents))
    # Vérification de santé : un serveur absent est détecté en quelques secondes, pas après des minutes d'attente.
    for modele, cerveau in cerveaux.items():
        if hasattr(cerveau, "verifier"):
            ok, message = cerveau.verifier()
            if ok and message != "ok":            # modèle remplacé automatiquement (absent pour cette clé) : on le dit
                print(f"ℹ {message}", file=sys.stderr)
                journal.ajouter("coordinateur", "modele_remplace", {"demande": modele, "utilise": cerveau.modele, "message": message})
            if not ok:
                journal.ajouter("coordinateur", "modele_indisponible", {"modele": modele, "message": message})
                print(f"⚠ {message}", file=sys.stderr)
                if not cfg.repli_sans_ia:
                    raise ModeleHorsService(message)
                ctx.echecs_modele[modele] = ctx.seuil_echecs        # disjoncteur ouvert d'emblée : repli immédiat…
                ctx.disjoncteur_depuis[modele] = __import__("time").time()   # … et nouvel essai dans 90 s
                ctx.etat_modele[modele] = {"disponible": False, "message": message}
            else:
                ctx.etat_modele[modele] = {"disponible": True, "message": "en ligne"}
    return ctx, agents, Orchestrateur(ctx, agents, ordre=cfg.ordre, graine=cfg.graine)
