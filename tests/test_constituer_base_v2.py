"""Tests hors ligne de outils/constituer_base_v2.py : le réseau est simulé, aucun site n'est contacté.

    python -m pytest tests/test_constituer_base_v2.py -q      (ou : python tests/test_constituer_base_v2.py)
"""
import csv
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import constituer_base_v2 as cb  # noqa: E402


def pdf_avec_articles(titre: str, n: int = 5) -> bytes:
    try:
        from reportlab.pdfgen import canvas
    except ImportError:  # sans reportlab : PDF minimal écrit à la main
        lignes = " ".join(f"(Article {i} Le patient a droit a l information numero {i}.) Tj T*" for i in range(1, n + 1))
        flux = f"BT /F1 10 Tf 14 TL 40 800 Td ({titre}) Tj T* {lignes} ET".encode()
        objets = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                  b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
                  b"<< /Length %d >>stream\n" % len(flux) + flux + b"\nendstream",
                  b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
        sortie, pos = b"%PDF-1.4\n", []
        for i, o in enumerate(objets, 1):
            pos.append(len(sortie))
            sortie += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        xref = len(sortie)
        sortie += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % p for p in pos)
        return sortie + b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % xref
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon)
    y = 800
    c.drawString(40, y, titre)
    for i in range(1, n + 1):
        y -= 40
        c.drawString(40, y, f"Article {i}")
        c.drawString(40, y - 14, f"Toute personne a droit a l'information sur sa sante, disposition numero {i}, en langue comprise.")
    c.save()
    return tampon.getvalue()


class ReseauSimule(cb.Reseau):
    def __init__(self, pages: dict):
        super().__init__(actif=True, pause=0, essais=1)
        self.pages, self.appels = pages, []

    def get(self, url):
        self.appels.append(url)
        if url not in self.pages:
            raise RuntimeError("HTTP 404")
        donnees, type_contenu = self.pages[url]
        return donnees, type_contenu, url


def corpus_test(dossier: Path) -> Path:
    corpus = dossier / "corpus"
    corpus.mkdir()
    for f in ("filtres_pictogrammes.json", "vocabulaire_consultation.json"):
        shutil.copy2(cb.CORPUS / f, corpus / f)
    vrai = json.loads((cb.CORPUS / "catalogue_sources.json").read_text(encoding="utf-8"))
    base = {"axes": vrai["axes"], "dossiers": vrai["dossiers"], "description": "test"}
    commun = dict(autorite="Test", date="2020", type="loi", langue="fr", verification="a_confirmer", utilite="test", themes=["sante"])
    base["sources"] = [
        dict(id="CM-PDF", titre="Loi directe en PDF", dossier="A_cameroun/01_lois_reglementations_sante", axes=["E1"],
             urls=["https://ex.cm/loi.pdf"], **commun),
        dict(id="CM-PAGE", titre="Loi cadre sante trouvee dans la page", dossier="A_cameroun/01_lois_reglementations_sante", axes=["E1", "E4"],
             urls=["https://ex.who/page"], **commun),
        dict(id="UN-HTML", titre="Pacte en HTML", dossier="B_international/01_onu_droits_humains", axes=["E5"],
             urls=["https://ex.un/pacte"], **commun),
        dict(id="CM-MANQUE", titre="Loi introuvable", dossier="A_cameroun/03_protection_donnees", axes=["E3"], urls=[], **commun),
        dict(id="CM-DEPOSE", titre="Texte depose a la main", dossier="A_cameroun/02_strategies_ia_numerique_cybersecurite",
             axes=["E2"], urls=["https://ex.cm/bloque"], **commun),
    ]
    (corpus / "catalogue_sources.json").write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    return corpus


