"""The CLE_API.txt file: ONE API key, pasted by whoever runs MEDIMCOM IA; the right provider is recognised
automatically (free or paid: Groq, OpenRouter, Gemini, Mistral, xAI/Grok, Anthropic/Claude, OpenAI/GPT).

    CLE_API.txt          your file, ONE line: CLE=your_key (never published: excluded from Git by .gitignore)
                         optional lines: MODELE=…, CLE_SECOURS=…, FOURNISSEUR=… (Mistral key), PATIENTS_FICTIFS=non
    CLE_API.exemple.txt  the template published in the repository; CLE_API.txt is copied from it on first start

Read at every start of interface/serveur.py when neither --fournisseur nor --mode is given.
Order: CLE_API.txt, then (if empty) the key already kept in ~/.config/medimcom/env or .env, then the local Ollama
model if requested, otherwise the written rules (no model). Keys are never printed.

    python3 -m medimcom.cle_api          # says what will be used, without starting anything
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "CLE_API.txt"
EXEMPLE = RACINE / "CLE_API.exemple.txt"

# (start of the key, provider): most specific first ('sk-ant-' and 'sk-or-' before 'sk-')
PREFIXES = [("gsk_", "groq"), ("sk-or-", "openrouter"), ("sk-ant-", "anthropic"), ("xai-", "xai"), ("AIza", "gemini"),
            ("sk-", "openai")]
GRATUITS = {"groq": "free tier", "openrouter": "free ':free' models", "gemini": "free tier",
            "mistral": "free tier (Experiment)", "xai": "paid", "anthropic": "paid", "openai": "paid"}
VIDES = ("", "votre_cle", "votre_clé", "votre-cle", "collez_votre_cle_ici", "...", "xxx")


def detecter(cle: str) -> str | None:
    """Provider deduced from the beginning of the key; None if unknown (e.g. Mistral: set FOURNISSEUR=mistral)."""
    return next((f for p, f in PREFIXES if cle.startswith(p)), None)


def est_vide(cle: str) -> bool:
    c = (cle or "").strip().lower()
    return c in VIDES or "votre" in c or "collez" in c or len(c) < 12


def lire(chemin: Path | None = None) -> dict:
    """NAME=value lines of the file ('#' comments ignored). Creates CLE_API.txt from the template if it is missing."""
    chemin = chemin or FICHIER
    if not chemin.exists() and chemin == FICHIER and EXEMPLE.exists():
        try:
            shutil.copyfile(EXEMPLE, FICHIER)
        except OSError:
            return {}
    valeurs = {}
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8-sig", errors="replace").splitlines():   # "-sig": Windows BOM
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            if "=" not in ligne:
                # the file contains only the key, pasted alone on a line: accepted as is
                if "CLE" not in valeurs and re.fullmatch(r"[A-Za-z0-9_\-.]{12,}", ligne):
                    valeurs["CLE"] = ligne
                continue
            nom, valeur = (x.strip() for x in ligne.split("=", 1))
            valeur = re.split(r"\s+#", valeur)[0].strip().strip('"').strip("'")   # comment at the end of the line
            valeurs[nom.upper().replace(" ", "_")] = valeur
    return valeurs


def choisir(chemin: Path | None = None) -> dict:
    """What the file asks for: {fournisseur, cle, modele, secours: [(provider, key)], fictifs, probleme}."""
    from .session import FOURNISSEURS
    v = lire(chemin)
    # 'Fictitious patients' statement: 'oui' by default. If the line was deleted (file reduced to the key), 'oui' is
    # kept and the terminal says so; only an explicit 'non' switches the online model off.
    fictifs = v.get("PATIENTS_FICTIFS", "oui").strip().lower()
    choix = {"fournisseur": None, "cle": None, "modele": v.get("MODELE") or None, "secours": [], "probleme": None,
             "fictifs": fictifs not in ("non", "no", "n", "0", "faux", "false"),
             "fictifs_implicite": "PATIENTS_FICTIFS" not in v}
    cle, demande = v.get("CLE", ""), (v.get("FOURNISSEUR") or "auto").strip().lower()
    if est_vide(cle):
        return choix
    f = detecter(cle) if demande in ("", "auto") else demande
    if f not in FOURNISSEURS:
        choix["probleme"] = (f"unknown provider '{demande}'" if demande not in ("", "auto") else
                             "key not recognised: add the line FOURNISSEUR=mistral (or the provider's name)")
        return choix
    choix.update(fournisseur=f, cle=cle)
    for nom in ("CLE_SECOURS", "CLE_SECOURS_2"):
        c = v.get(nom, "")
        fs = detecter(c) if not est_vide(c) else None
        if fs and fs in FOURNISSEURS and fs != f:
            choix["secours"].append((fs, c))
    return choix


def appliquer(cfg, chemin: Path | None = None) -> str:
    """Sets cfg (provider, key, model, fallback, fictitious data) from CLE_API.txt. Returns a sentence for the
    terminal (never the key). Only call it when neither --fournisseur nor --mode was given."""
    from .session import FOURNISSEURS, charger_env
    c = choisir(chemin)
    if c["probleme"]:
        return f"⚠ CLE_API.txt: {c['probleme']}. The agents run on their written rules (no language model)."
    if not c["fournisseur"]:
        charger_env()        # CLE= empty: a key already kept on this computer (~/.config/medimcom/env or .env)?
        gardee = next((f for f in ("groq", "gemini", "openrouter", "mistral", "anthropic", "openai", "xai")
                       if os.environ.get(FOURNISSEURS[f]["variable_cle"])), None)
        if not gardee:
            return ("CLE_API.txt: no API key. The agents run on their written rules (no language model). "
                    "To use a model: in CLE_API.txt, replace votre_clé with your API key (line CLE=).")
        c.update(fournisseur=gardee, cle=os.environ[FOURNISSEURS[gardee]["variable_cle"]])
        origine = "key kept on this computer (CLE_API.txt is empty)"
    else:
        origine = "CLE_API.txt"
    if not c["fictifs"] and origine == "CLE_API.txt":
        return ("⚠ CLE_API.txt: PATIENTS_FICTIFS=non. An online model receives the agents' messages: it is only used with "
                "fictitious patients. The agents run on their written rules (no language model). "
                "To use it: PATIENTS_FICTIFS=oui in CLE_API.txt.")
    f = FOURNISSEURS[c["fournisseur"]]
    os.environ[f["variable_cle"]] = c["cle"]          # the file wins over an older key of the same provider
    cfg.fournisseur, cfg.cle, cfg.donnees_fictives = c["fournisseur"], c["cle"], True
    if c["modele"]:
        cfg.modele = c["modele"]
    for fs, cs in c["secours"]:
        os.environ[FOURNISSEURS[fs]["variable_cle"]] = cs
        if fs not in cfg.secours:
            cfg.secours.append(fs)
    modele = c["modele"] or f["modele"]
    texte = (f"✓ {origine}: {f['nom']} — {GRATUITS.get(c['fournisseur'], '')} — model {modele}"
             + (f"; fallback: {', '.join(FOURNISSEURS[s]['nom'] for s, _ in c['secours'])}" if c["secours"] else ""))
    if c.get("fictifs_implicite") and origine == "CLE_API.txt":
        texte += ("\n  Reminder: messages are sent to the provider, outside the country: FICTITIOUS patients only "
                  "(UAE Federal Law No. 2 of 2019, Art. 13).")
    return texte


def cles_a_memoriser(chemin: Path | None = None) -> dict[str, str]:
    """{VARIABLE: key} from the file, for the personal copy ~/.config/medimcom/env."""
    from .session import FOURNISSEURS
    c = choisir(chemin)
    sortie = {}
    if c["fournisseur"]:
        sortie[FOURNISSEURS[c["fournisseur"]]["variable_cle"]] = c["cle"]
    for fs, cs in c["secours"]:
        sortie[FOURNISSEURS[fs]["variable_cle"]] = cs
    return sortie


def main() -> int:
    from .session import Config
    cfg = Config()
    print(appliquer(cfg))
    return 0 if cfg.fournisseur else 1


if __name__ == "__main__":
    sys.exit(main())
