"""Branchement de la base constituée par outils/constituer_base_v2.py (dossier « base_v2 ») sur les agents.

Où est la base ? Dans l'ordre :
  1. la variable MEDIMCOM_BASE (chemin du dossier ; « aucune » pour ne pas l'utiliser) ;
  2. MEDIMCOM_IA/base_v2 (emplacement recommandé, exclu du dépôt GitHub) ;
  3. ~/MEDIMCOM_base_v2 (emplacement par défaut du script de constitution).

Ce qu'elle apporte, sans IA ni réseau :
- `charger_pictogrammes` : les images et libellés de 02_pictogrammes deviennent des pictogrammes affichables ;
- `LexiqueBaseV2` : moteur de l'agent 1 (traduire / interpreter) sur les 1 287 notions du vocabulaire de consultation,
  expressions et notions composées comprises ; il garde les règles de sûreté du lexique de démonstration
  (négation, « au maximum », chiffres, doses, médicaments jamais perdus) ;
- `Corpus` : recherche BM25 dans les 87 textes officiels découpés par article et dans les fiches de l'OMS.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from .base import jetons
from .pictogrammes import MEDICAMENTS, MOTS, MOTS_OUTILS, LexiquePictogrammes, _norm

RACINE = Path(__file__).resolve().parent.parent

# Couleur du cadre (catégories de la bibliothèque) pour chaque catégorie du vocabulaire
CADRE_PAR_CATEGORIE = {
    "01": "reponse", "02": "reponse", "03": "reponse", "04": "reponse", "05": "emotion", "06": "soin", "07": "soin",
    "08": "personne", "09": "corps", "10": "corps", "11": "symptome", "12": "symptome", "13": "symptome", "14": "emotion",
    "15": "soin", "16": "soin", "17": "soin", "18": "soin", "19": "soin", "20": "soin", "21": "soin", "22": "soin",
    "23": "soin", "24": "personne", "25": "personne", "26": "temps", "27": "nombre", "28": "nombre", "29": "symptome",
    "30": "reponse", "99": "soin",
}
ORDRE_SOURCES = {"arasaac": 0, "mulberry": 1, "openmoji": 2}


def trouver_base(explicite: str | None = None) -> Path | None:
    for c in (explicite, os.environ.get("MEDIMCOM_BASE"), RACINE / "base_v2", Path.home() / "MEDIMCOM_base_v2"):
        if c is None or str(c).strip() == "":
            continue
        if str(c).lower() in ("aucune", "non", "0", "none"):
            return None
        p = Path(c).expanduser()
        if (p / "01_base_juridique").is_dir() or (p / "02_pictogrammes").is_dir():
            return p.resolve()
    return None


# ------------------------------------------------------------------------------------------------ pictogrammes
def lire_notions(base: Path) -> list[dict]:
    f = base / "02_pictogrammes" / "notions.csv"
    if not f.exists():
        return []
    with f.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _analyser(entree: str) -> tuple[str, str, list[str], list[str], list[str]]:
    champs = [x.strip() for x in entree.split("|")]
    fr, en = champs[0], champs[1]
    if len(champs) > 2 and champs[2].startswith("="):
        return fr, en, [fr], [x.strip() for x in champs[2][1:].split("+") if x.strip()], []
    alias = [a.strip() for a in champs[2].split("/")] if len(champs) > 2 else []
    return fr, en, [fr] + [a for a in alias if a], [], [a.strip() for a in champs[3].split("/")] if len(champs) > 3 else []


def _ident(fr: str) -> str:
    t = _norm(fr.replace("œ", "oe").replace("’", "'"))
    t = re.sub(r"\s+", " ", re.sub(r"[^\w' -]", " ", t)).strip()
    return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_").upper()[:40]


def charger_pictogrammes(base: Path) -> dict:
    """Enregistre dans la bibliothèque chaque notion qui a une image dans la base ; renvoie {id: notion}."""
    from . import bibliotheque as B
    dossier = (base / "02_pictogrammes").resolve()
    attributions = {}
    cat = dossier / "catalogue.jsonl"
    if cat.exists():
        for ligne in cat.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                x = json.loads(ligne)
                attributions[x["fichier"]] = x
    notions = {}
    for n in lire_notions(base):
        nid = n["notion"]
        code = n["categorie"][:2]
        entree = {"id": nid, "categorie": CADRE_PAR_CATEGORIE.get(code, "soin"), "categorie_vocabulaire": n["categorie"],
                  "fr": n["fr"], "en": n["en"], "ar": n.get("ar", "") or n["fr"],
                  "composition": [c for c in n.get("composition", "").split(" + ") if c]}
        notions[nid] = entree
        if entree["composition"]:
            continue
        images = [i for i in n.get("images", "").split() if i and not i.startswith("[")]
        images.sort(key=lambda i: ORDRE_SOURCES.get(i.split("/")[-1].split("_")[0], 9))
        for im in images:
            f = (dossier / im).resolve()
            if dossier in f.parents and f.is_file() and f.suffix.lower() in (".png", ".svg", ".jpg", ".jpeg"):
                a = attributions.get(im, {})
                B.VOCABULAIRE[nid] = entree
                B.EXTERNES[nid] = {"fichier": im, "chemin": f, "base": a.get("source", ""), "licence": a.get("licence", ""),
                                   "attribution": a.get("attribution", ""), "url": "", "auteur": ""}
                entree["image"] = im
                break
    # Toutes les autres images de la base (variantes d'une notion, pictogrammes retenus par étiquette santé, Mulberry,
    # OpenMoji) : chacune devient un pictogramme à part entière, nommé par son premier mot-clé et rangé dans sa catégorie.
    utilisees = {n.get("image") for n in notions.values()}
    for fichier, a in attributions.items():
        if fichier in utilisees:
            continue
        f = (dossier / fichier).resolve()
        if not (dossier in f.parents and f.is_file() and f.suffix.lower() in (".png", ".svg", ".jpg", ".jpeg")):
            continue
        ident = "IMG_" + re.sub(r"[^A-Za-z0-9]+", "_", f"{a.get('source', '')}_{a.get('id', '')}").strip("_").upper()
        libelle_anglais = not [m for m in a.get("mots_fr") or [] if m]     # pas de mot français : libellé anglais en repli
        mots_fr = [m for m in a.get("mots_fr") or [] if m] or [m for m in a.get("mots_en") or [] if m]
        mots_en = [m for m in a.get("mots_en") or [] if m] or mots_fr
        lie = [notions[x] for x in a.get("notions", []) if x in notions]
        fr = lie[0]["fr"] if lie else (mots_fr[0] if mots_fr else ident)
        en = lie[0]["en"] if lie else (mots_en[0] if mots_en else fr)
        code = (a.get("categorie") or "99")[:2]
        entree = {"id": ident, "categorie": CADRE_PAR_CATEGORIE.get(code, "soin"), "categorie_vocabulaire": a.get("categorie") or "99",
                  "fr": fr, "en": en, "ar": (lie[0]["ar"] if lie else "") or fr, "composition": [], "image": fichier,
                  "variante_de": lie[0]["id"] if lie else None, "mots_fr": mots_fr[:6], "mots_en": mots_en[:6],
                  "sensible": "sensible" in (a.get("etiquettes") or []), "popularite": int(a.get("popularite") or 0),
                  "libelle_anglais": libelle_anglais and not lie}
        notions[ident] = entree
        B.VOCABULAIRE[ident] = entree
        B.EXTERNES[ident] = {"fichier": fichier, "chemin": f, "base": a.get("source", ""), "licence": a.get("licence", ""),
                             "attribution": a.get("attribution", ""), "url": "", "auteur": ""}
    return notions


class LexiqueBaseV2(LexiquePictogrammes):
    """Texte ⇄ pictogrammes sur le vocabulaire de consultation de la base (expressions les plus longues d'abord).

    Règles de sûreté identiques au lexique de démonstration : la négation (« pas », « jamais », « sans »…), la limite
    (« jusqu'à », « pas plus de »), les chiffres, les doses et les noms de médicaments ne sont jamais perdus ; un mot sans
    pictogramme disponible est signalé au médecin (non_traduits), jamais remplacé par une image approchante.
    """

    LONGUEUR_MAX = 7
    # Formes conjuguées fréquentes à l'oral : « j'ai mal », « vous avez mal », « ça fait mal » -> DOULEUR (comme le lexique
    # de démonstration, pour que la combinaison « partie du corps + douleur » et les contrôles des agents restent identiques)
    FORMES_ORALES = {("ai", "mal"): "DOULEUR", ("avez", "mal"): "DOULEUR", ("a", "mal"): "DOULEUR", ("fait", "mal"): "DOULEUR",
                     ("as", "mal"): "DOULEUR", ("ont", "mal"): "DOULEUR", ("mal",): "DOULEUR"}
    IMPERATIFS = {"buvez": "boire", "dormez": "dormir", "prenez": "prendre", "mettez": "mettre", "faites": "faire", "dites": "dire",
                  "allez": "aller", "venez": "venir", "revenez": "revenir", "sortez": "sortir", "ouvrez": "ouvrir", "suivez": "suivre",
                  "lisez": "lire", "ecrivez": "ecrire", "attendez": "attendre", "repondez": "repondre", "courez": "courir",
                  "tenez": "tenir", "souriez": "sourire", "choisissez": "choisir", "evitez": "eviter", "reposez": "se reposer"}
    AUXILIAIRES = {"ai", "as", "a", "avez", "avons", "ont", "suis", "es", "est", "sommes", "etes", "sont", "me", "te", "nous", "ca"}
    # Mots qui ne portent pas de sens à illustrer : « je VAIS vous prescrire » (futur proche), « COMME médicament ».
    # Leur donner une image à tout prix dégrade le message (« vais » -> « ça va », « comme » -> un drapeau).
    MOTS_IGNORES = {"vais", "vas", "vont", "allons", "comme", "donc", "alors", "puis", "aussi", "tres", "vraiment", "deja"}
    # Participes et formes irrégulières fréquents -> infinitif (« qu'avez-vous PRIS » = prendre, jamais « bris » = casser)
    IRREGULIERS = {"pris": "prendre", "prise": "prendre", "prises": "prendre", "prends": "prendre", "prend": "prendre",
                   "bu": "boire", "bois": "boire", "boit": "boire", "mis": "mettre", "mise": "mettre", "mets": "mettre",
                   "dormi": "dormir", "dors": "dormir", "dort": "dormir", "vomi": "vomir", "vomis": "vomir", "vomit": "vomir",
                   "mange": "manger", "manges": "manger", "senti": "sentir", "sens": "sentir",
                   "sent": "sentir", "sentez": "sentir", "toussez": "tousser", "tousse": "tousser", "saigne": "saigner",
                   "saignez": "saigner", "respirez": "respirer", "respire": "respirer", "marche": "marcher"}
    # Mots de violence ou d'atteinte à soi : JAMAIS traduits d'office (« pendre » ne doit pas devenir « accrocher », ni
    # « tuer » une image quelconque). Le médecin les voit « sans pictogramme » ; le juriste juge le message.
    MOTS_DANGEREUX = {"pendre", "pends", "pend", "pendez", "pendu", "pendue", "pendaison", "suicide", "suicider", "suicidez",
                      "suicidaire", "tuer", "tue", "tuez", "tuera", "tuerai", "mourir", "meurs", "mourez", "crever", "creve",
                      "crevez", "egorger", "poignarder", "empoisonner", "noyer", "noyez", "etrangler", "buter", "massacrer"}

    def __init__(self, base: Path | None = None, notions: dict | None = None):
        from .bibliotheque import connu
        self.base = base or trouver_base()
        self.notions = notions if notions is not None else (charger_pictogrammes(self.base) if self.base else {})
        self._connu = connu
        self.formes: dict[tuple, str] = {}
        voc = RACINE / "kb" / "corpus" / "vocabulaire_consultation.json"
        entrees = []
        if voc.exists():
            for c in json.loads(voc.read_text(encoding="utf-8"))["categories"].values():
                entrees += c["notions"]
        for e in entrees:
            fr, _, formes, _, _ = _analyser(e)
            nid = _ident(fr)
            if nid not in self.notions:
                continue
            for forme in formes:
                cle = tuple(self._mots(forme))
                if cle and cle not in self.formes:
                    self.formes[cle] = nid
        for nid, n in self.notions.items():             # libellé français de la base (notions historiques comprises)
            if nid.startswith("IMG_"):                  # images du catalogue : règles plus strictes, plus bas
                continue
            cle = tuple(self._mots(n["fr"]))
            if cle:
                self.formes.setdefault(cle, nid)
        for cle in [c for c in self.formes if len(c) == 1 and (c[0] in MOTS_OUTILS or c[0] in self.AUXILIAIRES)]:
            del self.formes[cle]                        # « là » (= « la » sans accent) ne doit pas capter l'article « la »
        # Mots-clés FRANÇAIS des autres images (catalogue complet compris) : utilisés seulement quand aucune notion du
        # vocabulaire de consultation ne correspond (« voiture », « école ») ; jamais un contenu sensible ; jamais un
        # mot-clé anglais (« car » est aussi un mot français) ; à mot égal, l'image la plus utilisée l'emporte.
        # Prudence (retour d'usage : « pendre » -> « accrocher », « comme » -> un drapeau, « male » -> « mâle ») :
        #  - seul le LIBELLÉ PRINCIPAL de l'image compte, jamais ses mots-clés secondaires (« pendre » est un mot-clé
        #    secondaire de l'image « accrocher ») ;
        #  - seulement les images ARASAAC, dont les libellés français sont écrits par des orthophonistes ; les libellés
        #    français de Mulberry et d'OpenMoji sont déduits de l'anglais (« as » -> « comme ») : recherche manuelle seulement ;
        #  - l'accent doit correspondre exactement (« male » n'est pas « mâle ») : voir self._accents.
        self._accents: dict[tuple, str] = {}
        generales = sorted((n for n in self.notions.values() if n["id"].startswith("IMG_ARASAAC_") and not n.get("sensible")
                            and not n.get("libelle_anglais") and not n.get("variante_de") and self._disponible(n["id"])
                            and not str(n.get("categorie_vocabulaire", "")).startswith(("91", "98"))),
                           key=lambda n: -n.get("popularite", 0))
        for n in generales:
            m = n["fr"]
            cle = tuple(self._mots(m))
            existante = self.formes.get(cle)
            if cle and len(cle) <= 4 and (existante is None or not self._disponible(existante)) \
                    and not (len(cle) == 1 and (cle[0] in MOTS_OUTILS or cle[0] in self.AUXILIAIRES or len(cle[0]) < 3)) \
                    and not any(w in MEDICAMENTS or w in self.MOTS_DANGEREUX or w in self.MOTS_IGNORES for w in cle) \
                    and not (existante and existante.startswith("IMG_")):
                self.formes[cle] = n["id"]      # aussi quand la notion du vocabulaire n'a pas d'image dans cette base
                self._accents[cle] = " ".join(self._mots_accents(m))
        for cle, nid in self.FORMES_ORALES.items():
            if nid in self.notions or self._connu(nid):
                self.formes[cle] = nid
        self.alias: dict[str, list[tuple]] = defaultdict(list)      # toutes les façons de dire chaque notion
        for cle, nid in self.formes.items():
            self.alias[nid].append(cle)
        self._recherche = None
        self.langue_saisie = "fr"        # « en » : le médecin écrit en anglais (voir _traduire_en)
        self._formes_en = None
        self.rapprochement = True        # rapprochement automatique et sûr des mots inconnus (voir _rapprocher)

    @property
    def recherche(self) -> "RecherchePictogrammes":
        if self._recherche is None:
            self._recherche = RecherchePictogrammes(self)
        return self._recherche

    def chercher(self, requete: str, k: int = 12) -> list[dict]:
        return self.recherche.chercher(requete, k)

    def suggerer(self, mots: list[str], k: int = 3) -> dict[str, list[str]]:
        """Pour chaque mot sans pictogramme : les pictogrammes les plus proches (mots-clés, écriture, sens), proposés au
        médecin. Jamais insérés d'office."""
        sortie = {}
        for m in mots:
            m = re.sub(r"\s*\(en partie\)$", "", m)
            if len(m) < 3 or _norm(m) in MOTS_OUTILS:
                continue
            res = [r["id"] for r in self.recherche.chercher(m, k * 2) if any(v for kk, v in r["pourquoi"].items() if kk != "cosinus")]
            if res:
                sortie[m] = res[:k]
        return sortie

    @staticmethod
    def _mots_accents(texte: str) -> list[str]:
        """Comme _mots, mais en gardant les accents (« mâle » ≠ « male »)."""
        t = (texte or "").lower().replace("’", "'")
        return [re.sub(r"^(d|l|qu|j|s|n|c|m|t)'", "", m) for m in re.findall(r"[\w']+|\?", t) if m]

    @staticmethod
    def _mots(texte: str) -> list[str]:
        t = _norm(texte.replace("’", "'"))
        return [re.sub(r"^(d|l|qu|j|s|n|c|m|t)'", "", m) for m in re.findall(r"[\w']+|\?", t) if m]

    def _deplier(self, nid: str, profondeur: int = 0) -> list[str]:
        n = self.notions.get(nid)
        if n and n["composition"] and profondeur < 3:
            return [x for c in n["composition"] for x in self._deplier(c, profondeur + 1)]
        return [nid]

    def _disponible(self, nid: str) -> bool:
        return self._connu(nid)

    # Catégories où un rapprochement automatique est sans risque d'inverser le sens (corps, douleur, sensations,
    # symptômes, ressenti, mots de la conversation). Jamais : médicaments, doses, temps, quantités, négation.
    CATEGORIES_RAPPROCHABLES = ("03", "04", "05", "06", "07", "08", "09", "11", "12", "14")

    def _rapprocher(self, mot: str) -> str | None:
        """Mot inconnu -> une notion, en arrière-plan, seulement quand c'est SÛR : forme conjuguée (« sentez » -> sentir)
        ou faute de frappe évidente sur un mot long (« doulleur » -> douleur). JAMAIS par le sens seul, ni par une
        ressemblance sur un mot court : un mot français valide ressemble souvent à un autre qui n'a rien à voir
        (« pris » / « bris » -> casser, « vais » -> « ça va »). Mieux vaut un mot « sans pictogramme », que le médecin
        voit et corrige, qu'une image fausse. Le rapprochement est noté sur la proposition : le médecin le voit."""
        m = _norm(mot)
        if len(m) < 4 or m.isdigit() or m in MOTS_OUTILS or m in MEDICAMENTS or re.search(r"\d", m) \
                or m in self.MOTS_DANGEREUX or m in self.MOTS_IGNORES or m in self.AUXILIAIRES:
            return None
        if m in self.IRREGULIERS:
            nid = self.formes.get(tuple(self._mots(self.IRREGULIERS[m])))
            return nid if nid and self._disponible(nid) else None
        for cand in ([m[:-2] + "er", m[:-2] + "ir", m[:-2] + "re", m[:-1] + "r"] if m.endswith(("ez", "es")) else []) + \
                ([m[:-3] + "er"] if m.endswith("ons") else []) + ([m[:-1] + "r"] if m.endswith("e") else []):
            nid = self.formes.get(tuple(self._mots(cand)))
            if nid and self._disponible(nid):
                return nid
        if len(m) < 6:                       # faute de frappe : seulement sur un mot assez long pour être sans ambiguïté
            return None
        try:
            res = self.recherche.chercher(mot, 5)
        except Exception:  # noqa: BLE001
            return None
        for r in res:
            n = self.notions.get(r["id"], {})
            if not str(n.get("categorie_vocabulaire", "")).startswith(self.CATEGORIES_RAPPROCHABLES):
                continue
            for forme in self.alias.get(r["id"], []):
                if len(forme) == 1 and forme[0][:2] == m[:2] and len(forme[0]) >= 5 \
                        and RecherchePictogrammes._distance(m, forme[0], 1) <= 1:
                    return r["id"]
        return None

    @staticmethod
    def _inversions(texte: str) -> str:
        """Questions à inversion : « avez-vous mal ? » -> « vous avez mal ? », « comment vous sentez-vous » -> « comment
        vous sentez ». Un seul pictogramme VOUS par question, au lieu de « vous vous vous » ; la forme orale
        « avez mal » reste reconnue (DOULEUR)."""
        motif = re.compile(r"\b(\w+)-(?:t-)?(vous|tu)\b", flags=re.IGNORECASE)
        phrases = re.split(r"(?<=[?.!])", texte)
        sortie = []
        for ph in phrases:
            if not motif.search(ph):
                sortie.append(ph)
                continue
            deja = re.search(r"(?<![-\w])(vous|tu)\b(?!-)", motif.sub("", ph), flags=re.IGNORECASE)
            premier = [True]

            def remplacer(m):
                if premier[0] and not deja:
                    premier[0] = False
                    return f"{m.group(2)} {m.group(1)}"
                return m.group(1)
            sortie.append(motif.sub(remplacer, ph))
        return "".join(sortie)

    def _choix_ou(self) -> str | None:
        """Image du « ou » de choix, si la base en a une (libellé exact « ou », sans accent), jamais celle du lieu."""
        if not hasattr(self, "_ou_choix"):
            self._ou_choix = next((n["id"] for n in self.notions.values() if n.get("fr", "").strip().lower() == "ou"
                                   and n["id"] != "OU" and self._disponible(n["id"])), None)
        return self._ou_choix

    def _mot_connu(self, m: str, brut: str) -> bool:
        if m in MOTS or m in MOTS_OUTILS or m in self.AUXILIAIRES or m in self.MOTS_IGNORES or m in self.IRREGULIERS \
                or m in MEDICAMENTS or m in self.MOTS_DANGEREUX or m.isdigit() or m == "?":
            return True
        cle = (m,)
        if cle in self.formes:
            return not (cle in self._accents and " ".join(self._mots_accents(brut)) != self._accents[cle])
        return any(c[0] == m for c in self.formes if len(c) > 1)      # début d'une expression (« pas plus de »)

    def _corriger(self, m: str, brut: str) -> str | None:
        """Faute de frappe ou de dictée sur un mot inconnu -> forme connue, seulement quand c'est sûr :
        clavier QWERTY d'un habitué de l'AZERTY (« sentew » -> sentez), e final en trop (« male » -> mal),
        nom de médicament mal écrit (« tramadole », « paracetamole », « ibuprophene »)."""
        if len(m) < 3 or self._mot_connu(m, brut) or re.search(r"\d", m):
            return None
        from .lecture import trouver_medicaments, variantes
        if "w" in m or re.search(r"q(?!u)", m):
            for v in variantes(m):
                if ("w" not in v and not re.search(r"q(?!u)", v)) and self._mot_connu(v, v):
                    return v
        if m.endswith("e") and m[:-1] in MOTS:
            return m[:-1]
        if len(m) >= 6:
            lus = trouver_medicaments(m, {n: {} for n in MEDICAMENTS})
            if len(lus) == 1 and lus[0]["nom"] in MEDICAMENTS:
                return lus[0]["nom"]
        if len(m) >= 7:                    # faute sur un mot long : même prononciation, ou une lettre près, sans ambiguïté
            from .lecture import cle_phonetique, distance
            idx = self._index_fautes()
            cands = set(idx["cles"].get(cle_phonetique(m), set()))
            if len(cands) != 1:
                cands = {w for w in idx["par_debut"].get(m[:2], ()) if abs(len(w) - len(m)) <= 1 and distance(m, w, 1) <= 1}
            cands = {w for w in cands if not (m.endswith(("er", "ir", "re")) and m.startswith(w[:-1]))}   # « droguer » n'est pas « drogue »
            if len(cands) == 1:
                return next(iter(cands))
        return None

    def _index_fautes(self) -> dict:
        """Mots connus d'au moins 6 lettres (formes d'une seule notion) : clé de prononciation et deux premières lettres."""
        if getattr(self, "_idx_fautes", None) is None:
            from .lecture import cle_phonetique
            cles, debut = {}, {}
            for c in self.formes:
                if len(c) == 1 and len(c[0]) >= 6 and c not in self._accents:
                    cles.setdefault(cle_phonetique(c[0]), set()).add(c[0])
                    debut.setdefault(c[0][:2], set()).add(c[0])
            self._idx_fautes = {"cles": cles, "par_debut": debut}
        return self._idx_fautes

    PREFIXES_COLLES = ("en", "au", "aux", "du", "de", "des", "le", "la", "les", "un", "une", "et", "a", "ma", "mon", "mes",
                       "ta", "ton", "sa", "son", "ce", "par", "pour", "sur", "dans", "avec", "sans", "chez", "tres", "pas",
                       "plus", "trop", "votre", "vos", "mal", "bien")

    def _decoller(self, texte: str) -> tuple[str, dict]:
        """Mots collés par erreur de frappe ou de dictée : « enpharmacie » -> « en pharmacie », « malau ventre » ->
        « mal au ventre ». Seulement si le mot entier est inconnu et que ses deux morceaux sont connus."""
        corrections = {}

        def separer(mt):
            w = mt.group(0)
            if mt.end() < len(mt.string) and mt.string[mt.end()] in "'’":
                return w                          # élision (« jusqu'à », « qu'avez ») : pas un mot collé
            n = _norm(w)
            if len(n) < 5 or self._mot_connu(n, w) or n in MEDICAMENTS:
                return w
            for k in range(min(len(n) - 2, 8), 1, -1):
                a, b = n[:k], n[k:]
                connu_a, connu_b = len(a) >= 3 and self._mot_connu(a, a), len(b) >= 3 and self._mot_connu(b, b)
                outil_b = b in self.PREFIXES_COLLES or b in MOTS_OUTILS
                if (a in self.PREFIXES_COLLES and connu_b and not outil_b) or (connu_a and outil_b and a not in MOTS_OUTILS) \
                        or (len(a) >= 4 and len(b) >= 4 and connu_a and connu_b):
                    corrections[w] = f"{a} {b}"
                    return f"{w[:k]} {w[k:]}"
            return w
        return re.sub(r"[A-Za-zÀ-ÿ]+", separer, texte), corrections

    MOTS_EN = {"not": "NE_PAS", "no": "NE_PAS", "don't": "NE_PAS", "dont": "NE_PAS", "never": "NE_PAS", "stop": "STOP",
               "emergency": "URGENCE", "maximum": "MAXIMUM", "max": "MAXIMUM", "you": "VOUS", "your": "VOUS", "i": "MOI", "me": "MOI",
               "my": "MOI", "yes": "OUI", "pain": "DOULEUR", "hurt": "DOULEUR", "hurts": "DOULEUR", "ache": "DOULEUR"}
    VIDES_EN = {"the", "a", "an", "of", "to", "is", "are", "am", "do", "does", "did", "be", "it", "this", "that", "and", "or",
                "in", "on", "at", "for", "with", "have", "has", "had", "will", "would", "please", "some", "any"}
    MEDICAMENTS_EN = {"acetaminophen": "paracetamol", "paracetamol": "paracetamol", "tylenol": "paracetamol", "ibuprofen": "ibuprofene",
                      "advil": "ibuprofene", "aspirin": "aspirine", "amoxicillin": "amoxicilline", "metformin": "metformine",
                      "tramadol": "tramadol", "misoprostol": "misoprostol"}

    def _traduire_en(self, texte: str) -> dict:
        """Le médecin écrit en ANGLAIS : libellés anglais des notions et des images ARASAAC (plus longue expression
        d'abord), mêmes règles de sûreté (négation, chiffres, doses, médicaments jamais perdus)."""
        if self._formes_en is None:
            self._formes_en = {}
            for nid, n in self.notions.items():
                if not n.get("en") or not self._disponible(nid) or n.get("sensible") \
                        or str(n.get("categorie_vocabulaire", "")).startswith(("91", "98")):
                    continue
                if nid.startswith("IMG_") and not nid.startswith("IMG_ARASAAC_"):
                    continue
                cle = tuple(re.findall(r"[a-z0-9']+", n["en"].lower()))
                if cle and not (nid.startswith("IMG_") and cle in self._formes_en):
                    self._formes_en.setdefault(cle, nid)
        jetons = re.findall(r"[a-z0-9']+|\?", (texte or "").lower().replace("’", "'"))
        pictos, manquants, i = [], [], 0
        while i < len(jetons):
            m = jetons[i]
            if m == "?":
                pictos.append("QUESTION"); i += 1; continue
            if m.isdigit():
                pictos.append(f"CHIFFRE:{m}"); i += 1; continue
            if re.fullmatch(r"\d+(?:[.,]\d+)?(mg|g|ml|ui)", m):
                pictos.append(f"DOSE:{m}"); i += 1; continue
            if m in self.MEDICAMENTS_EN:
                pictos.append(f"MEDICAMENT:{self.MEDICAMENTS_EN[m]}"); i += 1; continue
            if m in self.MOTS_EN and self._disponible(self.MOTS_EN[m]) and self.MOTS_EN[m] in ("NE_PAS", "STOP", "URGENCE", "MAXIMUM"):
                pictos.append(self.MOTS_EN[m]); i += 1; continue
            trouve = None
            for L in range(min(5, len(jetons) - i), 0, -1):
                nid = self._formes_en.get(tuple(jetons[i:i + L]))
                if nid:
                    trouve = (nid, L)
                    break
            if trouve:
                pictos.append(trouve[0]); i += trouve[1]; continue
            if m in self.MOTS_EN and self._disponible(self.MOTS_EN[m]):
                pictos.append(self.MOTS_EN[m])
            elif m not in self.VIDES_EN:
                manquants.append(m)
            i += 1
        pictos = [p for k, p in enumerate(pictos) if k == 0 or p != pictos[k - 1] or p.startswith("CHIFFRE:")]
        pictos = combiner_pictogrammes(pictos, self.notions)
        compte = len(pictos) + len(manquants)
        return {"pictogrammes": pictos, "non_traduits": manquants, "rapproches": {}, "corrections": {},
                "couverture": round(len(pictos) / compte, 2) if compte else 0.0}

    def traduire(self, texte: str) -> dict:
        if self.langue_saisie == "en":
            return self._traduire_en(texte)
        texte = self._inversions(texte)
        texte, colles = self._decoller(texte)
        # Doses et rythmes écrits vite : « 1kg », « 7fois parjours », « 3x/j » -> « 1kg », « 7 fois par jour »
        texte = re.sub(r"(\d+(?:[.,]\d+)?)\s*(mg|g|kg|ml|l|mcg|µg|ui)\b", r"\1\2", texte, flags=re.IGNORECASE)
        texte = re.sub(r"(\d)\s*(?:fois|x)\b", r"\1 fois", texte, flags=re.IGNORECASE)
        texte = re.sub(r"\bpar\s*jours?\b|/\s*j(?:our)?\b", " par jour", texte, flags=re.IGNORECASE)
        bruts = re.findall(r"[\w'’]+|\?", texte)
        mots = [re.sub(r"^(d|l|qu|j|s|n|c|m|t)'", "", _norm(b).replace("’", "'")) for b in bruts]
        corrections = dict(colles)
        for k, (m, b) in enumerate(zip(mots, bruts)):        # fautes de frappe et de dictée, corrigées et montrées
            c = self._corriger(m, b)
            if c:
                mots[k] = c
                corrections[b] = c
        pictos, manquants, rapproches, i = [], [], {}, 0
        while i < len(mots):
            m, brut = mots[i], bruts[i]
            if re.match(r"^j['’]", _norm(brut)) and self._disponible("MOI"):     # « j'ai », « j'avais » : le patient parle de lui
                pictos.append("MOI")
            if _norm(brut).replace("’", "'").startswith("jusqu"):
                pictos.append("MAXIMUM"); i += 1; continue
            if m == "?":
                pictos.append("QUESTION"); i += 1; continue
            if m.isdigit():
                pictos.append(f"CHIFFRE:{m}"); i += 1; continue
            if re.fullmatch(r"\d+(?:[.,]\d+)?(mg|g|kg|ml|l|mcg|µg|ui)", m):
                pictos.append(f"DOSE:{m}"); i += 1; continue
            if m in MEDICAMENTS:
                pictos.append(f"MEDICAMENT:{m}"); i += 1; continue
            if MOTS.get(m) in ("NE_PAS", "MAXIMUM", "STOP", "URGENCE"):   # mots de sûreté : jamais absorbés par une expression
                pictos.append(MOTS[m]); i += 1; continue
            # « où » (lieu) n'est pas « ou » (choix) : sans accent, on le reconnaît en tête de question. Perdre « où » change
            # la question (« où avez-vous mal ? » devenait « vous douleur ? »).
            # « où » (accent) ou « ou » en tête de question suivi d'un verbe (« ou avez-vous mal ? ») = le LIEU ;
            # sinon c'est le CHOIX (« la tête ou le ventre ? »), illustré si la base a une image « ou » (choix)
            verbe_suit = i + 1 < len(mots) and (mots[i + 1] in self.AUXILIAIRES or mots[i + 1] in ("vous", "tu", "est", "sont", "etes",
                                                                                                   "avez", "as", "habitez", "allez", "travaillez"))
            if m == "ou" and not (brut.lower().replace("ù", "u") != brut.lower() or (i == 0 and verbe_suit)):
                choix = self._choix_ou()
                if choix:
                    pictos.append(choix)
                i += 1; continue
            if m == "ou" and (brut.lower().replace("ù", "u") != brut.lower() or ("?" in texte and (i == 0 or mots[i - 1] in ("?", ".")))):
                if self._disponible("OU"):
                    pictos.append("OU")
                else:
                    manquants.append(brut)        # jamais perdu en silence : le médecin le voit « sans pictogramme »
                i += 1; continue
            if m in self.MOTS_DANGEREUX:          # jamais d'image d'office : le médecin et le juriste voient le mot tel quel
                manquants.append(brut); i += 1; continue
            if m in self.MOTS_IGNORES:
                i += 1; continue
            trouve = None
            for L in range(min(self.LONGUEUR_MAX, len(mots) - i), 0, -1):
                cle = tuple(mots[i:i + L])
                nid = self.formes.get(cle)
                if nid and cle in self._accents and " ".join(self._mots_accents(" ".join(bruts[i:i + L]))) != self._accents[cle]:
                    nid = None                    # image du catalogue général : l'accent doit correspondre (« male » ≠ « mâle »)
                if nid is None and L == 1 and len(m) > 3 and m[-1] in "sx":
                    nid = self.formes.get((m[:-1],))
                if nid is None and L == 1 and m.endswith("ez") and len(m) > 4:    # impératif : « mangez » -> manger
                    nid = self.formes.get(tuple(self._mots(self.IMPERATIFS.get(m, m[:-2] + "er"))))
                if nid:
                    trouve = (nid, L)
                    break
            if trouve:
                nid, L = trouve
                elements = self._deplier(nid)
                ok = [e for e in elements if self._disponible(e)]
                if ok:
                    pictos.extend(ok)
                    if len(ok) < len(elements):
                        manquants.append(" ".join(bruts[i:i + L]) + " (en partie)")
                else:
                    manquants.append(" ".join(bruts[i:i + L]))
                i += L
                continue
            if m in MOTS and MOTS[m] and self._disponible(MOTS[m]):
                pictos.append(MOTS[m])
            elif m in MOTS or m in MOTS_OUTILS or m in self.AUXILIAIRES:
                pass
            elif self.rapprochement and (proche := self._rapprocher(brut)):
                pictos.append(proche)
                rapproches[brut] = proche
            else:
                manquants.append(brut)
            i += 1
        j = 0
        while j < len(pictos) - 1:                      # « pas plus de 4 » = au maximum 4
            if pictos[j] == "NE_PAS" and pictos[j + 1] == "PLUS":
                pictos[j:j + 2] = ["MAXIMUM"]
            j += 1
        dedoublonne = [p for k, p in enumerate(pictos) if k == 0 or p != pictos[k - 1] or p.startswith("CHIFFRE:")]
        pictos = combiner_pictogrammes(dedoublonne, self.notions)
        compte = len(pictos) + len(manquants)
        return {"pictogrammes": pictos, "non_traduits": manquants, "rapproches": rapproches, "corrections": corrections,
                "couverture": round(len(pictos) / compte, 2) if compte else 0.0}

    def interpreter(self, pictogrammes: list[str]) -> str:
        from .bibliotheque import libelle
        return " ".join(("(" + " + ".join(libelle(x) for x in p.split("+")) + ")") if "+" in p else libelle(p) for p in pictogrammes)


# Palette du patient : TOUTES les notions illustrées, rangées en onglets (l'ordre est celui de l'écran). Une notion composée
# (« douleur qui va et vient ») n'a pas d'onglet : le patient l'exprime en enchaînant ses pictogrammes.
ONGLETS_PATIENT = {
    "reponses": ("02", "01"), "questions": ("03",), "corps": ("09",), "localisation": ("10",), "douleur": ("11",),
    "intensite": ("27I",), "sensations": ("28",), "symptomes": ("12",), "ressenti": ("14",), "maladies": ("13",),
    "soins": ("15", "16", "17", "18"), "alimentation": ("20",), "hygiene": ("21", "22"), "grossesse": ("23",),
    "handicap": ("24",), "personnes": ("08",), "vie quotidienne": ("25", "19"), "temps": ("26",), "nombres": ("27",),
    "urgence": ("29",), "droits": ("30", "04", "05", "06", "07"), "autres": ("99",),
    "general": ("90",), "symboles": ("91",),        # tout le catalogue (--tous-pictos) ; « 98 » (sensible) : recherche seulement
}
INTENSITE = ["PAS_DE_DOULEUR", "UN_PEU", "PEU", "LEGER", "MODERE", "FORT", "SEVERE", "BEAUCOUP", "TROP", "FAIBLE", "PLUS", "MOINS",
             "MIEUX", "PIRE", "PAREIL", "DE_PLUS_EN_PLUS_FORT", "DE_MOINS_EN_MOINS_FORT"]


def palette_patient(notions: dict, par_onglet: int = 50000) -> dict:
    from .bibliotheque import connu
    sortie = {}
    for onglet, codes in ONGLETS_PATIENT.items():
        if onglet == "intensite":
            ids = [f"CHIFFRE:{i}" for i in range(11)] + [i for i in INTENSITE if i in notions and connu(i)]
        else:
            ids = [nid for nid, n in notions.items() if n["categorie_vocabulaire"][:2] in codes and not n["composition"]
                   and connu(nid) and not (onglet == "nombres" and nid in INTENSITE) and not n.get("sensible")]
            if onglet in ("general", "symboles"):     # les plus utilisés d'abord
                ids.sort(key=lambda i: -notions[i].get("popularite", 0))
        if ids:
            sortie[onglet] = ids[:par_onglet]
    return sortie


# Images combinées (un grand pictogramme + 1 ou 2 médaillons) : « mal à la tête » = TÊTE + DOULEUR, « brûlure au ventre à
# gauche » = VENTRE + BRÛLURE + GAUCHE, « paracétamol 500 mg » = MÉDICAMENT + DOSE. La négation, la limite, l'urgence et STOP
# ne sont jamais combinées (contrôle de la bibliothèque) : elles restent des pictogrammes entiers.
SENSATIONS_LOCALES = {"DOULEUR", "AVOIR_MAL", "SANG", "GONFLEMENT", "SAIGNEMENT", "ERUPTION", "BOUTONS", "PLAIE", "COUPURE",
                      "BRULURE_DE_LA_PEAU", "HEMATOME", "BOSSE", "FRACTURE", "ENTORSE", "MORSURE", "PIQURE_D_INSECTE",
                      "ENGOURDISSEMENT", "PARALYSIE", "TREMBLEMENT", "GONFLE", "CLOQUE", "CROUTE", "TACHE", "PUS"}
COTES = {"GAUCHE", "DROITE", "LES_DEUX_COTES", "HAUT", "BAS", "DEVANT", "DERRIERE", "DEDANS", "A_LA_SURFACE", "EN_PROFONDEUR"}


def combiner_pictogrammes(pictos: list[str], notions: dict) -> list[str]:
    from .bibliotheque import combinaison_valide
    from .pictogrammes import PARTIES_DU_CORPS
    corps = {n for n, x in notions.items() if x.get("categorie_vocabulaire", "")[:2] == "09"} | PARTIES_DU_CORPS
    sensations = SENSATIONS_LOCALES | {n for n, x in notions.items()
                                       if x.get("categorie_vocabulaire", "")[:2] == "11" and not x.get("composition")}
    sortie, i = [], 0
    while i < len(pictos):
        a = pictos[i]
        b = pictos[i + 1] if i + 1 < len(pictos) else None
        c = pictos[i + 2] if i + 2 < len(pictos) else None
        groupe = None
        if b and a in corps and b in sensations:
            groupe = [a, b]
        elif b and a in sensations and b in corps:
            groupe = [b, a]                               # « douleur au ventre » : la partie du corps en grand
        elif b and a in corps and b in COTES:
            groupe = [a, b]
        elif b and a.startswith("MEDICAMENT:") and b.startswith("DOSE:"):
            groupe = [a, b]
        if groupe:
            n = 2
            if c and c in COTES and len(groupe) == 2 and groupe[1] not in COTES and combinaison_valide("+".join(groupe + [c])):
                groupe, n = groupe + [c], 3
            ident = "+".join(groupe)
            if combinaison_valide(ident):
                sortie.append(ident)
                i += n
                continue
        sortie.append(a)
        i += 1
    return sortie


# ------------------------------------------------------------------------------------------------ textes officiels
MOTS_VIDES_AR = {"ما", "هي", "هو", "من", "في", "على", "عن", "إلى", "الى", "كيف", "يتم", "يمكن", "و", "أو", "او", "مع", "هل", "ذلك", "هذا", "هذه"}


def _normaliser_arabe(m: str) -> str:
    m = re.sub(r"[\u064B-\u0652\u0640]", "", m)                    # voyelles brèves, tatweel
    m = re.sub(r"[إأآ]", "ا", m).replace("ة", "ه").replace("ى", "ي")
    return m[2:] if m.startswith("ال") and len(m) > 4 else m          # article « al- »


class Corpus:
    """Recherche BM25 (index inversé, sans dépendance) dans les morceaux de la base : articles des textes officiels
    (01_base_juridique/corpus_rag.jsonl) et sections des fiches de l'OMS (03_references_medicales/oms_fiches.jsonl)."""

    def __init__(self, base: Path, pays: str | None = None, k1: float = 1.4, b: float = 0.75):
        self.base, self.k1, self.b = base, k1, b
        self.morceaux: list[dict] = []
        f = base / "01_base_juridique" / "corpus_rag.jsonl"
        if f.exists():
            for ligne in f.read_text(encoding="utf-8").splitlines():
                if ligne.strip():
                    x = json.loads(ligne)
                    md = x["metadata"]
                    juridiction = md.get("juridiction", "")
                    if pays == "CM" and juridiction.startswith("D_"):
                        continue
                    if pays == "AE" and juridiction.startswith("A_"):
                        continue
                    self.morceaux.append({"id": x["id"], "type": "texte_officiel", "texte": x["text"], "source": md.get("source"),
                                          "titre": md.get("titre", ""), "article": md.get("article", ""), "juridiction": juridiction,
                                          "url": md.get("url", ""), "verification": md.get("verification", ""), "sha256": md.get("sha256", "")})
        f = base / "03_references_medicales" / "oms_fiches.jsonl"
        if f.exists():
            for ligne in f.read_text(encoding="utf-8").splitlines():
                if ligne.strip():
                    x = json.loads(ligne)
                    self.morceaux.append({"id": x["id"], "type": "reference_medicale", "texte": x["texte"], "source": f"OMS:{x['fiche']}",
                                          "titre": x.get("titre", ""), "article": x.get("section", ""), "juridiction": "OMS",
                                          "url": x.get("url", ""), "verification": "page officielle de l'OMS", "langue": x.get("langue"),
                                          "sha256": x.get("sha256", "")})
        self._indexer()

    @staticmethod
    def _jetons(texte: str, traduire: bool = True) -> list[str]:
        """Jetons latins (comme la base interne) + jetons arabes (lettres arabes, sans voyelles brèves ni tatweel)."""
        arabes = [_normaliser_arabe(m) for m in re.findall(r"[\u0621-\u064A\u0660-\u0669\u064B-\u0652\u0640]+", texte)]
        return jetons(texte, traduire=traduire) + [m for m in arabes if len(m) > 1 and m not in MOTS_VIDES_AR]

    def _indexer(self):
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.longueurs = []
        for i, m in enumerate(self.morceaux):
            # le titre (maladie, loi) et l'article ou la section comptent double : ce sont eux que vise une question
            c = Counter(self._jetons(f"{m['titre']} {m['titre']} {m['article']} {m['article']} {m['texte']}", traduire=False))
            self.longueurs.append(sum(c.values()))
            for t, n in c.items():
                self.postings[t].append((i, n))
        self.moyenne = sum(self.longueurs) / max(1, len(self.longueurs))
        N = len(self.morceaux)
        self.idf = {t: math.log(1 + (N - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def __len__(self):
        return len(self.morceaux)

    COLLECTIONS = {"texte_officiel": "juridique", "reference_medicale": "oms"}
    _vect = None

    def elements_a_vectoriser(self) -> dict[str, list[tuple[str, str]]]:
        """Textes à encoder, par collection. Chaque morceau est précédé de son contexte (titre du texte, article ou
        section) : un article isolé (« Article 13 : … ») est ainsi rattaché à sa loi, ce qui améliore la recherche."""
        sortie: dict[str, list] = {c: [] for c in self.COLLECTIONS.values()}
        for m in self.morceaux:
            tete = f"{m['titre']} — {m['article']}" if m["article"] else m["titre"]
            sortie[self.COLLECTIONS[m["type"]]].append((m["id"], f"{tete}\n{m['texte']}"))
        return sortie

    def brancher_vecteurs(self, dossier: Path, enc) -> dict:
        """Active la recherche hybride (mots + sens). Renvoie le nombre de vecteurs chargés par collection."""
        from .vecteurs import MatriceVecteurs
        matrices, bilan = [], {}
        for c in self.COLLECTIONS.values():
            m = MatriceVecteurs.charger(dossier, c, enc.nom)
            if m is not None:
                matrices.append(m)
                bilan[c] = len(m.ids)
        self._vect = (enc, matrices) if matrices else None
        return bilan

    def _bm25(self, question: str) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for t in set(self._jetons(question)):
            for i, tf in self.postings.get(t, ()):
                scores[i] += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.longueurs[i] / self.moyenne))
        return sorted(scores.items(), key=lambda x: -x[1])

    def chercher(self, question: str, k: int = 5, type_: str | None = None, methode: str | None = None) -> list[dict]:
        """methode : « bm25 », « vecteurs » ou « hybride » (défaut : hybride si des vecteurs sont branchés).
        Hybride : les 30 meilleurs par mots-clés (BM25) et les 30 meilleurs par le sens (cosinus) sont fusionnés par
        rangs réciproques (RRF). Chaque résultat dit POURQUOI il est là (rang par mots, rang et cosinus par le sens)."""
        from .vecteurs import encoder_requete, fusion_rangs
        methode = methode or ("hybride" if self._vect else "bm25")
        if not hasattr(self, "_rang_id"):
            self._rang_id = {m["id"]: i for i, m in enumerate(self.morceaux)}
        garde = lambda i: not type_ or self.morceaux[i]["type"] == type_  # noqa: E731
        bm = [(i, s) for i, s in self._bm25(question) if garde(i)][:30]
        vect: list[tuple[int, float]] = []
        if methode != "bm25" and self._vect:
            enc, matrices = self._vect
            q = encoder_requete(enc, question)
            autorises = {m["id"] for m in self.morceaux if not type_ or m["type"] == type_}
            for mat in matrices:
                vect += [(self._rang_id[i], c) for i, c in mat.chercher(q, 30, autorises) if i in self._rang_id]
            vect.sort(key=lambda x: -x[1])
            vect = vect[:30]
        if methode == "vecteurs":
            classement = [(i, c) for i, c in vect]
        elif methode == "hybride" and vect:
            classement = [(i, s) for i, s in fusion_rangs([i for i, _ in bm], [i for i, _ in vect])]
        else:
            classement = bm
        rang_bm = {i: r for r, (i, _) in enumerate(bm, 1)}
        cos = {i: c for i, c in vect}
        rang_v = {i: r for r, (i, _) in enumerate(vect, 1)}
        sortie = []
        for i, s in classement[:k]:
            m = self.morceaux[i]
            sortie.append({"extrait": m["id"], "score": round(s, 4), "type": m["type"], "source": m["source"], "titre": m["titre"],
                           "article": m["article"], "texte": m["texte"][:700], "lien": m["url"], "verification": m["verification"],
                           "citation": f"{m['titre']}, {m['article']}" if m["article"] else m["titre"],
                           "pourquoi": {"methode": methode if vect or methode == "bm25" else "bm25", "rang_mots": rang_bm.get(i),
                                        "rang_sens": rang_v.get(i), "cosinus": cos.get(i)}})
        return sortie


class RecherchePictogrammes:
    """Trouver un pictogramme par ce qu'on veut dire, pas seulement par son nom exact : « essoufflement »,
    « j'ai la tête qui tourne », « souffle court ». Trois signaux, fusionnés par rangs réciproques (RRF) :

    1. mots-clés (BM25) sur le libellé français, anglais, arabe, les synonymes du vocabulaire, les mots-clés ARASAAC
       et le titre de la catégorie (« Symptômes ») ;
    2. ressemblance d'écriture (n-grammes de caractères) : fautes de frappe, pluriels, « essouflement » ;
    3. le sens (vecteurs d'un modèle d'encodage local), si la base a été vectorisée (outils/vectoriser_base.py).

    Sûreté : ces résultats sont des PROPOSITIONS (au médecin, au patient, à l'agent traducteur) ; la traduction
    automatique ne remplace jamais un mot par une image approchante sans qu'un humain la choisisse."""

    def __init__(self, lexique: "LexiqueBaseV2"):
        from .vecteurs import EncodeurHachage
        self.lexique, self._vect, self._ecriture, self.seuil_sens = lexique, None, EncodeurHachage(512), 0.5
        titres = {}
        voc = RACINE / "kb" / "corpus" / "vocabulaire_consultation.json"
        if voc.exists():
            titres = {k: c.get("titre", "") for k, c in json.loads(voc.read_text(encoding="utf-8"))["categories"].items()}
        self.docs: dict[str, str] = {}
        for nid, n in lexique.notions.items():
            if n.get("variante_de") or not (lexique._disponible(nid) or n.get("composition")):
                continue
            alias = [" ".join(f) for f in lexique.alias.get(nid, [])]
            mots = n.get("mots_fr", []) + n.get("mots_en", [])
            self.docs[nid] = " | ".join(x for x in [n["fr"], n["en"], n.get("ar", "") if n.get("ar") != n["fr"] else "",
                                                     ", ".join(dict.fromkeys(alias + mots)),
                                                     titres.get(n.get("categorie_vocabulaire", ""), "")] if x)
        self.ids = list(self.docs)
        self._indexer()
        self._ecr = None

    def _indexer(self):
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.longueurs = []
        for k, nid in enumerate(self.ids):
            n = self.lexique.notions[nid]
            # le libellé compte triple : c'est lui que l'on cherche d'abord
            c = Counter(Corpus._jetons(f"{n['fr']} {n['fr']} {n['fr']} {self.docs[nid]}"))
            self.longueurs.append(sum(c.values()))
            for t, x in c.items():
                self.postings[t].append((k, x))
        self.moyenne = sum(self.longueurs) / max(1, len(self.longueurs))
        N = len(self.ids)
        self.idf = {t: math.log(1 + (N - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def elements_a_vectoriser(self) -> list[tuple[str, str]]:
        return [(nid, self.docs[nid]) for nid in self.ids]

    # Cosinus minimal pour qu'un pictogramme soit retenu « par le sens » : chaque modèle a son échelle (les E5 donnent
    # des cosinus serrés vers le haut, bge-m3 et mpnet plus étalés). L'encodeur « hachage » n'est pas sémantique :
    # il ne compte pas comme « sens » (la ressemblance d'écriture le remplace).
    SEUILS_SENS = {"e5": 0.80, "bge": 0.50, "mpnet": 0.45, "minilm": 0.45}

    def brancher_vecteurs(self, dossier: Path, enc) -> int:
        from .vecteurs import EncodeurHachage, MatriceVecteurs
        if isinstance(enc, EncodeurHachage):
            return 0
        m = MatriceVecteurs.charger(dossier, "pictogrammes", enc.nom)
        self._vect = (enc, m) if m is not None else None
        self.seuil_sens = next((v for k, v in self.SEUILS_SENS.items() if k in enc.nom.lower()), 0.5)
        return len(m.ids) if m is not None else 0

    def _ecriture_index(self):
        """Une ligne par façon d'écrire chaque notion (libellé + 4 synonymes) : « essouflement » retrouve
        « essoufflement », « douleurs » retrouve « douleur ». Construit à la première recherche."""
        if self._ecr is None:
            formes = []
            for i in self.ids:
                vus = [self.lexique.notions[i]["fr"]] + [" ".join(f) for f in self.lexique.alias.get(i, [])[:4]]
                formes += [(i, f) for f in dict.fromkeys(vus) if f]
            vect = self._ecriture.encoder([f for _, f in formes])
            try:
                import numpy as np
                vect = np.asarray(vect, dtype="float32")
            except ImportError:
                pass
            self._ecr = ([i for i, _ in formes], vect)
        return self._ecr

    @staticmethod
    def _distance(a: str, b: str, maxi: int) -> int:
        """Distance d'édition (insertions, suppressions, substitutions), arrêtée dès qu'elle dépasse `maxi`."""
        if abs(len(a) - len(b)) > maxi:
            return maxi + 1
        prec = list(range(len(b) + 1))
        for i, x in enumerate(a, 1):
            cour = [i] + [0] * len(b)
            for j, y in enumerate(b, 1):
                cour[j] = min(prec[j] + 1, cour[j - 1] + 1, prec[j - 1] + (x != y))
            if min(cour) > maxi:
                return maxi + 1
            prec = cour
        return prec[-1]

    def _orthographe_proches(self, requete: str) -> list[str]:
        """Mots courts mal écrits (« fivre », « tousse ») : les n-grammes ne suffisent pas, la distance d'édition oui
        (1 faute jusqu'à 6 lettres, 2 au-delà)."""
        mots = self.lexique._mots(requete)
        if len(mots) != 1 or len(mots[0]) < 4:
            return []
        m = mots[0]
        maxi = 1 if len(m) <= 6 else 2
        if not hasattr(self, "_mots_simples"):
            self._mots_simples = defaultdict(set)
            for i in self.ids:
                for f in [tuple(self.lexique._mots(self.lexique.notions[i]["fr"]))] + self.lexique.alias.get(i, []):
                    if len(f) == 1:
                        self._mots_simples[f[0]].add(i)
        proches = sorted((self._distance(m, w, maxi), w) for w in self._mots_simples if abs(len(w) - len(m)) <= maxi)
        return [i for d, w in proches if d <= maxi for i in sorted(self._mots_simples[w])][:10]

    def _ecriture_proches(self, requete: str, seuil: float = 0.6) -> list[str]:
        ids, vect = self._ecriture_index()
        q = self._ecriture.encoder([requete])[0]
        try:
            import numpy as np
            scores = (vect @ np.asarray(q, dtype="float32")).tolist()
        except (ImportError, TypeError):
            scores = [sum(a * b for a, b in zip(q, v)) for v in vect]
        meilleur: dict[str, float] = {}
        for i, c in zip(ids, scores):
            if c >= seuil and c > meilleur.get(i, -1):
                meilleur[i] = c
        return [i for i, _ in sorted(meilleur.items(), key=lambda x: -x[1])[:30]]

    def chercher(self, requete: str, k: int = 12, seuil_sens: float = 0.0) -> list[dict]:
        from .vecteurs import encoder_requete, fusion_rangs
        if not requete.strip():
            return []
        scores: dict[int, float] = defaultdict(float)
        for t in set(Corpus._jetons(requete)):
            for j, tf in self.postings.get(t, ()):
                scores[j] += self.idf[t] * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * self.longueurs[j] / self.moyenne))
        mots = [self.ids[j] for j, _ in sorted(scores.items(), key=lambda x: -x[1])[:30]]
        ecriture = list(dict.fromkeys(self._orthographe_proches(requete) + self._ecriture_proches(requete)))
        sens, cos = [], {}
        if self._vect:
            enc, m = self._vect
            res = [(i, c) for i, c in m.chercher(encoder_requete(enc, requete), 30) if i in self.docs]
            meilleur = res[0][1] if res else 0
            for i, c in res:       # seuil absolu du modèle ET proche du meilleur : on ne garde que les vraies proximités
                if c >= max(seuil_sens or self.seuil_sens, meilleur - 0.10):
                    sens.append(i)
                    cos[i] = c
        classement = fusion_rangs(*[x for x in (mots, ecriture, sens) if x])
        # le libellé exact (ou un synonyme exact, au singulier) passe en tête : « douleurs » -> DOULEUR d'abord
        cles = {tuple(self.lexique._mots(requete))}
        cles |= {tuple(m[:-1] if len(m) > 3 and m[-1] in "sx" else m for m in c) for c in list(cles)}
        exacts = [i for i in self.ids if tuple(self.lexique._mots(self.lexique.notions[i]["fr"])) in cles
                  or any(tuple(a) in cles for a in self.lexique.alias.get(i, []))]
        classement = [(i, 1.0) for i in exacts] + [(i, sc) for i, sc in classement if i not in exacts]
        sortie = []
        for nid, sc in classement[:k]:
            n = self.lexique.notions[nid]
            sortie.append({"id": nid, "fr": n["fr"], "en": n["en"], "categorie": n.get("categorie_vocabulaire", ""),
                           "score": round(sc, 4), "pourquoi": {"exact": nid in exacts, "mots": nid in mots, "ecriture": nid in ecriture,
                                                               "sens": nid in cos, "cosinus": cos.get(nid)}})
        return sortie