def pages_juridiques() -> dict:
    page = (b"<html><head><title>Loi</title></head><body><p>Fiche du texte</p>"
            b"<a href='/files/rapport_summary.pdf'>Summary</a>"
            b"<a href='/files/loi_cadre_sante.pdf'>Telecharger le texte integral (PDF)</a></body></html>")
    pacte = ("<html><body><script>var x=1;</script><h1>Pacte</h1>" +
             "".join(f"<p>Article {i}</p><p>" + f"Les Etats parties reconnaissent le droit de toute personne a la sante, alinea {i}. " * 3 + "</p>"
                     for i in range(1, 13)) + "</body></html>").encode()
    return {"https://ex.cm/loi.pdf": (pdf_avec_articles("Loi directe"), "application/pdf"),
            "https://ex.who/page": (page, "text/html"),
            "https://ex.who/files/loi_cadre_sante.pdf": (pdf_avec_articles("Loi cadre", 7), "application/pdf"),
            "https://ex.un/pacte": (pacte, "text/html; charset=utf-8")}


def test_juridique_complet():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        ancien, cb.CORPUS = cb.CORPUS, corpus_test(t)
        try:
            sortie = t / "base"
            (sortie / "entrees_manuelles").mkdir(parents=True)
            (sortie / "entrees_manuelles" / "CM-DEPOSE.pdf").write_bytes(pdf_avec_articles("Depose", 4))
            reseau = ReseauSimule(pages_juridiques())
            journal = cb.Journal(sortie / "journal.json")
            r = cb.etape_juridique(sortie, reseau, journal, forcer=False)
            assert r == {"documents": 5, "obtenus": 4, "manquants": 1, "morceaux_rag": r["morceaux_rag"]}, r
            jur = sortie / "01_base_juridique"
            d = jur / "A_cameroun/01_lois_reglementations_sante/CM-PAGE"
            assert (d / "original.pdf").read_bytes()[:4] == b"%PDF"
            assert "https://ex.who/files/loi_cadre_sante.pdf" in reseau.appels
            assert "rapport_summary" not in " ".join(reseau.appels), "le résumé ne doit pas être préféré au texte intégral"
            arts = [json.loads(l) for l in (d / "articles.jsonl").read_text(encoding="utf-8").splitlines()]
            assert [a["article"] for a in arts][:3] == ["1", "2", "3"] and len(arts) == 7, [a["article"] for a in arts]
            html_doc = jur / "B_international/01_onu_droits_humains/UN-HTML"
            assert (html_doc / "original.html").exists() and "var x" not in (html_doc / "texte.md").read_text(encoding="utf-8")
            assert len((html_doc / "articles.jsonl").read_text(encoding="utf-8").splitlines()) == 12
            assert "dépôt manuel" in (jur / "A_cameroun/02_strategies_ia_numerique_cybersecurite/CM-DEPOSE/fiche.md").read_text(encoding="utf-8")
            manuel = (sortie / "a_telecharger_a_la_main.md").read_text(encoding="utf-8")
            assert "CM-MANQUE" in manuel and "CM-DEPOSE" not in manuel
            matrice = (jur / "matrice_exigences.md").read_text(encoding="utf-8")
            assert "lacune" in matrice and "| E3 Protection des données | 0 / 1 |" in matrice
            rag = [json.loads(l) for l in (jur / "corpus_rag.jsonl").read_text(encoding="utf-8").splitlines()]
            assert all({"id", "text", "metadata"} <= set(x) for x in rag) and len({x["id"] for x in rag}) == len(rag)
            assert rag[0]["metadata"]["sha256"] and rag[0]["metadata"]["axes"]
            with (jur / "index_sources.csv").open(encoding="utf-8-sig") as f:
                assert len(list(csv.reader(f, delimiter=";"))) == 6
            # relance : rien n'est retéléchargé
            reseau2 = ReseauSimule(pages_juridiques())
            r2 = cb.etape_juridique(sortie, reseau2, cb.Journal(sortie / "journal.json"), forcer=False)
            assert r2["obtenus"] == 4 and reseau2.appels == [], reseau2.appels
        finally:
            cb.CORPUS = ancien


