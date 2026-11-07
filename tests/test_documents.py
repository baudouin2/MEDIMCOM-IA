"""Documents du patient : texte lu directement ; photo lue par le modèle en ligne (faux serveur compatible OpenAI) ;
sans modèle, la photo est jointe et le médecin est prévenu. Les faits extraits sont NON confirmés et vérifiés."""
import base64
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RACINE), str(RACINE / "interface")]
from serveur import Application  # noqa: E402

from medimcom.session import Config  # noqa: E402


def _attendre(cond, delai=5.0):
    fin = time.time() + delai
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_document_texte_lu_et_verifie():
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    app.evenement({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "f", "donnees": {"sexe": "F", "age": 28, "grossesse": True}})
    texte = "Ordonnance du Dr X : Tramadol 50 mg, 2 fois par jour. Antécédent : diabète."
    app.ajouter_document("ordonnance.txt", "ordonnance", "text/plain", base64.b64encode(texte.encode()).decode())
    doc = app.documents[0]
    assert _attendre(lambda: doc["extraction"]["statut"] == "lu")
    assert any(m["nom"] == "tramadol" for m in doc["extraction"]["medicaments"])
    assert _attendre(lambda: "medicaments_declares" in app.ctx.dossier.etat)
    f = app.ctx.dossier.etat["medicaments_declares"]
    assert f["valeur"] == "tramadol" and f["confirme"] is False, "un fait lu dans un document est à confirmer"
    assert any("tramadol" in s["texte"] and "grossesse" in s["texte"].lower() for s in app.ctx.dossier.suggestions.values())
    lignes = [l for l in app.ctx.journal.lignes if l["type"] == "document_ajoute"]
    assert lignes and "sha256" in lignes[0]["contenu"] and "Tramadol" not in json.dumps(lignes[0]["contenu"]), "jamais le contenu au journal"


def test_photo_sans_modele_jointe_et_signalee():
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    app.ajouter_document("photo.jpg", "ordonnance", "image/jpeg", base64.b64encode(b"\xff\xd8\xff faux jpeg").decode())
    doc = app.documents[0]
    assert _attendre(lambda: doc["extraction"]["statut"] == "non_lu") and "Lisez-la" in doc["extraction"]["resume"]


def test_photo_lue_par_le_modele():
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            image = any(p.get("type") == "image_url" for m in corps["messages"] for p in (m["content"] if isinstance(m["content"], list) else []))
            contenu = json.dumps({"type_document": "ordonnance", "medicaments": [{"nom": "Ibuprofène", "dose": "400 mg", "posologie": "3x/j"}],
                                  "maladies": ["ulcère gastrique"], "allergies": [], "resume": "Ordonnance manuscrite" if image else "?"})
            b = json.dumps({"choices": [{"message": {"content": contenu}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        from medimcom.cerveaux import CerveauOpenAI
        from medimcom.documents import lire, nouveau
        doc, octets = nouveau("photo.jpg", "ordonnance", "image/jpeg", base64.b64encode(b"\xff\xd8\xff").decode(), 1)
        cerveau = CerveauOpenAI(f"http://127.0.0.1:{srv.server_address[1]}/v1", "grok-4.7", cle="x")
        ex = lire(doc, octets, cerveau, json.loads((RACINE / "kb" / "regles_uae.json").read_text(encoding="utf-8"))["medicaments"])
        assert ex["statut"] == "lu" and ex["resume"] == "Ordonnance manuscrite" and ex["medicaments"][0]["nom"] == "ibuprofene"
        assert ex["faits"].get("ulcere_digestif") is True, ex
    finally:
        srv.shutdown()


def test_rapport_de_responsabilites():
    from medimcom.responsabilites import rapport
    app = Application(Config(verbeux=False, base="aucune"), asynchrone=False)
    ev = app.evenement
    ev({"type": "echange", "auteur": "medecin", "confirme": True, "texte": "f", "donnees": {"sexe": "M", "age": 40}})
    ev({"type": "texte_medecin", "auteur": "medecin", "texte": "Avez-vous mal ?", "contenu_type": "question"})
    ev({"type": "texte_medecin", "auteur": "medecin", "texte": "vous me plaisez", "contenu_type": "question"})
    d = next(iter(app.ctx.dossier.decisions.values()))
    ev({"type": "validation", "auteur": "medecin", "medecin": "DR-001", "decision_id": d["id"]})
    r = rapport(app.ctx.journal.lignes)
    par_id = {c["id"]: c for c in r["chaines"]}
    assert par_id[d["id"]]["decideur"] == "DR-001" and par_id[d["id"]]["fin"] == "envoyé au patient"
    assert any(c["responsabilite"].startswith("bloqué par le juriste") for c in r["chaines"])
    assert r["bilan"]["decisions_humaines"] >= 1
