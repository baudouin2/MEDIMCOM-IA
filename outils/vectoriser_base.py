"""Vectorise toute la base pour la recherche hybride (mots-clés + sens), EN LOCAL, sans clé d'API.

    pip install -r requirements-vecteurs.txt                       # une fois : fastembed (ONNX) + numpy
    python outils/vectoriser_base.py                               # modèle e5 multilingue (défaut), base_v2 trouvée seule
    python outils/vectoriser_base.py --encodeur fastembed:mpnet    # plus rapide, un peu moins précis
    python outils/vectoriser_base.py --encodeur ollama:bge-m3      # si Ollama est installé (ollama pull bge-m3)
    python outils/vectoriser_base.py --exporter                    # + fichiers JSONL pour Chroma / la base de l'UIT

Collections encodées :
  kb            les 124 dispositions vérifiées et les 9 lacunes (kb/index/vecteurs_<encodeur>.jsonl)
  juridique     les articles des textes officiels de base_v2 (titre + article + texte)
  oms           les sections des fiches de l'OMS
  pictogrammes  chaque pictogramme : libellés fr/en/ar, synonymes, mots-clés ARASAAC, catégorie
                (les trois dernières dans base_v2/07_vecteurs/)

Connexion lente : téléchargez le modèle ailleurs (`--telecharger-seulement`), puis copiez le dossier
~/.cache/medimcom/modeles sur cet ordinateur (clé USB). Le modèle « minilm » ne pèse que 0,2 Go.

Le travail est sauvegardé régulièrement : si vous l'interrompez (Ctrl+C), relancez la même commande, il reprend.
Après une mise à jour de la base, seuls les textes nouveaux ou modifiés sont réencodés.
Puis lancer le serveur avec : --recherche fastembed:e5 (le même encodeur).
"""
import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "kb" / "outils"))


