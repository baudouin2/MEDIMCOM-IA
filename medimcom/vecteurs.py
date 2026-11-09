"""Base vectorielle de la base de connaissances : encodage, index, recherche par similarité, fusion avec BM25.

Deux encodeurs :
- EncodeurOllama : vrai modèle d'encodage (par défaut « bge-m3 », multilingue : français, anglais, arabe),
  exécuté en LOCAL par Ollama (http://localhost:11434). Recherche « par le sens ».
- EncodeurHachage : sans modèle ni dépendance (n-grammes de caractères hachés). Recherche par ressemblance de
  mots seulement : sert de repli et pour les tests, pas de recherche sémantique.

Format d'échange (kb/index/vecteurs_<encodeur>.jsonl) : une ligne par morceau
{"id", "text", "metadata", "embedding"} : se charge tel quel dans Chroma, Qdrant, FAISS, pgvector ou la base
vectorielle de l'UIT. L'en-tête (première ligne, clé "_index") décrit l'encodeur, la dimension et l'empreinte
des morceaux, pour vérifier qu'un index correspond bien à la base actuelle.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import time
import urllib.request
from pathlib import Path


def _normaliser(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class EncodeurHachage:
    """Vecteur de n-grammes de caractères (3 à 5) et de mots, hachés dans `dimension` cases, normalisé."""

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension
        self.nom = f"hachage-{dimension}"

    def _un(self, texte: str) -> list[float]:
        t = unicodedata.normalize("NFD", texte.lower())
        t = "".join(c for c in t if unicodedata.category(c) != "Mn")
        v = [0.0] * self.dimension
        for mot in re.findall(r"\w+", t):
            elements = [f"w:{mot}"] + [f"c:{g}" for n in (3, 4, 5) for g in
                                       (f" {mot} "[i:i + n] for i in range(max(1, len(mot) + 3 - n)))]
            for e in elements:
                h = int.from_bytes(hashlib.blake2b(e.encode(), digest_size=8).digest(), "big")
                v[h % self.dimension] += 1.0 if (h >> 63) == 0 else -1.0
        return _normaliser([math.copysign(math.log1p(abs(x)), x) for x in v])

    def encoder(self, textes: list[str], role: str = "passage") -> list[list[float]]:
        return [self._un(t) for t in textes]


class EncodeurOllama:
    """Modèle d'encodage local servi par Ollama (aucune donnée ne quitte la machine)."""

    def __init__(self, modele: str = "bge-m3", url: str = "http://localhost:11434", lot: int = 16, delai: int = 300):
        self.modele, self.url, self.lot, self.delai = modele, url.rstrip("/"), lot, delai
        self.nom = f"ollama-{modele}"
        self.dimension = None

    def encoder(self, textes: list[str], role: str = "passage") -> list[list[float]]:
        sortie = []
        for i in range(0, len(textes), self.lot):
            corps = json.dumps({"model": self.modele, "input": textes[i:i + self.lot]}).encode("utf-8")
            req = urllib.request.Request(self.url + "/api/embed", data=corps, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.delai) as r:
                    vecteurs = json.loads(r.read())["embeddings"]
            except Exception as e:
                raise RuntimeError(f"Ollama ne répond pas ou ne connaît pas « {self.modele} » ({e}). "
                                   f"Lancer Ollama, puis : ollama pull {self.modele}") from e
            sortie.extend(_normaliser(v) for v in vecteurs)
        self.dimension = len(sortie[0]) if sortie else None
        return sortie


