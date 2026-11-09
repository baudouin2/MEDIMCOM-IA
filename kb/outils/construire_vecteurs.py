"""Construit la base vectorielle à partir des morceaux de la base (kb/index/chunks.jsonl).

    ollama pull bge-m3                                            # une fois (modèle d'encodage multilingue, local)
    python kb/outils/construire_vecteurs.py                       # -> kb/index/vecteurs_ollama-bge-m3.jsonl
    python kb/outils/construire_vecteurs.py --encodeur hachage    # sans modèle (repli, recherche par mots)

Le fichier produit contient, pour chaque morceau, le texte, les métadonnées (source, article, lien officiel,
niveau de vérification) et le vecteur : il se charge tel quel dans Chroma, Qdrant, FAISS, pgvector ou la base
vectorielle de l'UIT (voir kb/README.md). Les morceaux sont d'abord régénérés depuis la base, pour que l'index
corresponde toujours aux fiches actuelles.
"""
import argparse
import json
import time

from _chemin import KB
from construire_index import morceaux
from medimcom.base import BaseConnaissances
from medimcom.vecteurs import IndexVectoriel, encodeur

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--encodeur", default="ollama:bge-m3", help="ollama:<modèle> (défaut ollama:bge-m3) ou hachage")
    a = p.parse_args()
    base = BaseConnaissances(KB)
    ms = list(morceaux(base))
    (KB / "index" / "chunks.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in ms), encoding="utf-8")
    enc = encodeur(a.encodeur)
    t0 = time.time()
    index = IndexVectoriel.construire(ms, enc)
    sortie = KB / "index" / f"vecteurs_{enc.nom}.jsonl"
    index.sauver(sortie)
    print(f"{len(ms)} morceaux encodés avec {enc.nom} (dimension {len(index.vecteurs[0])}) en {time.time() - t0:.0f} s -> {sortie}")