def main(argv=None):
    from medimcom.base_v2 import Corpus, LexiqueBaseV2, charger_pictogrammes, trouver_base
    from medimcom.vecteurs import IndexVectoriel, MatriceVecteurs, encodeur
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--encodeur", default="fastembed:e5", help="fastembed:e5 (défaut), fastembed:mpnet, ollama:bge-m3, hachage")
    p.add_argument("--base", default=None, help="dossier base_v2 (défaut : trouvé automatiquement)")
    p.add_argument("--collections", default="kb,juridique,oms,pictogrammes")
    p.add_argument("--telecharger-seulement", action="store_true",
                   help="seulement télécharger le modèle (sur une bonne connexion), pour le copier ensuite par clé USB")
    p.add_argument("--essais", type=int, default=30, help="reprises du téléchargement du modèle si la connexion coupe")
    p.add_argument("--exporter", action="store_true", help="écrire aussi {id, text, metadata, embedding} en JSONL (Chroma, UIT)")
    a = p.parse_args(argv)
    voulues = {c.strip() for c in a.collections.split(",") if c.strip()}
    enc = encodeur(a.encodeur)
    dossier_modeles = getattr(enc, "dossier_modeles", None)
    print(f"Encodeur : {enc.nom}" + (f" (modèle rangé dans {dossier_modeles()})" if dossier_modeles else ""))
    t0 = time.time()
    # Téléchargement du modèle (une seule fois) : sur une connexion instable, il est repris là où il s'était arrêté.
    for essai in range(1, a.essais + 1):
        try:
            enc.encoder(["test"], role="passage")
            break
        except KeyboardInterrupt:
            print("\nInterrompu : relancez la même commande, le téléchargement reprendra.")
            return 1
        except Exception as e:  # noqa: BLE001
            court = str(e).split("\n")[0][:160]
            if "absent" in court or isinstance(e, ImportError):      # paquet manquant : réessayer ne sert à rien
                print(f"\n✖ {court}\n  Dans cet environnement Python : pip install -r requirements-vecteurs.txt")
                return 1
            if essai == a.essais:
                print(f"\n✖ Modèle impossible à télécharger après {essai} essais ({court}).\n"
                      "  Relancez plus tard (la partie déjà reçue est gardée), ou choisissez un modèle plus léger :\n"
                      "  --encodeur fastembed:mpnet (1 Go) · fastembed:minilm (0,2 Go, textes courts).")
                return 1
            pause = min(60, 5 * essai)
            print(f"  connexion interrompue (essai {essai}/{a.essais}) : reprise dans {pause} s…")
            enc._m = None if hasattr(enc, "_m") else None
            time.sleep(pause)
    print(f"  prêt en {time.time() - t0:.0f} s")
    if a.telecharger_seulement:
        print("Modèle téléchargé. Pour l'utiliser sur un autre ordinateur, copiez ce dossier au même endroit"
              + (f" : {dossier_modeles()}" if dossier_modeles else "") + ".")
        return 0

    if "kb" in voulues:
        from construire_index import morceaux
        from medimcom.base import BaseConnaissances
        kb = RACINE / "kb"
        ms = list(morceaux(BaseConnaissances(kb)))
        print(f"  kb : {len(ms)} morceaux")
        IndexVectoriel.construire(ms, enc).sauver(kb / "index" / f"vecteurs_{enc.nom}.jsonl")

    base = trouver_base(a.base)
    if not base:
        print("base_v2 introuvable : seule la base interne kb/ a été vectorisée (--base CHEMIN).")
        return 0
    dossier = base / "07_vecteurs"
    print(f"Base : {base}")
    corpus = Corpus(base)                          # tous pays confondus : le filtre par pays se fait à la recherche
    elements = corpus.elements_a_vectoriser()
    for c in ("juridique", "oms"):
        if c in voulues and elements.get(c):
            MatriceVecteurs.construire(elements[c], enc, dossier, c)
    if "pictogrammes" in voulues and (base / "02_pictogrammes" / "notions.csv").exists():
        lx = LexiqueBaseV2(base, charger_pictogrammes(base))
        MatriceVecteurs.construire(lx.recherche.elements_a_vectoriser(), enc, dossier, "pictogrammes")
        elements["pictogrammes"] = lx.recherche.elements_a_vectoriser()

    if a.exporter:
        import numpy as np  # noqa: F401
        meta = {m["id"]: m for m in corpus.morceaux}
        for c in ("juridique", "oms", "pictogrammes"):
            m = MatriceVecteurs.charger(dossier, c, enc.nom)
            if m is None:
                continue
            textes = dict(elements.get(c, []))
            f = dossier / "export" / f"{c}.{enc.nom}.jsonl"
            f.parent.mkdir(parents=True, exist_ok=True)
            with f.open("w", encoding="utf-8") as sortie:
                for i, v in zip(m.ids, m.matrice):
                    md = {k: x for k, x in meta.get(i, {}).items() if k not in ("texte", "id")} or {"collection": c}
                    sortie.write(json.dumps({"id": i, "text": textes.get(i, ""), "metadata": md,
                                             "embedding": [round(float(x), 6) for x in v]}, ensure_ascii=False) + "\n")
            print(f"  export : {f}")
    (dossier / "LISEZMOI.md").write_text(
        "# Vecteurs de la base (recherche hybride)\n\n"
        f"Encodeur : `{enc.nom}` · similarité : cosinus (vecteurs normalisés) · fusion avec BM25 : rangs réciproques (RRF, k = 60).\n\n"
        "| Fichier | Contenu |\n|---|---|\n"
        "| `<collection>.<encodeur>.npy` | matrice float32, une ligne par morceau |\n"
        "| `<collection>.<encodeur>.json` | identifiants et empreinte SHA-256 (16 car.) de chaque texte encodé |\n"
        "| `export/*.jsonl` | `{id, text, metadata, embedding}` pour Chroma, Qdrant, FAISS ou la base de l'UIT |\n\n"
        f"Reconstruire : `python outils/vectoriser_base.py --encodeur {a.encodeur}`.\n", encoding="utf-8")
    print(f"Terminé en {(time.time() - t0) / 60:.1f} min. Lancer le serveur avec : --recherche {a.encodeur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