class EncodeurFastembed:
    """Modèle d'encodage exécuté en LOCAL par fastembed (ONNX : ni PyTorch, ni carte graphique, ni clé d'API).
    Le modèle est téléchargé une fois (Hugging Face), puis tout reste sur la machine : aucune donnée ne sort.

    Alias : « e5 » = intfloat/multilingual-e5-large (1024 dimensions, ~100 langues dont français, anglais, arabe ;
    le plus précis, 2,2 Go) ; « mpnet » = paraphrase-multilingual-mpnet-base-v2 (768 dim., 1 Go, plus rapide) ;
    « minilm » = paraphrase-multilingual-MiniLM-L12-v2 (384 dim., 0,2 Go ; textes courts : pictogrammes)."""

    ALIAS = {"e5": "intfloat/multilingual-e5-large",
             "mpnet": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
             "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"}

    def __init__(self, modele: str = "e5", lot: int = 16, telecharger: bool = True):
        self.modele = self.ALIAS.get(modele, modele)
        self.telecharger = telecharger      # False : n'utiliser que le modèle déjà téléchargé (le serveur n'attend jamais)
        self.nom = "fastembed-" + re.sub(r"[^a-z0-9]+", "-", self.modele.split("/")[-1].lower()).strip("-")
        self.lot, self._m, self.dimension = lot, None, None
        # Les modèles E5 ont été entraînés avec ces préfixes : sans eux, la recherche est nettement moins bonne.
        self.prefixes = {"requete": "query: ", "passage": "passage: "} if "e5" in self.modele.lower() else {}

    @staticmethod
    def dossier_modeles() -> Path:
        """Dossier PERMANENT des modèles (par défaut fastembed les range dans /tmp, vidé au redémarrage : il faudrait
        retélécharger 2 Go). Modifiable par la variable MEDIMCOM_MODELES."""
        import os
        return Path(os.environ.get("MEDIMCOM_MODELES") or Path.home() / ".cache" / "medimcom" / "modeles")

    def _charger(self):
        if self._m is None:
            import os
            # Téléchargement HTTP classique, qui REPREND où il s'était arrêté : le protocole « Xet » de Hugging Face
            # échoue sur les connexions instables (« channel closed », « IncompleteBody »).
            os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
            os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
            try:
                from fastembed import TextEmbedding
            except ImportError as e:
                raise RuntimeError("fastembed absent : pip install -r requirements-vecteurs.txt") from e
            self.dossier_modeles().mkdir(parents=True, exist_ok=True)
            self._m = TextEmbedding(model_name=self.modele, cache_dir=str(self.dossier_modeles()),
                                    local_files_only=not self.telecharger)
        return self._m

    def encoder(self, textes: list[str], role: str = "passage") -> list[list[float]]:
        p = self.prefixes.get(role, "")
        sortie = [_normaliser([float(x) for x in v]) for v in self._charger().embed([p + t for t in textes], batch_size=self.lot)]
        self.dimension = len(sortie[0]) if sortie else None
        return sortie


def encodeur(nom: str, telecharger: bool = True):
    """« hachage », « ollama:<modèle> » (défaut bge-m3) ou « fastembed:<modèle ou alias> » (défaut e5)."""
    if nom == "hachage":
        return EncodeurHachage()
    if nom.startswith("ollama"):
        return EncodeurOllama(nom.split(":", 1)[1] if ":" in nom else "bge-m3")
    if nom.startswith("fastembed"):
        return EncodeurFastembed(nom.split(":", 1)[1] if ":" in nom else "e5", telecharger=telecharger)
    raise ValueError(f"encodeur inconnu : {nom} (hachage, ollama:<modèle>, fastembed:<modèle>)")


def encoder_requete(enc, texte: str) -> list[float]:
    """Vecteur d'une question (avec le préfixe « requête » si le modèle en a un), mis en cache : les agents posent
    souvent la même question plusieurs fois pendant une consultation."""
    cle = (getattr(enc, "nom", id(enc)), texte)
    cache = _CACHE_REQUETES
    if cle not in cache:
        try:
            v = enc.encoder([texte], role="requete")[0]
        except TypeError:                     # encodeur sans notion de rôle
            v = enc.encoder([texte])[0]
        if len(cache) > 2000:
            cache.clear()
        cache[cle] = v
    return cache[cle]


