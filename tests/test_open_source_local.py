"""Local version with open-source models: Ollama (on this computer, nothing leaves) and Groq (Whisper for dictation).
The Ollama server is simulated: we check that the agents call it with their tools, that a prescription photo is read
by the local vision model, and that the screen says who runs the model."""
import base64
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RACINE), str(RACINE / "interface")]


def test_moteur_de_dictee_et_nom_du_fournisseur(monkeypatch):
    from serveur import fournisseur_lisible, moteur_dictee
    for v in ("GROQ_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    assert moteur_dictee(SimpleNamespace(fournisseur=None)) == "navigateur"
    monkeypatch.setenv("GROQ_API_KEY", "g")
    assert moteur_dictee(SimpleNamespace(fournisseur=None)) == "groq"
    monkeypatch.setenv("XAI_API_KEY", "x")
    assert moteur_dictee(SimpleNamespace(fournisseur="xai")) == "xai"
    assert moteur_dictee(SimpleNamespace(fournisseur="groq")) == "groq"
    assert "sur cet ordinateur" in fournisseur_lisible(SimpleNamespace(mode="ollama", fournisseur=None))
    assert "open source" in fournisseur_lisible(SimpleNamespace(mode="openai", fournisseur="groq"))


def test_ollama_local_agents_et_photo(monkeypatch):
    pytest.importorskip("ollama")
    recus = []

    class H(BaseHTTPRequestHandler):
        def _r(self, d):
            b = json.dumps(d).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            self._r({"models": [{"name": "qwen3:8b", "model": "qwen3:8b"}, {"name": "qwen3-vl:8b", "model": "qwen3-vl:8b"}]})

        def do_POST(self):
            d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recus.append(d)
            c = ('{"medicaments":[{"nom":"Doliprane","dose":"1 g","posologie":"3 fois par jour"}],"maladies":[],"allergies":[],'
                 '"resume":"Ordonnance","lisibilite":"bonne"}') if d["messages"][-1].get("images") else "Rien à ajouter."
            self._r({"model": d["model"], "message": {"role": "assistant", "content": c}, "done": True})

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("OLLAMA_HOST", f"http://127.0.0.1:{srv.server_address[1]}")
        monkeypatch.setenv("MEDIMCOM_MODELE_VISION", "qwen3-vl:8b")
        from serveur import Application

        from medimcom.session import Config
        app = Application(Config(mode="ollama", modele="qwen3:8b", verbeux=False, base="aucune"), asynchrone=False)
        etat = app._etat_modele()
        assert etat["disponible"] and "sur cet ordinateur" in etat["fournisseur"] and etat["message"] != "en ligne"
        app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous mal au ventre ?", "contenu_type": "question"})
        assert recus and recus[0].get("tools"), "l'assistant doit appeler le modèle local avec ses outils"
        app.ajouter_document("ordo.jpg", "ordonnance", "image/jpeg", base64.b64encode(b"\xff\xd8\xff" + b"x" * 2000).decode())
        for _ in range(50):
            if app.documents[-1]["extraction"]["statut"] != "en_cours":
                break
            time.sleep(0.1)
        ex = app.documents[-1]["extraction"]
        assert ex["statut"] == "lu" and "local" in ex["par"] and "qwen3-vl:8b" in ex["par"], ex
        assert [m["nom"] for m in ex["medicaments"]] == ["paracetamol"], "Doliprane = paracétamol"
        assert [d["model"] for d in recus if d["messages"][-1].get("images")] == ["qwen3-vl:8b"]
    finally:
        srv.shutdown()


def test_ollama_sans_modele_de_vision_le_dit(monkeypatch):
    pytest.importorskip("ollama")
    monkeypatch.delenv("MEDIMCOM_MODELE_VISION", raising=False)
    from medimcom.cerveaux import CerveauOllama
    with pytest.raises(RuntimeError, match="qwen3-vl"):
        CerveauOllama("qwen3:8b").lire_document(b"img", "image/jpeg", "consigne")


def test_cause_lisible_des_pannes_du_modele():
    import socket
    import ssl
    import urllib.error

    from medimcom.cerveaux import expliquer, lire_erreur
    assert "Internet" in expliquer(urllib.error.URLError(socket.gaierror(-2, "Name or service not known")))
    assert "certifi" in expliquer(urllib.error.URLError(ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED]")))
    assert "slow" in expliquer(TimeoutError("timed out"))
    assert "quota" in expliquer(RuntimeError("HTTP 429 : Rate limit reached on tokens per day"))
    assert "credits" in expliquer(RuntimeError("HTTP 403 : Your team has used all available credits"))
    assert "retired" in expliquer(RuntimeError("HTTP 400 : The model `x` has been decommissioned"))
    import io
    e = urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b'{"error":{"message":"Invalid API Key gsk_FAUSSE_cle_de_test"}}'))
    assert "FAUSSE" not in lire_erreur(e), "une clé Groq (gsk_…) ne doit jamais s'afficher"


def test_cle_du_projet_gardee_dans_la_copie_personnelle(tmp_path):
    from medimcom.session import memoriser_cles
    projet, perso = tmp_path / ".env", tmp_path / "config" / "medimcom" / "env"
    projet.write_text("# commentaire\nGROQ_API_KEY=gsk_FAUSSE_A\n", encoding="utf-8")
    assert memoriser_cles(projet, perso) == ["GROQ_API_KEY"]
    assert "GROQ_API_KEY=gsk_FAUSSE_A" in perso.read_text() and oct(perso.stat().st_mode & 0o777) == "0o600"
    assert memoriser_cles(projet, perso) == [], "déjà enregistrée : rien à refaire"
    perso.write_text(perso.read_text() + "XAI_API_KEY=xai-FAUSSE\n")
    projet.write_text("GROQ_API_KEY=gsk_FAUSSE_B\n", encoding="utf-8")
    assert memoriser_cles(projet, perso) == ["GROQ_API_KEY"]
    t = perso.read_text()
    assert "gsk_FAUSSE_B" in t and "gsk_FAUSSE_A" not in t and "XAI_API_KEY=xai-FAUSSE" in t, "les autres clés sont gardées"


def test_pare_feu_cloudflare_1010_signature_python_refusee():
    """Feedback of 9 November: Groq answered curl but refused the application (HTTP 403 "error code: 1010") because
    urllib announced itself as "Python-urllib". Requests now carry their own identity."""
    from medimcom.cerveaux import CerveauOpenAI, expliquer
    vus = []

    class H(BaseHTTPRequestHandler):
        def _r(self, d, code=200):
            b = (d if isinstance(d, bytes) else json.dumps(d).encode())
            self.send_response(code); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def _bloque(self):
            ua = self.headers.get("User-Agent") or ""
            vus.append(ua)
            if not ua or ua.startswith("Python-urllib"):
                self._r(b"error code: 1010", 403)
                return True
            return False

        def do_GET(self):
            if not self._bloque():
                self._r({"data": [{"id": "qwen/qwen3.8-27b"}]})

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            if not self._bloque():
                self._r({"choices": [{"message": {"role": "assistant", "content": "Bonjour"}}]})

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = CerveauOpenAI(f"http://127.0.0.1:{srv.server_address[1]}/v1", "qwen/qwen3.8-27b", cle="gsk_FAUSSE")
        assert c.verifier() == (True, "ok"), vus
        assert c.chat([{"role": "user", "content": "test"}], [])["content"] == "Bonjour"
        assert all(v.startswith("MEDIMCOM-IA") for v in vus), vus
    finally:
        srv.shutdown()
    assert "Cloudflare" in expliquer(RuntimeError("HTTP 403 : error code: 1010"))
