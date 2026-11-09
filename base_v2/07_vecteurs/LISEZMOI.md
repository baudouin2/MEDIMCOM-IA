# Vecteurs de la base (recherche hybride)

Encodeur : `fastembed-paraphrase-multilingual-minilm-l12-v2` · similarité : cosinus (vecteurs normalisés) · fusion avec BM25 : rangs réciproques (RRF, k = 60).

| Fichier | Contenu |
|---|---|
| `<collection>.<encodeur>.npy` | matrice float32, une ligne par morceau |
| `<collection>.<encodeur>.json` | identifiants et empreinte SHA-256 (16 car.) de chaque texte encodé |
| `export/*.jsonl` | `{id, text, metadata, embedding}` pour Chroma, Qdrant, FAISS ou la base de l'UIT |

Reconstruire : `python outils/vectoriser_base.py --encodeur fastembed:minilm`.
