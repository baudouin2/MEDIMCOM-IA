"""Latency: with a slow online model, the doctor's and patient's clicks go through at once, the assistant reasons in
the background without losing anything, and the connection to the model is kept open."""
import http.server
import json
import sys
import threading
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "interface"))
from medimcom.cerveaux import CerveauOpenAI  # noqa: E402
from medimcom.session import Config  # noqa: E402
from serveur import Application  # noqa: E402


def _faux_modele(delai: float):
    """Fake OpenAI-compatible service: reads the record then finishes; notes each call and the connection used."""
    appels = []

    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True        # like a real service: no artificial wait between headers and body

        def _json(self, obj):
            r = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(r)))
            self.end_headers()
            self.wfile.write(r)

        def do_GET(self):
            self._json({"data": [{"id": "m"}]})

        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            appels.append({"connexion": self.client_address[1], "messages": corps["messages"]})
            time.sleep(delai)
            if any(m["role"] == "tool" for m in corps["messages"]):
                appel = {"id": "t", "type": "function", "function": {"name": "terminer", "arguments": "{}"}}
            else:
                appel = {"id": "l", "type": "function", "function": {"name": "lire_dossier", "arguments": "{}"}}
            self._json({"choices": [{"message": {"content": "", "tool_calls": [appel]}}]})

        def log_message(self, *a):
            pass

    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return serveur, appels


def _attendre(cond, limite=30.0):
    t0 = time.time()
    while not cond():
        assert time.time() - t0 < limite, "délai dépassé"
        time.sleep(0.02)
    return time.time() - t0


def test_clics_immediats_et_reflexion_en_arriere_plan():
    serveur, appels = _faux_modele(1.0)
    try:
        cfg = Config(verbeux=False, mode="openai", url=f"http://127.0.0.1:{serveur.server_port}/v1", modele="m",
                     agents_ia=["assistant"], base="aucune")
        app = Application(cfg, asynchrone=True)
        d = app.ctx.dossier
        app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous mal au ventre ?", "contenu_type": "question"})
        assert _attendre(lambda: any(x["statut"] == "attente_validation" for x in d.decisions.values())) < 0.5
        _attendre(lambda: app.reflexion_en_cours, 5)                    # the assistant queries the model…
        prop = next(x for x in d.decisions.values() if x["statut"] == "attente_validation")
        app.evenement({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": prop["id"]})
        assert _attendre(lambda: prop["statut"] == "envoye") < 0.5, "la validation a attendu le modèle"
        app.evenement({"type": "reponse_patient", "auteur": "patient", "pictogrammes": ["OUI"]})
        _attendre(lambda: app.en_cours == 0)
        assert app.vue_medecin()["reflexion_en_cours"] is True
        # … then resumes: the patient's answer, which arrived during its reasoning, is not lost for it.
        _attendre(lambda: not app.reflexion_en_cours and not app._a_reflechir and app.en_cours == 0)
        vus = " ".join(json.dumps(a["messages"], ensure_ascii=False) for a in appels)
        assert "reponse_patient" in vus or "OUI" in vus, "l'assistant n'a jamais vu la réponse du patient"
        assert len(appels) <= 6, f"trop d'appels au modèle : {len(appels)}"
        assert any(l["type"] == "appel_modele" and "duree_s" in l["contenu"] for l in app.ctx.journal.lignes)
    finally:
        serveur.shutdown()


def test_connexion_gardee_ouverte(monkeypatch):
    for v in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(v, raising=False)
    serveur, appels = _faux_modele(0.0)
    try:
        c = CerveauOpenAI(f"http://127.0.0.1:{serveur.server_port}/v1", "m", "cle")
        for _ in range(3):
            c.chat([{"role": "user", "content": "x"}], [])
        assert len(appels) == 3 and len({a["connexion"] for a in appels}) == 1, "une nouvelle connexion à chaque appel"
    finally:
        serveur.shutdown()
