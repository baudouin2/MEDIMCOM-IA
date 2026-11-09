"""Builds the vector store from the chunks of the base (kb/index/chunks.jsonl).

    ollama pull bge-m3                                            # once (multilingual embedding model, local)
    python kb/outils/construire_vecteurs.py                       # -> kb/index/vecteurs_ollama-bge-m3.jsonl
    python kb/outils/construire_vecteurs.py --encodeur hachage    # without a model (fallback, keyword search)

The file produced contains, for each chunk, the text, the metadata (source, article, official link, verification
level) and the vector: it loads as is into Chroma, Qdrant, FAISS, pgvector or the ITU vector store (see
kb/README.md). The chunks are first regenerated from the base, so that the index always matches the current provisions.
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