def faux_arasaac():
    def item(i, fr, en, tags, cats=(), **k):
        return ({"_id": i, "keywords": [{"keyword": x} for x in fr], "tags": list(tags), "categories": list(cats), "downloads": 10, **k},
                {"_id": i, "keywords": [{"keyword": x} for x in en], "tags": list(tags), "categories": list(cats)})
    items = [item(1, ["douleur"], ["pain"], ["health", "symptom"]),
             item(2, ["dinosaure"], ["dinosaur"], ["animal", "dinosaur", "prehistory"]),
             item(3, ["Saragosse"], ["Zaragoza"], ["place", "aragon", "city"]),
             item(4, ["triste"], ["sad"], ["feeling"]),
             item(5, ["fard à paupières"], ["eyeshadow"], ["makeup", "cosmetic", "beauty"]),
             item(6, ["stéthoscope"], ["stethoscope"], ["medical equipment", "health"]),
             item(7, ["coup"], ["hit"], ["action"], violence=True),
             item(8, ["radiographie du thorax"], ["chest x-ray"], ["medical test", "health"]),
             item(9, ["médecin"], ["doctor"], ["health professional", "job"])]
    return [a for a, _ in items], [b for _, b in items]


def test_pictogrammes_filtres():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fr, en = faux_arasaac()
        png = b"\x89PNG\r\n\x1a\nfaux"
        pages = {f"{cb.ARASAAC_API}/pictograms/all/fr": (json.dumps(fr).encode(), "application/json"),
                 f"{cb.ARASAAC_API}/pictograms/all/en": (json.dumps(en).encode(), "application/json"),
                 cb.MULBERRY + "scripts/data/symbol-info-en.csv": (
                     "symbol-id,symbol,grammar,category-id,category,rated,tags\n1,thermometer,Noun,5,Healthcare Medical items,0,\n"
                     "2,tiger,Noun,6,Animal Mammal,0,\n3,doctor,Noun,7,People Profession,0,\n4,builder,Noun,7,People Profession,0,\n"
                     "5,\"vomit_,_to\",Verb,8,Verb,0,\n6,knife,Noun,9,Food Kitchen items,0,\n".encode(), "text/csv"),
                 cb.OPENMOJI + "data/openmoji.json": (json.dumps([
                     {"hexcode": "1F912", "annotation": "face with thermometer", "group": "smileys-emotion", "subgroups": "face-unwell", "tags": "ill, sick", "openmoji_tags": "", "skintone": ""},
                     {"hexcode": "1F996", "annotation": "T-Rex", "group": "animals-nature", "subgroups": "animal-reptile", "tags": "dinosaur", "openmoji_tags": "", "skintone": ""},
                     {"hexcode": "1F9D1-200D-2695-FE0F", "annotation": "health worker", "group": "people-body", "subgroups": "person-role", "tags": "doctor", "openmoji_tags": "", "skintone": ""},
                     {"hexcode": "1F9D1-1F3FB-200D-2695-FE0F", "annotation": "health worker: light skin tone", "group": "people-body", "subgroups": "person-role", "tags": "doctor", "openmoji_tags": "", "skintone": "1F3FB"}]).encode(), "application/json")}
        for i in range(1, 10):
            pages[cb.ARASAAC_IMG.format(id=i)] = (png, "image/png")
        for nom in ("thermometer", "doctor", "vomit_%2C_to", "knife"):
            pages[cb.MULBERRY + f"EN/{nom}.svg"] = (b"<svg/>", "image/svg+xml")
        for h in ("1F912", "1F9D1-200D-2695-FE0F"):
            pages[cb.OPENMOJI + f"color/618x618/{h}.png"] = (png, "image/png")
        sortie = t / "base"
        reseau = ReseauSimule(pages)
        r = cb.etape_pictogrammes(sortie, reseau, cb.Journal(sortie / "journal.json"))
        p = sortie / "02_pictogrammes"
        fichiers = {f.name for f in p.rglob("*") if f.suffix in (".png", ".svg")}
        assert {"arasaac_1.png", "arasaac_4.png", "arasaac_6.png", "arasaac_8.png", "arasaac_9.png"} <= fichiers, fichiers
        for exclu in ("arasaac_2.png", "arasaac_3.png", "arasaac_5.png", "arasaac_7.png", "mulberry_tiger.svg", "mulberry_builder.svg",
                      "openmoji_1F996.png", "openmoji_1F9D1-1F3FB-200D-2695-FE0F.png"):
            assert exclu not in fichiers, exclu
        assert (p / "11_douleur_description" / "arasaac_1.png").exists(), "douleur doit être rangée avec la description de la douleur (notion)"
        assert (p / "14_emotions_ressenti" / "arasaac_4.png").exists()
        assert (p / "08_personnes_soignants" / "mulberry_doctor.svg").exists()
        notions = {l["notion"]: l for l in csv.DictReader((p / "notions.csv").open(encoding="utf-8-sig"), delimiter=";")}
        assert "arasaac_1.png" in notions["DOULEUR"]["images"] and "mulberry_thermometer.svg" in notions["THERMOMETRE"]["images"]
        assert r["par_source"] == {"arasaac": 5, "mulberry": 4, "openmoji": 2}, r
        assert (p / "11_douleur_description" / "mulberry_knife.svg").exists(), "symbole rattaché par libellé anglais exact (alias « knife »)"
        assert (p / "planches" / "index.html").exists() and (p / "LICENCES.md").exists()
        rejets = (p / "audit" / "rejets.csv").read_text(encoding="utf-8-sig")
        assert "violence" in rejets
        # relance : aucune image retéléchargée
        reseau2 = ReseauSimule(pages)
        cb.etape_pictogrammes(sortie, reseau2, cb.Journal(sortie / "journal.json"))
        assert not [u for u in reseau2.appels if u.endswith((".png", ".svg"))]


