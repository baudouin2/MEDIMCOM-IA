"""Recherche hybride (mots-clés + sens) : vectorisation reprise, fusion par rangs, pictogrammes trouvés par le sens ou
malgré une faute, suggestions au médecin, outil des agents, et repli BM25 si le modèle manque (jamais d'arrêt)."""
import json
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RACINE), str(RACINE / "outils"), str(RACINE / "tests"), str(RACINE / "interface")]
from medimcom.vecteurs import EncodeurHachage, MatriceVecteurs, _normaliser  # noqa: E402


class FauxSens:
    """Encodeur « sémantique » de test : des mots différents qui veulent dire la même chose ont le même vecteur."""
    nom = "faux-sens"
    CONCEPTS = [("information", "informé", "renseigner", "savoir"), ("fièvre", "chaud", "température"),
                ("consentement", "accord", "accepter"), ("vomir", "nausée", "vomissement", "vomissements")]

    def encoder(self, textes, role="passage"):
        sortie = []
        for t in textes:
            t = t.lower()
            v = [float(any(m in t for m in c)) for c in self.CONCEPTS] + [0.01]
            sortie.append(_normaliser(v))
        return sortie


def test_matrice_reprise_et_cosinus():
    with tempfile.TemporaryDirectory() as t:
        enc = EncodeurHachage(64)
        el = [("a", "douleur au ventre"), ("b", "fièvre de l'enfant"), ("c", "consentement écrit")]
        m = MatriceVecteurs.construire(el, enc, Path(t), "essai", progression=lambda *_: None)
        assert m.ids == ["a", "b", "c"] and m.matrice.shape == (3, 64)
        vus = []
        MatriceVecteurs.construire(el + [("d", "toux la nuit")], enc, Path(t), "essai", progression=vus.append)
        assert "3 déjà encodés, 1 à encoder" in vus[0], "la reprise réencode tout"
        res = MatriceVecteurs.charger(Path(t), "essai", enc.nom).chercher(enc.encoder(["fièvre enfant"])[0], 2)
        assert res[0][0] == "b" and res[0][1] > res[1][1]


def test_corpus_hybride_trouve_par_le_sens():
    from medimcom.base_v2 import Corpus
    from test_base_v2_branchement import constituer
    with tempfile.TemporaryDirectory() as t:
        base = constituer(Path(t))
        corpus = Corpus(base)
        enc = FauxSens()
        for c, el in corpus.elements_a_vectoriser().items():
            if el:
                MatriceVecteurs.construire(el, enc, base / "07_vecteurs", c, progression=lambda *_: None)
        question = "comment se renseigner"                # aucun mot commun avec « droit à l'information »
        assert corpus.chercher(question, 3, methode="bm25") == []
        bilan = corpus.brancher_vecteurs(base / "07_vecteurs", enc)
        assert bilan.get("juridique")
        res = corpus.chercher(question, 3)
        assert res and "information" in res[0]["texte"].lower() and res[0]["pourquoi"]["rang_sens"] == 1
        assert res[0]["pourquoi"]["methode"] == "hybride" and res[0]["pourquoi"]["cosinus"] > 0.5


def test_pictogrammes_hybrides_et_suggestions():
    from medimcom import bibliotheque as B
    from medimcom.base_v2 import LexiqueBaseV2, charger_pictogrammes
    from test_base_v2_branchement import constituer
    sauve_v, sauve_e = dict(B.VOCABULAIRE), dict(B.EXTERNES)
    try:
        with tempfile.TemporaryDirectory() as t:
            base = constituer(Path(t))
            lx = LexiqueBaseV2(base, charger_pictogrammes(base))
            assert lx.chercher("douleurs", 3)[0]["id"] == "DOULEUR", "le libellé exact doit passer en tête"
            assert lx.chercher("fievre", 3)[0]["id"] == "FIEVRE"
            assert any(r["id"] == "BRULURE" for r in lx.chercher("brulure", 5))
            assert "consentment" not in lx.suggerer(["consentment"]) or "CONSENTEMENT" in lx.suggerer(["consentment"])["consentment"]
            # par le sens : « il a très chaud » ne partage aucun mot avec « fièvre »
            enc = FauxSens()
            MatriceVecteurs.construire(lx.recherche.elements_a_vectoriser(), enc, base / "07_vecteurs", "pictogrammes",
                                       progression=lambda *_: None)
            assert lx.recherche.brancher_vecteurs(base / "07_vecteurs", enc) > 0
            lx.recherche.seuil_sens = 0.5
            r = lx.chercher("il a très chaud", 5)
            assert any(x["id"] == "FIEVRE" and x["pourquoi"]["sens"] and not x["pourquoi"]["mots"] for x in r)
            assert lx.recherche.brancher_vecteurs(base / "07_vecteurs", EncodeurHachage()) == 0, "le hachage n'est pas du sens"
    finally:
        B.VOCABULAIRE.clear(); B.VOCABULAIRE.update(sauve_v)
        B.EXTERNES.clear(); B.EXTERNES.update(sauve_e)


def test_repli_bm25_si_modele_absent_et_api():
    import os
    import threading
    import urllib.request
    from medimcom import bibliotheque as B
    from medimcom.session import Config
    from serveur import Application, creer_serveur
    from test_base_v2_branchement import constituer
    sauve_v, sauve_e = dict(B.VOCABULAIRE), dict(B.EXTERNES)
    ancien = os.environ.get("MEDIMCOM_BASE")
    try:
        with tempfile.TemporaryDirectory() as t:
            base = constituer(Path(t))
            os.environ["MEDIMCOM_BASE"] = str(base)
            # modèle introuvable : la consultation démarre quand même, en BM25, et le journal le dit
            app = Application(Config(verbeux=False, recherche="ollama:modele-inexistant-xyz", pays="CM"), asynchrone=False)
            conf = next(l for l in app.ctx.journal.lignes if l["type"] == "configuration")["contenu"]
            assert "erreur" in conf["recherche_dans_la_base"]
            assert app.ctx.corpus.chercher("information", 1)
            # l'outil des agents et la route de l'interface
            a = next(x for x in app.agents if x.nom == "traducteur")
            res = a.executer("chercher_pictogrammes", {"idee": "douleur"})
            assert isinstance(res, list) and res[0]["id"] == "DOULEUR"
            srv = creer_serveur(app, port=0)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                j = json.loads(op.open(f"http://127.0.0.1:{srv.server_port}/api/pictogrammes/chercher?q=fievre").read())
                assert j["resultats"][0]["id"] == "FIEVRE" and j["sens"] is False
            finally:
                srv.shutdown()
    finally:
        if ancien is None:
            os.environ.pop("MEDIMCOM_BASE", None)
        else:
            os.environ["MEDIMCOM_BASE"] = ancien
        B.VOCABULAIRE.clear(); B.VOCABULAIRE.update(sauve_v)
        B.EXTERNES.clear(); B.EXTERNES.update(sauve_e)