_CACHE_REQUETES: dict = {}


class MatriceVecteurs:
    """Une collection de vecteurs sur disque, pour les grandes bases (base_v2 : articles de loi, fiches de l'OMS,
    pictogrammes) : <collection>.<encodeur>.npy (float32, vecteurs normalisés) + .json (ids, empreinte de chaque texte).

    La construction REPREND où elle s'était arrêtée (sauvegarde régulière) et ne réencode que les textes nouveaux ou
    modifiés (empreinte SHA-256 de chaque texte) : relancer après une mise à jour de la base est rapide."""

    def __init__(self, ids: list[str], empreintes: list[str], matrice, encodeur_nom: str):
        self.ids, self.empreintes, self.matrice, self.encodeur_nom = ids, empreintes, matrice, encodeur_nom
        self.rang = {i: k for k, i in enumerate(ids)}

    @staticmethod
    def chemins(dossier: Path, collection: str, encodeur_nom: str) -> tuple[Path, Path]:
        return Path(dossier) / f"{collection}.{encodeur_nom}.npy", Path(dossier) / f"{collection}.{encodeur_nom}.json"

    @classmethod
    def charger(cls, dossier: Path, collection: str, encodeur_nom: str) -> "MatriceVecteurs | None":
        import numpy as np
        f_npy, f_json = cls.chemins(dossier, collection, encodeur_nom)
        if not (f_npy.exists() and f_json.exists()):
            return None
        meta = json.loads(f_json.read_text(encoding="utf-8"))
        m = np.load(f_npy)
        if len(meta["ids"]) != len(m):
            return None
        return cls(meta["ids"], meta["empreintes"], m, meta["encodeur"])

    def sauver(self, dossier: Path, collection: str) -> None:
        import numpy as np
        Path(dossier).mkdir(parents=True, exist_ok=True)
        f_npy, f_json = self.chemins(dossier, collection, self.encodeur_nom)
        tmp = f_npy.parent / (f_npy.name + ".tmp.npy")
        np.save(tmp, self.matrice.astype("float32"))
        tmp.replace(f_npy)                       # écriture atomique : une interruption ne laisse pas un fichier abîmé
        f_json.write_text(json.dumps({"encodeur": self.encodeur_nom, "collection": collection, "similarite": "cosinus",
                                      "dimension": int(self.matrice.shape[1]) if len(self.ids) else 0,
                                      "ids": self.ids, "empreintes": self.empreintes}, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def construire(cls, elements: list[tuple[str, str]], enc, dossier: Path, collection: str, lot: int = 64,
                   progression=print) -> "MatriceVecteurs":
        import numpy as np
        empreinte = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]  # noqa: E731
        ancien = cls.charger(dossier, collection, enc.nom)
        connus = {(i, e): ancien.matrice[k] for k, (i, e) in enumerate(zip(ancien.ids, ancien.empreintes))} if ancien else {}
        ids = [i for i, _ in elements]
        emps = [empreinte(t) for _, t in elements]
        vect: list = [connus.get((i, e)) for i, e in zip(ids, emps)]
        a_faire = [k for k, v in enumerate(vect) if v is None]
        progression(f"  {collection} : {len(elements)} textes, {len(elements) - len(a_faire)} déjà encodés, {len(a_faire)} à encoder")
        t0, faits = time.time(), 0
        for debut in range(0, len(a_faire), lot):
            ks = a_faire[debut:debut + lot]
            for k, v in zip(ks, enc.encoder([elements[k][1] for k in ks], role="passage")):
                vect[k] = np.asarray(v, dtype="float32")
            faits += len(ks)
            if faits % (lot * 10) < lot or faits == len(a_faire):      # sauvegarde régulière : reprise possible
                pret = [k for k, v in enumerate(vect) if v is not None]
                cls([ids[k] for k in pret], [emps[k] for k in pret], np.vstack([vect[k] for k in pret]), enc.nom).sauver(dossier, collection)
                reste = (time.time() - t0) / faits * (len(a_faire) - faits)
                progression(f"    {faits}/{len(a_faire)} encodés · reste environ {reste / 60:.0f} min")
        dim = len(next(v for v in vect if v is not None)) if elements else 0
        m = np.vstack(vect) if elements else np.zeros((0, dim), dtype="float32")
        x = cls(ids, emps, m, enc.nom)
        x.sauver(dossier, collection)
        return x

    def chercher(self, vecteur_requete: list[float], k: int = 20, autorises: set | None = None) -> list[tuple[str, float]]:
        import numpy as np
        if not len(self.ids):
            return []
        scores = self.matrice @ np.asarray(vecteur_requete, dtype="float32")       # cosinus (vecteurs normalisés)
        sortie = []
        for j in np.argsort(-scores):
            i = self.ids[int(j)]
            if autorises is None or i in autorises:
                sortie.append((i, round(float(scores[int(j)]), 4)))
                if len(sortie) >= k:
                    break
        return sortie


def empreinte_morceaux(morceaux: list[dict]) -> str:
    h = hashlib.sha256()
    for m in morceaux:
        h.update((m["id"] + "\x00" + m["text"] + "\n").encode("utf-8"))
    return h.hexdigest()[:16]


class IndexVectoriel:
    def __init__(self, morceaux: list[dict], vecteurs: list[list[float]], encodeur_nom: str, empreinte: str):
        assert len(morceaux) == len(vecteurs)
        self.morceaux, self.vecteurs, self.encodeur_nom, self.empreinte = morceaux, vecteurs, encodeur_nom, empreinte

    @classmethod
    def construire(cls, morceaux: list[dict], enc) -> "IndexVectoriel":
        return cls(morceaux, enc.encoder([m["text"] for m in morceaux]), enc.nom, empreinte_morceaux(morceaux))

    def sauver(self, chemin: Path) -> None:
        dim = len(self.vecteurs[0]) if self.vecteurs else 0
        lignes = [json.dumps({"_index": {"encodeur": self.encodeur_nom, "dimension": dim, "morceaux": len(self.morceaux),
                                         "empreinte_morceaux": self.empreinte, "similarite": "cosinus"}}, ensure_ascii=False)]
        lignes += [json.dumps({**m, "embedding": [round(x, 6) for x in v]}, ensure_ascii=False)
                   for m, v in zip(self.morceaux, self.vecteurs)]
        Path(chemin).write_text("\n".join(lignes) + "\n", encoding="utf-8")

    @classmethod
    def charger(cls, chemin: Path) -> "IndexVectoriel":
        lignes = [json.loads(l) for l in Path(chemin).read_text(encoding="utf-8").splitlines() if l.strip()]
        tete, corps = lignes[0]["_index"], lignes[1:]
        morceaux = [{k: v for k, v in x.items() if k != "embedding"} for x in corps]
        return cls(morceaux, [x["embedding"] for x in corps], tete["encodeur"], tete["empreinte_morceaux"])

    def chercher(self, question: str, enc, k: int = 5, filtre=None) -> list[tuple[str, float]]:
        q = encoder_requete(enc, question)
        scores = [(sum(a * b for a, b in zip(q, v)), m["id"]) for m, v in zip(self.morceaux, self.vecteurs)
                  if filtre is None or filtre(m)]
        scores.sort(reverse=True)
        return [(i, round(s, 4)) for s, i in scores[:k]]


def fusion_rangs(*classements: list[str], k: int = 60) -> list[tuple[str, float]]:
    """Fusion par rangs réciproques (RRF) : robuste quand les scores n'ont pas la même échelle."""
    total: dict[str, float] = {}
    for cl in classements:
        for r, i in enumerate(cl, 1):
            total[i] = total.get(i, 0.0) + 1.0 / (k + r)
    return sorted(total.items(), key=lambda x: -x[1])
