"""CLE_API.txt: one pasted key is enough, the provider (free or paid) is recognised automatically, and each
API's quirks are handled (Claude refuses "temperature" < 1, some OpenAI models too)."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from medimcom import cle_api  # noqa: E402
from medimcom.session import FOURNISSEURS, Config  # noqa: E402

VARIABLES = [f["variable_cle"] for f in FOURNISSEURS.values()]


@pytest.fixture(autouse=True)
def _env_propre(monkeypatch, tmp_path):
    sauve = dict(os.environ)                    # appliquer() writes in os.environ: everything is restored afterwards
    for v in VARIABLES:
        os.environ.pop(v, None)
    monkeypatch.setattr("medimcom.session.ENV_PERSONNEL", tmp_path / "perso_env")
    monkeypatch.setattr("medimcom.session.RACINE", tmp_path)          # no project .env
    yield
    os.environ.clear()
    os.environ.update(sauve)


def _fichier(tmp_path, **lignes):
    p = tmp_path / "CLE_API.txt"
    p.write_text("# commentaire\n" + "".join(f"{k}={v}\n" for k, v in lignes.items()), encoding="utf-8")
    return p


@pytest.mark.parametrize("cle,attendu", [
    ("gsk_FAUSSE0123456789abcdef", "groq"), ("sk-or-v1-FAUSSE0123456789", "openrouter"), ("AIzaFAUSSE0123456789abc", "gemini"),
    ("xai-FAUSSE0123456789abcdef", "xai"), ("sk-ant-api03-FAUSSE012345", "anthropic"), ("sk-proj-FAUSSE0123456789", "openai"),
    ("sk-FAUSSE0123456789abcdefgh", "openai")])
def test_fournisseur_reconnu_au_debut_de_la_cle(tmp_path, cle, attendu):
    cfg = Config()
    texte = cle_api.appliquer(cfg, _fichier(tmp_path, CLE=cle, PATIENTS_FICTIFS="oui"))
    assert cfg.fournisseur == attendu and cfg.donnees_fictives, texte
    assert os.environ[FOURNISSEURS[attendu]["variable_cle"]] == cle
    assert cle not in texte, "la clé ne s'affiche jamais"


def test_cas_particuliers(tmp_path):
    cfg = Config()
    assert "no API key" in cle_api.appliquer(cfg, _fichier(tmp_path, CLE="collez_votre_cle_ici", PATIENTS_FICTIFS="oui"))
    assert cfg.fournisseur is None
    cfg = Config()
    assert "FOURNISSEUR=mistral" in cle_api.appliquer(cfg, _fichier(tmp_path, CLE="AbCdEf0123456789AbCdEf0123456789"))
    cfg = Config()
    cle_api.appliquer(cfg, _fichier(tmp_path, CLE="AbCdEf0123456789AbCdEf0123456789", FOURNISSEUR="mistral", PATIENTS_FICTIFS="oui",
                                    MODELE="mistral-small-latest"))
    assert cfg.fournisseur == "mistral" and cfg.modele == "mistral-small-latest"
    cfg = Config()
    assert "PATIENTS_FICTIFS" in cle_api.appliquer(cfg, _fichier(tmp_path, CLE="gsk_FAUSSE0123456789abcdef", PATIENTS_FICTIFS="non"))
    assert cfg.fournisseur is None, "sans attestation « patients fictifs », pas de modèle en ligne"
    cfg = Config()
    cle_api.appliquer(cfg, _fichier(tmp_path, CLE="gsk_FAUSSE0123456789abcdef  # ma clé", CLE_SECOURS="xai-FAUSSE0123456789abcdef",
                                    PATIENTS_FICTIFS="oui"))
    assert cfg.fournisseur == "groq" and cfg.secours == ["xai"] and os.environ["GROQ_API_KEY"] == "gsk_FAUSSE0123456789abcdef"


def test_fichier_cree_depuis_l_exemple(tmp_path, monkeypatch):
    exemple = tmp_path / "CLE_API.exemple.txt"
    exemple.write_text((RACINE / "CLE_API.exemple.txt").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(cle_api, "FICHIER", tmp_path / "CLE_API.txt")
    monkeypatch.setattr(cle_api, "EXEMPLE", exemple)
    assert cle_api.choisir()["fournisseur"] is None and (tmp_path / "CLE_API.txt").exists()
    assert "CLE_API.txt" in (RACINE / ".gitignore").read_text(), "le fichier de clé ne doit jamais partir sur GitHub"


def _serveur(regle):
    vus = []

    class H(BaseHTTPRequestHandler):
        def _r(self, d, code=200):
            b = json.dumps(d).encode()
            self.send_response(code); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            vus.append(("GET", dict(self.headers), None))
            self._r({"data": [{"id": "m"}]})

        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            vus.append(("POST", dict(self.headers), corps))
            erreur = regle(corps)
            if erreur:
                return self._r({"error": {"message": erreur}}, 400)
            self._r({"choices": [{"message": {"role": "assistant", "content": "ok"}}]})

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, vus


def test_claude_sans_temperature_et_cle_en_x_api_key():
    from medimcom.cerveaux import CerveauOpenAI
    srv, vus = _serveur(lambda c: "temperature: must be 1" if c.get("temperature", 1) != 1 else None)
    try:
        c = CerveauOpenAI(f"http://127.0.0.1:{srv.server_address[1]}/v1", "m", cle="sk-ant-FAUSSE")
        c.base = c.base.replace("127.0.0.1", "127.0.0.1")
        c.anthropic = c.sans_temperature = True          # what the address api.anthropic.com does
        assert c.verifier()[0] and c.chat([{"role": "user", "content": "x"}], [])["content"] == "ok"
        post = [v for v in vus if v[0] == "POST"][-1]
        assert "temperature" not in post[2] and post[2]["max_tokens"] and post[1].get("x-api-key") == "sk-ant-FAUSSE"
    finally:
        srv.shutdown()


def test_modele_qui_refuse_temperature_reessai_sans():
    from medimcom.cerveaux import CerveauOpenAI
    srv, vus = _serveur(lambda c: "Unsupported value: 'temperature' does not support 0.0 with this model" if "temperature" in c else None)
    try:
        c = CerveauOpenAI(f"http://127.0.0.1:{srv.server_address[1]}/v1", "m", cle="sk-FAUSSE")
        assert c.chat([{"role": "user", "content": "x"}], [])["content"] == "ok" and c.sans_temperature
    finally:
        srv.shutdown()


def test_base_au_format_du_code_de_reference_uit(tmp_path):
    """kb/InputDocs: subfolders = document_category, one .md file per source, Inputs.md manifest (ignored at ingestion)."""
    sys.path.insert(0, str(RACINE / "kb" / "outils"))
    import exporter_inputdocs as E
    r = E.exporter(tmp_path / "InputDocs")
    sources = json.loads((RACINE / "kb" / "sources.json").read_text(encoding="utf-8"))["sources"]
    fichiers = list((tmp_path / "InputDocs" / "AI_Strategies").glob("*.md"))
    assert r["sources"] == len(sources) == len(fichiers) and len({f.name for f in fichiers}) == len(fichiers)
    assert (tmp_path / "InputDocs" / "Inputs.md").exists() and len(list((tmp_path / "InputDocs" / "AI_Use_Cases").glob("*.md"))) == 2
    assert all(f.name.isascii() for f in fichiers), "noms de fichiers sans accents"
    loi = next(f for f in fichiers if "Medical_Liability" in f.name).read_text(encoding="utf-8")
    assert "uaelegislation.gov.ae" in loi and "Art. 3" in loi
    # the version published in the repository is up to date
    publie = sorted(p.name for p in (RACINE / "kb" / "InputDocs" / "AI_Strategies").glob("*.md"))
    assert publie == sorted(f.name for f in fichiers), "relancer : python kb/outils/exporter_inputdocs.py"


def test_fichier_reduit_a_la_cle(tmp_path):
    """Feedback of 9 November: a file replaced by the single line CLE=… (or by the key alone) must work."""
    p = tmp_path / "CLE_API.txt"
    for contenu in ("CLE=gsk_FAUSSE0123456789abcdef\n", "﻿gsk_FAUSSE0123456789abcdef\r\n"):
        p.write_text(contenu, encoding="utf-8")
        cfg = Config()
        texte = cle_api.appliquer(cfg, p)
        assert cfg.fournisseur == "groq" and cfg.donnees_fictives and "FICTITIOUS" in texte, (contenu, texte)