def test_audit_et_sans_reseau():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fr, en = faux_arasaac()
        pages = {f"{cb.ARASAAC_API}/pictograms/all/fr": (json.dumps(fr).encode(), "application/json"),
                 f"{cb.ARASAAC_API}/pictograms/all/en": (json.dumps(en).encode(), "application/json")}
        r = cb.etape_audit_pictos(t / "b", ReseauSimule(pages))
        assert r["pictogrammes_arasaac"] == 9 and r["noire"] >= 4
        lignes = (t / "b/02_pictogrammes/audit/etiquettes_arasaac.csv").read_text(encoding="utf-8-sig")
        assert "dinosaur" in lignes
        assert cb.main(["--sortie", str(t / "c"), "--sans-reseau", "--etapes", "juridique"]) == 0
        assert (t / "c/a_telecharger_a_la_main.md").exists() and (t / "c/00_LISEZMOI.md").exists()


def test_migration():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        ancienne = t / "ancienne"
        (ancienne / "1_textes_juridiques/complementaires/CM_Cameroun/originaux").mkdir(parents=True)
        (ancienne / "1_textes_juridiques/complementaires/CM_Cameroun/originaux/CM-DEC-2013-093.pdf").write_bytes(b"%PDF-1.4 x")
        (ancienne / "1_textes_juridiques/CM_Cameroun/divers.pdf").parent.mkdir(parents=True)
        (ancienne / "1_textes_juridiques/CM_Cameroun/divers.pdf").write_bytes(b"%PDF-1.4 y")
        (ancienne / "3_jeu_de_donnees_assistant/references/oms").mkdir(parents=True)
        (ancienne / "3_jeu_de_donnees_assistant/references/oms/paludisme.md").write_text("x", encoding="utf-8")
        (ancienne / "3_jeu_de_donnees_assistant/cas.jsonl").write_text("{}\n", encoding="utf-8")
        r = cb.etape_migration(ancienne, t / "nouvelle")
        assert (t / "nouvelle/entrees_manuelles/CM-DEC-2013-093.pdf").exists()
        assert (t / "nouvelle/01_base_juridique/E_anciens_a_classer/CM_Cameroun/divers.pdf").exists()
        assert (t / "nouvelle/03_references_medicales/oms/paludisme.md").exists()
        assert (t / "nouvelle/04_jeu_de_donnees_assistant/cas.jsonl").exists()
        assert not (t / "nouvelle/04_jeu_de_donnees_assistant/references").exists()
        assert r["textes_rattaches"] == 1 and r["textes_a_classer"] == 1


