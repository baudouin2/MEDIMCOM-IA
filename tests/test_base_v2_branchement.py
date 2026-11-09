"""Branchement de base_v2 sur les agents : une petite base est constituée par le vrai script (réseau simulé), puis
utilisée par le traducteur, la recherche des agents, la palette du patient et le script d'évaluation."""
import json
import os
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils"))
sys.path.insert(0, str(RACINE / "tests"))
import base_v2_entrainement as ent  # noqa: E402
import constituer_base_v2 as cb  # noqa: E402
from test_constituer_base_v2 import ReseauSimule, corpus_test, pages_juridiques  # noqa: E402

MOTS_IMAGES = ["moi", "avoir mal", "douleur", "tête", "ventre", "depuis", "hier", "manger", "après", "repas", "ne pas",
               "prendre un médicament", "comprimé", "deux fois par jour", "fièvre", "sel", "question", "boire", "eau", "beaucoup",
               "dos", "toux", "nuit", "consentement", "accepter", "médecin", "gauche", "brûlure", "fort", "rouge"]


def constituer(dossier: Path) -> Path:
    ancien, cb.CORPUS = cb.CORPUS, corpus_test(dossier)
    try:
        sortie = dossier / "base_v2"
        journal = cb.Journal(sortie / "journal.json")
        cb.etape_juridique(sortie, ReseauSimule(pages_juridiques()), journal, forcer=False)
        fr = [{"_id": i, "keywords": [{"keyword": m}], "tags": [], "downloads": 1} for i, m in enumerate(MOTS_IMAGES, 1)]
        en = [{"_id": i, "keywords": [{"keyword": "x"}], "tags": []} for i in range(1, len(MOTS_IMAGES) + 1)]
        fr.append({"_id": 900, "keywords": [{"keyword": "otite externe"}], "tags": ["health", "illness"], "downloads": 1})   # sans notion
        en.append({"_id": 900, "keywords": [{"keyword": "swimmer's ear"}], "tags": ["health", "illness"]})
        pages = {f"{cb.ARASAAC_API}/pictograms/all/fr": (json.dumps(fr).encode(), "application/json"),
                 f"{cb.ARASAAC_API}/pictograms/all/en": (json.dumps(en).encode(), "application/json")}
        for i in list(range(1, len(MOTS_IMAGES) + 1)) + [900]:
            pages[cb.ARASAAC_IMG.format(id=i)] = (b"\x89PNG\r\n\x1a\nfaux", "image/png")
        cb.etape_pictogrammes(sortie, ReseauSimule(pages), journal, objectif=0)
        oms = sortie / "03_references_medicales" / "oms_fiches.jsonl"
        oms.parent.mkdir(parents=True, exist_ok=True)
        oms.write_text(json.dumps({"id": "oms-fr-malaria-1", "fiche": "malaria", "langue": "fr", "titre": "Paludisme",
                                   "section": "Symptômes", "texte": "Le paludisme provoque fièvre, frissons et maux de tête.",
                                   "url": "https://www.who.int/fr/news-room/fact-sheets/detail/malaria", "sha256": "x",
                                   "notion": "PALUDISME", "licence": "OMS"}, ensure_ascii=False) + "\n" + json.dumps(
            {"id": "oms-ar-malaria-1", "fiche": "malaria", "langue": "ar", "titre": "الملاريا", "section": "الأعراض",
             "texte": "تشمل أعراض الملاريا الحمى والقشعريرة والصداع.", "url": "https://www.who.int/ar/news-room/fact-sheets/detail/malaria",
             "sha256": "y", "notion": "PALUDISME", "licence": "OMS"}, ensure_ascii=False) + "\n", encoding="utf-8")
        ent.etape_entrainement(sortie)
        return sortie
    finally:
        cb.CORPUS = ancien


