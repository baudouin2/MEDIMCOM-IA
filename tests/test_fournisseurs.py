"""Online API providers (free tiers): presets, "fictitious data" safeguard, fallback, HTTP 429 quota."""
import http.server
import json
import sys
import threading
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from medimcom.cerveaux import CerveauOpenAI, CerveauSecours  # noqa: E402
from medimcom.session import FOURNISSEURS, Config, creer_cerveau, preparer  # noqa: E402


def test_prereglages(monkeypatch=None):
    import os
    os.environ["GROQ_API_KEY"] = "test"
    cfg = preparer(Config(fournisseur="groq", donnees_fictives=True))
    assert cfg.mode == "openai" and cfg.url == FOURNISSEURS["groq"]["url"] and cfg.modele == FOURNISSEURS["groq"]["modele"]
    cfg = preparer(Config(fournisseur="groq", modele="qwen/qwen3.6-27b", donnees_fictives=True))
    assert cfg.modele == "qwen/qwen3.6-27b", "un modèle choisi explicitement n'est pas remplacé"
    try:
        preparer(Config(fournisseur="groq"))
        raise AssertionError("un modèle en ligne doit exiger --donnees-fictives")
    except SystemExit as e:
        assert "fictitious" in str(e)
    for f in FOURNISSEURS.values():
        assert f["url"].startswith("https://") and f["variable_cle"].endswith("_API_KEY") and f["console"].startswith("https://")


class Panne:
    nom, modele = "panne", "x"

    def chat(self, messages, outils):
        raise RuntimeError("HTTP 429 quota épuisé")

    def verifier(self):
        return False, "quota"


class Repond:
    nom, modele = "secours", "y"

    def chat(self, messages, outils):
        return {"content": "ok", "reflexion": "", "tool_calls": []}

    def verifier(self):
        return True, "ok"


def test_secours_passe_au_suivant():
    c = CerveauSecours([Panne(), Repond()])
    assert c.chat([], [])["content"] == "ok" and c.dernier == "secours"
    assert c.verifier()[0] is True
    try:
        CerveauSecours([Panne(), Panne()]).chat([], [])
        raise AssertionError
    except RuntimeError as e:
        assert "all providers failed" in str(e)


def test_secours_construit_depuis_la_config():
    import os
    os.environ["GROQ_API_KEY"], os.environ["OPENROUTER_API_KEY"] = "a", "b"
    cfg = preparer(Config(fournisseur="groq", secours=["openrouter"], donnees_fictives=True))
    c = creer_cerveau(cfg, cfg.modele)
    assert isinstance(c, CerveauSecours) and len(c.cerveaux) == 2


def test_quota_429_puis_succes():
    appels = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            appels.append(1)
            self.rfile.read(int(self.headers["Content-Length"]))
            if len(appels) == 1:
                self.send_response(429)
                self.send_header("Retry-After", "0.1")
                self.end_headers()
                return
            corps = json.dumps({"choices": [{"message": {"content": "bonjour", "tool_calls": []}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, *a):
            pass

    serveur = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        c = CerveauOpenAI(f"http://127.0.0.1:{serveur.server_port}/v1", "m", "cle")
        assert c.chat([{"role": "user", "content": "x"}], [])["content"] == "bonjour" and len(appels) == 2
    finally:
        serveur.shutdown()


def test_cle_lue_dans_env(tmp_path=None):
    import os
    import tempfile
    from medimcom.session import charger_env
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / ".env"
        f.write_text("# commentaire\nexport MEDIMCOM_TEST_CLE=abc\nMEDIMCOM_TEST_VIDE=\napi key = xai-test\n", encoding="utf-8")
        os.environ.pop("XAI_API_KEY", None)
        os.environ.pop("MEDIMCOM_TEST_CLE", None)
        assert charger_env(f) == 2 and os.environ["MEDIMCOM_TEST_CLE"] == "abc" and os.environ["XAI_API_KEY"] == "xai-test"
        os.environ.pop("XAI_API_KEY", None)
        os.environ["MEDIMCOM_TEST_CLE"] = "deja"
        charger_env(f)
        assert os.environ["MEDIMCOM_TEST_CLE"] == "deja", "une variable déjà définie n'est pas écrasée"
    assert ".env" in (RACINE / ".gitignore").read_text(encoding="utf-8")


def test_effort_retire_si_refuse():
    corps_recus = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            corps_recus.append(corps)
            if "reasoning_effort" in corps:
                self.send_response(400)
                self.end_headers()
                return
            r = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(r)

        def log_message(self, *a):
            pass

    serveur = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        c = CerveauOpenAI(f"http://127.0.0.1:{serveur.server_port}/v1", "m", "k", effort="low")
        assert c.chat([{"role": "user", "content": "x"}], [])["content"] == "ok"
        assert corps_recus[0]["reasoning_effort"] == "low" and "reasoning_effort" not in corps_recus[1] and c.effort is None
    finally:
        serveur.shutdown()