def test_catalogue_reel_coherent():
    cat = json.loads((cb.CORPUS / "catalogue_sources.json").read_text(encoding="utf-8"))
    ids = [s["id"] for s in cat["sources"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 80
    for s in cat["sources"]:
        assert set(s["axes"]) <= set(cat["axes"]), s["id"]
        assert s["dossier"].split("/")[0] in cat["dossiers"], s["id"]
        assert s["urls"] or s.get("page") or s["verification"] == "manuel", s["id"]
        assert all(u.startswith("https://") or u.startswith("http://") for u in s["urls"]), s["id"]
        for u in s["urls"]:
            assert not any(p in u for p in ("memoireonline", "anove.ai", "bristows", "camerlex")), f"source non officielle : {s['id']}"
    cm = [s for s in cat["sources"] if s["dossier"].startswith("A_cameroun")]
    assert len(cm) >= 25
    notions, _ = cb.charger_vocabulaire()
    assert len(notions) >= 500 and len({n["id"] for n in notions}) == len(notions)


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)


# ------------------------------------------------------------------------------- version « de zéro » : objectif, références, entraînement
import base_v2_entrainement as ent  # noqa: E402
import base_v2_references as ref  # noqa: E402


def test_objectif_pictos_elargit_sans_sortir_du_domaine():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fr, en = faux_arasaac()
        for i in range(100, 110):   # variantes supplémentaires de « douleur »
            fr.append({"_id": i, "keywords": [{"keyword": "douleur"}], "tags": [], "downloads": 1})
            en.append({"_id": i, "keywords": [{"keyword": "pain"}], "tags": []})
        for i in range(200, 205):   # mot-clé contenant une notion santé, sans étiquette
            fr.append({"_id": i, "keywords": [{"keyword": f"fièvre forte {i}"}], "tags": [], "downloads": 1})
            en.append({"_id": i, "keywords": [{"keyword": "high fever"}], "tags": []})
        fr.append({"_id": 300, "keywords": [{"keyword": "dinosaure fièvre"}], "tags": ["dinosaur"], "downloads": 99})
        en.append({"_id": 300, "keywords": [{"keyword": "dinosaur"}], "tags": ["dinosaur"]})
        png = b"\x89PNG\r\n\x1a\nfaux"
        pages = {f"{cb.ARASAAC_API}/pictograms/all/fr": (json.dumps(fr).encode(), "application/json"),
                 f"{cb.ARASAAC_API}/pictograms/all/en": (json.dumps(en).encode(), "application/json")}
        for it in fr:
            pages[cb.ARASAAC_IMG.format(id=it["_id"])] = (png, "image/png")
        sortie = t / "b"
        sans = cb.etape_pictogrammes(sortie, ReseauSimule(pages), cb.Journal(sortie / "journal.json"), objectif=0)
        avec = cb.etape_pictogrammes(t / "c", ReseauSimule(pages), cb.Journal(t / "c" / "journal.json"), objectif=1000)
        assert sans["images"] == 7 and avec["images"] == 7 + 8 + 5, (sans, avec)   # 3 variantes de « douleur » sur 11 prises d'office
        assert avec["objectif_atteint"] is False and len(avec["paliers"]) == 3
        assert not (t / "c/02_pictogrammes/13_maladies_antecedents/arasaac_300.png").exists()
        assert not list((t / "c/02_pictogrammes").rglob("arasaac_300.png")), "liste noire respectée même pour atteindre l'objectif"
        petit = cb.etape_pictogrammes(t / "d", ReseauSimule(pages), cb.Journal(t / "d" / "journal.json"), objectif=10)
        assert petit["images"] == 10 and petit["objectif_atteint"] is True


def test_notions_citees_existent():
    notions, _ = cb.charger_vocabulaire()
    ids = {n["id"] for n in notions}
    manquantes = {n for _, n in ref.OMS_FICHES} - ids
    assert not manquantes, manquantes
    assert len(ent.phrases(notions)) > 1500
    for p in ent.phrases(notions)[:50]:
        assert set(p["notions"]) <= ids and p["fr"] and p["en"]
    for c in list(ent.A_CORPS) + list(ent.A_MED) + ent.SYMPTOMES_NOMS + ent.EMOTIONS + ent.TEMPS:
        assert c in ids, c


def test_references_et_entrainement_de_zero():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        ancien, cb.CORPUS = cb.CORPUS, corpus_test(t)
        try:
            sortie = t / "base"
            journal = cb.Journal(sortie / "journal.json")
            cb.etape_juridique(sortie, ReseauSimule(pages_juridiques()), journal, forcer=False)
            fiche = ("<html><body><nav>Menu</nav><h1>Paludisme</h1><h2>Principaux faits</h2><p>" + "Le paludisme est une maladie due à un parasite. " * 4 +
                     "</p><h2>Symptômes</h2><p>" + "Fièvre, maux de tête et frissons apparaissent 10 à 15 jours après la piqûre. " * 3 +
                     "</p><h2>Prévention</h2><p>" + "Dormir sous une moustiquaire imprégnée d'insecticide. " * 3 + "</p><footer>Pied</footer></body></html>").encode()
            pages = {ref.LANGUES["fr"] + "malaria": (fiche, "text/html"), ref.LANGUES["en"] + "malaria": (fiche.replace(b"Sympt\xc3\xb4mes", b"Symptoms"), "text/html"),
                     ref.MEDLINE + "fever": (b"<nlmSearchResult><list><document url='https://medlineplus.gov/fever.html'><content name='title'>Fever</content>"
                                             b"<content name='FullSummary'>&lt;p&gt;A fever is a body temperature above normal.&lt;/p&gt;</content>"
                                             b"<content name='mesh'>Fever</content></document></list></nlmSearchResult>", "text/xml"),
                     ref.WIKIDATA + "action=wbsearchentities&type=item&limit=1&language=en&search=malaria": (b'{"search":[{"id":"Q12156"}]}', "application/json")}
            pages[ref.WIKIDATA + "action=wbgetentities&props=labels|descriptions|aliases|claims&languages=fr|en|ar&ids=Q12156"] = (json.dumps(
                {"entities": {"Q12156": {"labels": {"fr": {"value": "paludisme"}, "en": {"value": "malaria"}, "ar": {"value": "ملاريا"}},
                                         "aliases": {"fr": [{"value": "malaria"}]},
                                         "claims": {"P494": [{"mainsnak": {"datavalue": {"value": "B50-B54"}}}]}}}}).encode(), "application/json")
            r = ref.etape_references(sortie, ReseauSimule(pages), journal)
            assert r["oms"]["pages"] == 2 and r["medlineplus"]["sujets"] == 1 and r["wikidata"]["termes"] == 1, r
            sections = [json.loads(l) for l in (sortie / "03_references_medicales/oms_fiches.jsonl").read_text(encoding="utf-8").splitlines()]
            assert {s["section"] for s in sections if s["langue"] == "fr"} == {"Principaux faits", "Symptômes", "Prévention"}
            assert all("Menu" not in s["texte"] and s["sha256"] for s in sections)
            lex = (sortie / "03_references_medicales/lexique_multilingue_wikidata.csv").read_text(encoding="utf-8-sig")
            assert "ملاريا" in lex and "B50-B54" in lex
            fr, en = faux_arasaac()
            pp = {f"{cb.ARASAAC_API}/pictograms/all/fr": (json.dumps(fr).encode(), "application/json"),
                  f"{cb.ARASAAC_API}/pictograms/all/en": (json.dumps(en).encode(), "application/json")}
            for i in range(1, 10):
                pp[cb.ARASAAC_IMG.format(id=i)] = (b"\x89PNG", "image/png")
            cb.etape_pictogrammes(sortie, ReseauSimule(pp), journal, objectif=0)
            e = ent.etape_entrainement(sortie)
            assert e["pictogrammes_images"] == 5 and e["phrases_pictogrammes"] > 1500 and e["juridique_classification"] > 20
            assert e["references_qr"] == 6, e   # 3 sections × 2 langues
            d = sortie / "05_jeux_entrainement"
            qr = [json.loads(l) for l in (d / "references_qr.jsonl").read_text(encoding="utf-8").splitlines()]
            assert any(q["question"] == "Quels sont les symptômes : Paludisme ?" for q in qr)
            meta = [json.loads(l) for l in (sortie / "02_pictogrammes/metadata.jsonl").read_text(encoding="utf-8").splitlines()]
            assert all((sortie / "02_pictogrammes" / m["file_name"]).exists() and m["split"] in ("train", "validation", "test") for m in meta)
            ph = [json.loads(l) for l in (d / "phrases_pictogrammes.jsonl").read_text(encoding="utf-8").splitlines()]
            douleur = next(p for p in ph if p["notions"] == ["MOI", "AVOIR_MAL", "TETE"])
            assert douleur["fr"] == "J'ai mal à la tête." and douleur["synthetique"] is True
            assert "Usages interdits" in (d / "FICHE_DE_DONNEES.md").read_text(encoding="utf-8")
            assert ent.partition("x") == ent.partition("x")
        finally:
            cb.CORPUS = ancien


def test_vocabulaire_conversationnel():
    v = json.loads((cb.CORPUS / "vocabulaire_consultation.json").read_text(encoding="utf-8"))
    assert len(v["categories"]) == 30 and len(v["groupes"]) == 5
    notions, _ = cb.charger_vocabulaire()
    ids = {n["id"] for n in notions}
    assert len(notions) >= 1200
    composees = [n for n in notions if n["composition"]]
    assert len(composees) >= 150
    for n in composees:
        assert set(n["composition"]) <= ids, (n["id"], set(n["composition"]) - ids)
    par_id = {n["id"]: n for n in notions}
    assert par_id["OU_AVEZ_VOUS_MAL"]["composition"] == ["OU", "AVOIR_MAL"]
    assert "s'asseoir" in par_id["ASSEYEZ_VOUS"]["recherche_fr"] and "sit" in par_id["ASSEYEZ_VOUS"]["recherche_en"]
    for cat in ("03_questions", "05_reassurance_soutien", "06_consignes_examen", "07_conseils_recommandations", "11_douleur_description",
                "16_medicaments_posologie", "17_chirurgie_operations", "20_alimentation_regime", "22_activite_sommeil_mode_de_vie", "25_vie_quotidienne_contexte"):
        assert sum(1 for n in notions if n["categorie"] == cat) >= 20, cat
    intentions = {p["intention"].split(":")[0] for p in ent.phrases(notions)}
    assert {"question", "consigne", "conseil", "reassurance", "douleur_detaillee", "conseil_hygiene_de_vie", "annonce_operation"} <= intentions


def test_bon_sens_du_mot_jambe_humaine():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fr = [{"_id": 50, "keywords": [{"keyword": "jambe"}, {"keyword": "cheval"}], "tags": ["animal", "horse"], "downloads": 900},
              {"_id": 51, "keywords": [{"keyword": "jambe"}], "tags": ["human body", "body part"], "downloads": 3}]
        en = [{"_id": 50, "keywords": [{"keyword": "leg"}], "tags": ["animal"]}, {"_id": 51, "keywords": [{"keyword": "leg"}], "tags": ["human body"]}]
        pages = {f"{cb.ARASAAC_API}/pictograms/all/fr": (json.dumps(fr).encode(), "application/json"),
                 f"{cb.ARASAAC_API}/pictograms/all/en": (json.dumps(en).encode(), "application/json"),
                 cb.ARASAAC_IMG.format(id=50): (b"\x89PNG", "image/png"), cb.ARASAAC_IMG.format(id=51): (b"\x89PNG", "image/png")}
        cb.etape_pictogrammes(t / "b", ReseauSimule(pages), cb.Journal(t / "b" / "journal.json"), objectif=0)
        notions = {l["notion"]: l for l in csv.DictReader((t / "b/02_pictogrammes/notions.csv").open(encoding="utf-8-sig"), delimiter=";")}
        assert notions["JAMBE"]["images"].split()[0].endswith("arasaac_51.png"), notions["JAMBE"]["images"]
        assert "arasaac_50" not in notions["JAMBE"]["images"], "la patte de cheval n'illustre pas la jambe du patient"
        assert "autre sens du mot" in (t / "b/02_pictogrammes/audit/rejets.csv").read_text(encoding="utf-8-sig")


def test_tous_les_pictos_tous_domaines():
    """--tous-pictos : tout le catalogue, y compris hors santé ; contenus sensibles gardés mais rangés à part."""
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fr, en = faux_arasaac()
        fr.append({"_id": 300, "keywords": [{"keyword": "dinosaure"}], "tags": ["dinosaur"], "downloads": 99})
        en.append({"_id": 300, "keywords": [{"keyword": "dinosaur"}], "tags": ["dinosaur"]})
        fr.append({"_id": 301, "keywords": [{"keyword": "voiture"}], "tags": ["transport"], "downloads": 50})
        en.append({"_id": 301, "keywords": [{"keyword": "car"}], "tags": ["transport"]})
        fr.append({"_id": 302, "keywords": [{"keyword": "coup"}], "tags": [], "violence": True, "downloads": 1})
        en.append({"_id": 302, "keywords": [{"keyword": "hit"}], "tags": []})
        png = b"\x89PNG\r\n\x1a\nfaux"
        pages = {f"{cb.ARASAAC_API}/pictograms/all/fr": (json.dumps(fr).encode(), "application/json"),
                 f"{cb.ARASAAC_API}/pictograms/all/en": (json.dumps(en).encode(), "application/json")}
        for it in fr:
            pages[cb.ARASAAC_IMG.format(id=it["_id"])] = (png, "image/png")
        strict = cb.etape_pictogrammes(t / "a", ReseauSimule(pages), cb.Journal(t / "a" / "journal.json"), objectif=0)
        tout = cb.etape_pictogrammes(t / "b", ReseauSimule(pages), cb.Journal(t / "b" / "journal.json"), objectif=0, tous=True, paralleles=3)
        assert tout["images"] == len(fr) > strict["images"], (strict, tout)
        assert list((t / "b/02_pictogrammes").rglob("arasaac_301.png")), "voiture (hors santé) absente"
        assert (t / "b/02_pictogrammes/90_vocabulaire_general/arasaac_300.png").exists()
        assert (t / "b/02_pictogrammes/98_sensible/arasaac_302.png").exists()
        cat = [json.loads(l) for l in (t / "b/02_pictogrammes/catalogue.jsonl").read_text(encoding="utf-8").splitlines()]
        assert next(c for c in cat if c["id"] == "301")["popularite"] == 50
        # relance : rien n'est retéléchargé
        r = cb.etape_pictogrammes(t / "b", ReseauSimule(pages), cb.Journal(t / "b" / "journal.json"), objectif=0, tous=True)
        assert r["telechargees"] == 0 and r["deja_presentes"] == len(fr)