def test_branchement_complet():
    from medimcom import bibliotheque as B
    from medimcom.base_v2 import Corpus, LexiqueBaseV2, charger_pictogrammes, palette_patient, trouver_base
    with tempfile.TemporaryDirectory() as t:
        base = constituer(Path(t))
        assert trouver_base(str(base)) == base.resolve() and trouver_base("aucune") is None
        sauve_v, sauve_e = dict(B.VOCABULAIRE), dict(B.EXTERNES)
        try:
            notions = charger_pictogrammes(base)
            assert B.connu("TETE") and B.connu("FIEVRE") and "<image" in B.svg("FIEVRE")
            lex = LexiqueBaseV2(base, notions)
            r = lex.traduire("J'ai mal à la tête depuis hier")
            assert r["pictogrammes"][0] == "MOI" and "TETE+DOULEUR" in r["pictogrammes"] and "HIER" in r["pictogrammes"], r
            r = lex.traduire("Ne prenez pas de comprimé après le repas")
            assert "NE_PAS" in r["pictogrammes"] and "COMPRIME" in r["pictogrammes"], r
            assert r["pictogrammes"][-2:] == ["APRES", "REPAS"], "« après le repas » = notion composée APRÈS + REPAS"
            r = lex.traduire("Prenez 2 comprimés deux fois par jour, jusqu'à 3 jours")
            assert "CHIFFRE:2" in r["pictogrammes"] and "MAXIMUM" in r["pictogrammes"] and "COMPRIME" in r["pictogrammes"], r
            r = lex.traduire("Avez-vous une allergie au pollen ?")
            assert "QUESTION" in r["pictogrammes"] and any("pollen" in m for m in r["non_traduits"]), "mot inconnu signalé, jamais inventé"
            assert "tête" in lex.interpreter(["TETE+DOULEUR"]).lower()
            r = lex.traduire("Buvez beaucoup d'eau, mangez après le repas")
            assert {"BOIRE", "BEAUCOUP", "EAU", "MANGER"} <= set(r["pictogrammes"]) and not r["non_traduits"], r
            assert "la" not in lex.traduire("J'ai mal à la tête")["non_traduits"]
            r = lex.traduire("J'ai une brûlure au ventre à gauche")
            assert "VENTRE+BRULURE+GAUCHE" in r["pictogrammes"], r
            r = lex.traduire("Pas de douleur au dos")
            assert r["pictogrammes"][0] == "NE_PAS" and "DOS+DOULEUR" in r["pictogrammes"], "la négation reste entière"
            pal = palette_patient(notions)
            assert pal["intensite"][:11] == [f"CHIFFRE:{i}" for i in range(11)] and "FORT" in pal["intensite"]
            assert "BRULURE" in pal["douleur"] and "ROUGE" in pal["sensations"] and "GAUCHE" in pal["localisation"]
            assert "IMG_ARASAAC_900" in notions and B.connu("IMG_ARASAAC_900") and B.libelle("IMG_ARASAAC_900") == "otite externe"
            assert any("IMG_ARASAAC_900" in v for v in pal.values()), "toute image de la base est proposée au patient"
            assert "IMG_ARASAAC_900" in lex.traduire("Vous avez une otite externe")["pictogrammes"], "mot-clé d'une image hors vocabulaire"
            assert "douleur" in palette_patient(notions) or "corps" in palette_patient(notions)

            c = Corpus(base, pays="CM")
            assert len(c) > 10
            res = c.chercher("droit de toute personne à la santé", k=3)
            assert res and res[0]["lien"].startswith("https://") and res[0]["citation"]
            assert c.chercher("frissons paludisme", k=1, type_="reference_medicale")[0]["source"] == "OMS:malaria"
            assert c.chercher("ما هي أعراض الملاريا؟", k=1, type_="reference_medicale")[0]["extrait"] == "oms-ar-malaria-1", "recherche en arabe"

            from medimcom.session import Config, construire
            ctx, agents, _ = construire(Config(base=str(base), verbeux=False))
            assert isinstance(ctx.pictogrammeur, LexiqueBaseV2) and ctx.corpus is not None
            juriste = next(a for a in agents if a.nom == "juriste")
            rep = juriste._consulter("droit à la santé information", 3)
            assert set(rep) == {"fiches", "extraits"} and rep["extraits"]
            config = next(l for l in ctx.journal.lignes if l["type"] == "configuration")["contenu"]
            assert "LexiqueBaseV2" in config["pictogrammes"] and config["base_v2"] == str(base.resolve())

            ctx2, _, _ = construire(Config(base="aucune", verbeux=False))
            assert ctx2.corpus is None and type(ctx2.pictogrammeur).__name__ == "LexiquePictogrammes"

            import evaluer_base_v2 as ev
            assert ev.main(["--base", str(base)]) == 0
            res = json.loads((base / "06_evaluation" / "resultats.json").read_text(encoding="utf-8"))
            assert res["traduction"]["exemples"] > 0 and res["traduction"]["negations_conservees"].split("/")[0] == res["traduction"]["negations_conservees"].split("/")[1]
            assert "Recherche juridique" in (base / "06_evaluation" / "RESULTATS.md").read_text(encoding="utf-8")
        finally:
            B.VOCABULAIRE.clear(); B.VOCABULAIRE.update(sauve_v)
            B.EXTERNES.clear(); B.EXTERNES.update(sauve_e)
            os.environ["MEDIMCOM_BASE"] = "aucune"
