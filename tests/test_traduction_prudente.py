"""CAREFUL translation (field feedback of 7 November): better a word "without pictogram", which the doctor sees and
corrects, than a wrong image. Real cases from the journal: "pendre" -> "accrocher", "comme" -> a flag, "male" ->
"mâle", "pris" -> "casser" ("bris"), "vais" -> "ça va"."""
import json
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RACINE), str(RACINE / "outils"), str(RACINE / "tests")]

# (file, source, id, category, mots_fr): images of the full catalogue that trapped the automatic translation
PIEGES = [
    ("90_vocabulaire_general/arasaac_28691.png", "arasaac", "28691", "90_vocabulaire_general", ["accrocher", "pendre", "suspendre"]),
    ("91_emojis_symboles/openmoji_1F1E6-1F1F8.svg", "openmoji", "1F1E6_1F1F8", "91_emojis_symboles", ["comme", "drapeau"]),
    ("90_vocabulaire_general/arasaac_38895.png", "arasaac", "38895", "90_vocabulaire_general", ["mâle"]),
    ("90_vocabulaire_general/arasaac_4735.png", "arasaac", "4735", "12_symptomes", ["casser", "bris"]),
    ("90_vocabulaire_general/arasaac_13630.png", "arasaac", "13630", "03_questions", ["ça va"]),
    ("90_vocabulaire_general/arasaac_500.png", "arasaac", "500", "90_vocabulaire_general", ["voiture", "auto"]),
    ("90_vocabulaire_general/arasaac_501.png", "arasaac", "501", "90_vocabulaire_general", ["prendre"]),
    ("90_vocabulaire_general/mulberry_kill_to.svg", "mulberry", "kill_to", "90_vocabulaire_general", ["tuer"]),
]


def _base(dossier: Path) -> Path:
    from test_base_v2_branchement import constituer
    base = constituer(dossier)
    p = base / "02_pictogrammes"
    with (p / "catalogue.jsonl").open("a", encoding="utf-8") as f:
        for fichier, source, ident, cat, mots in PIEGES:
            (p / fichier).parent.mkdir(parents=True, exist_ok=True)
            (p / fichier).write_bytes(b"\x89PNG\r\n\x1a\nfaux" if fichier.endswith(".png") else b"<svg xmlns='http://www.w3.org/2000/svg'/>")
            f.write(json.dumps({"fichier": fichier, "source": source, "id": ident, "categorie": cat, "mots_fr": mots,
                                "mots_en": ["x"], "notions": [], "etiquettes": [], "popularite": 10}, ensure_ascii=False) + "\n")
    return base


def test_pas_d_image_a_tout_prix():
    from medimcom import bibliotheque as B
    from medimcom.base_v2 import LexiqueBaseV2, charger_pictogrammes
    sauve_v, sauve_e = dict(B.VOCABULAIRE), dict(B.EXTERNES)
    try:
        with tempfile.TemporaryDirectory() as t:
            lx = LexiqueBaseV2(*(lambda b: (b, charger_pictogrammes(b)))(_base(Path(t))))
            r = lx.traduire("et vous pendre")
            assert "IMG_ARASAAC_28691" not in r["pictogrammes"] and "pendre" in r["non_traduits"], r
            r = lx.traduire("je vais vous tuer")
            assert not any("KILL" in p for p in r["pictogrammes"]) and "tuer" in r["non_traduits"], r
            assert "IMG_ARASAAC_13630" not in r["pictogrammes"] and "vais" not in r["rapproches"], "« vais » n'est pas « ça va »"
            r = lx.traduire("qu'avez-vous pris comme medicament ?")
            assert not any(p.startswith("IMG_OPENMOJI") for p in r["pictogrammes"]), "« comme » n'est pas un drapeau"
            assert "IMG_ARASAAC_4735" not in r["pictogrammes"], "« pris » n'est pas « bris » (casser)"
            assert r["rapproches"].get("pris") == "IMG_ARASAAC_501", "« pris » = prendre (forme irrégulière)"
            r = lx.traduire("ou avez vous male")
            assert "IMG_ARASAAC_38895" not in r["pictogrammes"], "« male » sans accent n'est pas « mâle »"
            r = lx.traduire("Comment vous sentez-vous, où avez-vous mal ?")
            assert r["pictogrammes"].count("VOUS") <= 1 and "DOULEUR" in "".join(r["pictogrammes"]), "un seul « vous » par question"
            # what must keep working
            assert "IMG_ARASAAC_500" in lx.traduire("la voiture")["pictogrammes"], "libellé principal du catalogue : gardé"
            assert "IMG_ARASAAC_500" not in lx.traduire("une auto")["pictogrammes"], "mot-clé secondaire : pas d'office"
            r = lx.traduire("J'ai une doulleur")
            assert "DOULEUR" in r["pictogrammes"] and ("doulleur" in r["rapproches"] or "doulleur" in r["corrections"]), "faute évidente"
            # the doctor's (manual) search still finds everything, including the images kept out of automatic
            # translation
            assert any(x["id"] == "IMG_ARASAAC_28691" for x in lx.chercher("pendre", 10))
    finally:
        B.VOCABULAIRE.clear(); B.VOCABULAIRE.update(sauve_v)
        B.EXTERNES.clear(); B.EXTERNES.update(sauve_e)


def test_ou_question_jamais_perdu():
    from medimcom import bibliotheque as B
    from medimcom.base_v2 import LexiqueBaseV2, charger_pictogrammes
    sauve_v, sauve_e = dict(B.VOCABULAIRE), dict(B.EXTERNES)
    try:
        with tempfile.TemporaryDirectory() as t:
            lx = LexiqueBaseV2(*(lambda b: (b, charger_pictogrammes(b)))(_base(Path(t))))
            for texte in ("Où avez-vous mal ?", "ou avez vous mal ?"):
                r = lx.traduire(texte)
                assert "OU" in r["pictogrammes"] or any(m.lower() in ("où", "ou") for m in r["non_traduits"]), (texte, r)
            assert "OU" not in lx.traduire("Du thé ou du café")["pictogrammes"], "« ou » de choix : pas « où »"
    finally:
        B.VOCABULAIRE.clear(); B.VOCABULAIRE.update(sauve_v)
        B.EXTERNES.clear(); B.EXTERNES.update(sauve_e)


def test_mots_colles_fautes_et_anglais():
    from medimcom import bibliotheque as B
    from medimcom.base_v2 import LexiqueBaseV2, charger_pictogrammes
    sauve_v, sauve_e = dict(B.VOCABULAIRE), dict(B.EXTERNES)
    try:
        with tempfile.TemporaryDirectory() as t:
            lx = LexiqueBaseV2(*(lambda b: (b, charger_pictogrammes(b)))(_base(Path(t))))
            r = lx.traduire("j'ai malau ventre")
            assert r["corrections"].get("malau") == "mal au" and any("VENTRE" in p for p in r["pictogrammes"]), r
            r = lx.traduire("Prenez 2 comprimés jusqu'à 3 jours")
            assert "MAXIMUM" in r["pictogrammes"] and not r["corrections"], "« jusqu'à » n'est pas un mot collé"
            lx.langue_saisie = "en"
            r = lx.traduire("Do not take 2 tablets ?")
            assert "NE_PAS" in r["pictogrammes"] and "CHIFFRE:2" in r["pictogrammes"] and "QUESTION" in r["pictogrammes"], r
    finally:
        B.VOCABULAIRE.clear(); B.VOCABULAIRE.update(sauve_v)
        B.EXTERNES.clear(); B.EXTERNES.update(sauve_e)
