"""Local interface of MEDIMCOM IA: doctor screen + patient screen, connected to the agents.

    python interface/serveur.py                                   # prints the private link of the doctor screen
                                                                  # and http://127.0.0.1:8000/patient
    python interface/serveur.py --demo scenarios/grossesse.json   # "Next step" button (for the video)
    python interface/serveur.py --mode ollama --modele qwen3:8b   # real agents with a local model
    python interface/serveur.py --hote 0.0.0.0                    # patient tablet on the same Wi-Fi network (see warning)

Without --mode or --fournisseur, the API key of CLE_API.txt chooses the language model (see docs/GUIDE_CLE_API.md).
No dependency: Python standard library. FICTITIOUS data only.
Security: listens on 127.0.0.1 by default; the doctor screen and its actions require a secret token (link printed
at start-up); every write request must be JSON from the same origin; only localhost and IP addresses are
accepted as host name (protection against "DNS rebinding"). The patient screen has no token: it can only send
pictograms (reported as they are by the translator) and a limited number of documents.
"""
import sys as _sys
for _flux in (_sys.stdout, _sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

import argparse
import hmac
import html
import io
import queue
import ipaddress
import json
import os
import re
import secrets
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
WEB = ICI / "web" / "dist"            # compiled React interface (npm run build in interface/web)
CLASSIQUE = ICI / "classique"         # simple HTML pages, used if the React interface is not built
TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2",
         ".woff": "font/woff", ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json"}
CSP_PAGE = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
sys.path.insert(0, str(RACINE))

from medimcom.bibliotheque import CATALOGUE, VOCABULAIRE, connu, credits, libelle, svg  # noqa: E402
from medimcom.cerveaux import CerveauSimule  # noqa: E402
from medimcom.session import Config, construire  # noqa: E402

PALETTE_DEMO = {
    "reponses": ["OUI", "NON", "NE_PAS", "ACCORD", "COMPRENDRE", "QUESTION", "ATTENDRE", "STOP", "AIDE", "REPETER"],
    "corps": ["TETE", "POITRINE", "VENTRE", "GORGE", "OREILLE", "OEIL", "DENT", "DOS", "BRAS", "JAMBE", "PIED", "MAIN",
              "COEUR", "PEAU", "MOI"],
    "symptomes": ["DOULEUR", "FIEVRE", "TOUX", "VOMIR", "RESPIRER", "SANG", "ALLERGIE", "ENCEINTE", "VERTIGE", "FATIGUE",
                  "DIARRHEE", "CONSTIPATION", "DEMANGEAISON", "BRULURE", "GONFLEMENT", "RHUME", "EVANOUISSEMENT"],
    "ressenti": ["PEUR", "INQUIET", "TRISTE", "CONTENT", "COLERE"],
    "intensite": [f"CHIFFRE:{i}" for i in range(0, 11)],
    "temps": ["MATIN", "MIDI", "SOIR", "NUIT", "HEURE", "JOUR", "SEMAINE", "MOIS", "AN", "AVANT", "APRES", "PLUS", "MOINS"],
}


def palette(notions: dict | None = None) -> dict:
    """Patient palette: only the available pictograms (demo icons or installed bases).
    With base_v2, each tab is completed by the consultation-vocabulary concepts that have an image."""
    p = {k: [i for i in v if connu(i)] for k, v in PALETTE_DEMO.items()}
    if notions:
        from medimcom.base_v2 import ONGLETS_PATIENT, palette_patient
        for onglet, ids in palette_patient(notions).items():
            p[onglet] = list(dict.fromkeys(p.get(onglet, []) + ids))
        ordre = list(ONGLETS_PATIENT) + [k for k in p if k not in ONGLETS_PATIENT]   # screen order: answers, body, pain…
        p = {k: p[k] for k in ordre if k in p}
    return {k: v for k, v in p.items() if v}
CLES_FERMEES = ["grossesse", "fievre", "douleur", "nausees", "consentement_traitement", "allergies", "traitements_en_cours",
                "informe_usage_ia"]
# Welcome message: the patient knows an AI helps the doctor, that the doctor decides, and that they may refuse (DHA
# 2021, obligation IA-INFORMER). Their YES / NO answer is recorded (informe_usage_ia).
MESSAGE_ACCUEIL = ("Bonjour. Je suis votre médecin. Un ordinateur m'aide à traduire. C'est moi qui décide. "
                   "Vous pouvez dire non. Vous êtes d'accord ?")


class _SortieParFil(io.TextIOBase):
    """Standard output specific to each thread: the (online) assistant and the fast agents work at the same time,
    and each captures its own messages without mixing them (redirect_stdout is not made for that)."""

    def __init__(self, origine):
        self.origine, self.local = origine, threading.local()

    def write(self, texte):
        return (getattr(self.local, "tampon", None) or self.origine).write(texte)

    def flush(self):
        (getattr(self.local, "tampon", None) or self.origine).flush()


@contextmanager
def capturer():
    if not isinstance(sys.stdout, _SortieParFil):
        sys.stdout = _SortieParFil(sys.stdout)
    sortie, tampon = sys.stdout, io.StringIO()
    avant = getattr(sortie.local, "tampon", None)
    sortie.local.tampon = tampon
    try:
        yield tampon
    finally:
        sortie.local.tampon = avant


class Application:
    """One ongoing consultation. Every change goes through `evenement` (under lock)."""

    def __init__(self, cfg: Config, demo: Path | None = None, interface: str = "auto", asynchrone: bool = False):
        self.cfg, self.demo_chemin = cfg, demo
        self.react = interface == "react" or (interface == "auto" and (WEB / "index.html").exists())
        self.verrou = threading.RLock()
        # access to the doctor screen (link printed at start-up); when hosted, MEDIMCOM_JETON keeps the link from one
        # start to the next
        fixe = os.environ.get("MEDIMCOM_JETON", "").strip()
        if fixe and len(fixe) < 16:
            raise SystemExit("MEDIMCOM_JETON too short: at least 16 characters (e.g. python3 -c \"import secrets; print(secrets.token_urlsafe(24))\").")
        self.jeton = fixe or secrets.token_urlsafe(18)
        # Asynchronous mode (real server): a click only adds the event to a queue; the agents work in the background and
        # the screens read the latest snapshot of the consultation, without waiting for the agents to finish.
        self.asynchrone = asynchrone
        self.file: queue.Queue = queue.Queue()
        self.en_cours = 0
        self._compteur = threading.Lock()   # short lock, distinct from the agents' one: a click must never wait for the AI
        self.derniere_erreur = None
        self.reflexion_en_cours = False     # the online agent (assistant) reasons in the background
        self._a_reflechir = False           # reasoning remains to be done once no human is waiting
        self._photo_medecin = self._photo_patient = None
        self.reinitialiser()
        self._reveil = threading.Event()
        if asynchrone:
            threading.Thread(target=self._travailleur, daemon=True, name="agents").start()
            threading.Thread(target=self._reflecteur, daemon=True, name="reflexion").start()

    def reinitialiser(self):
        with self.verrou:
            self.ctx, self.agents, self.orch = construire(self.cfg)
            self.session = secrets.token_hex(4)          # changes with every new consultation
            self._recents = {}                            # anti-duplicates: starts from scratch with the consultation
            self.demo = json.loads(self.demo_chemin.read_text(encoding="utf-8")) if self.demo_chemin else None
            self.demo_index = 0
            if self.demo:
                self.ctx.journal.ajouter("coordinateur", "scenario", {"titre": self.demo["titre"]})
            self.orch.apres_tour = self._photographier     # the screen updates after each agent action
            # Doctor screen: the assistant's questions stay in the Assistant tab until the doctor picks them (except in
            # a demo scenario, which validates them step by step)
            self.ctx.questions_assistant_auto = bool(self.demo)
            self.messages_masques = set()
            self.documents, self._octets_documents = [], {}         # patient documents attached by the doctor or sent by the patient
            # "Slow" agents: those that query an online model. In asynchronous mode they play AFTER the fast agents and
            # give way as soon as a human clicks: a click never waits for the model's reasoning.
            self.lents = frozenset(a.nom for a in self.agents if not isinstance(a.cerveau, CerveauSimule)) if self.asynchrone else frozenset()
            self.ctx.interrompre = (lambda: self.en_cours > 0) if self.asynchrone else None
            self.ctx.attente_modele = self._hors_verrou if self.asynchrone else None
            self._a_reflechir = False
            self._photographier()

    # ------------------------------------------------------------------ events
    def evenement(self, evt: dict) -> str:
        if self.asynchrone and threading.current_thread().name not in ("agents", "reflexion"):
            with self._compteur:            # certainly not self.verrou: it is held during all the agents' work
                self.en_cours += 1
            self.file.put(evt)
            return "Transmis aux agents : traitement en cours (l'écran se met à jour tout seul)."
        return self._traiter(evt)

    def _travailleur(self):
        while True:
            evt = self.file.get()
            try:
                self._traiter(evt, exclure=self.lents)      # fast agents first: answer visible at once
                self.derniere_erreur = None
                self._a_reflechir = self._a_reflechir or bool(self.lents)
            except Exception as e:  # noqa: BLE001 — une erreur d'un événement ne doit jamais arrêter la consultation
                self.derniere_erreur = f"{e.__class__.__name__} : {e}"
                with self.verrou:
                    self.ctx.journal.ajouter("coordinateur", "erreur_evenement", {"evenement": evt.get("type"), "erreur": self.derniere_erreur})
            finally:
                with self._compteur:
                    self.en_cours = max(0, self.en_cours - 1)
                with self.verrou:
                    self._photographier()
            if self.file.empty() and self._a_reflechir:
                self._reveil.set()            # then the online agent reasons, in its own thread

    @contextmanager
    def _hors_verrou(self):
        """While the online model answers (several seconds), the lock is released: clicks are handled."""
        self.verrou.release()
        try:
            yield
        finally:
            self.verrou.acquire()

    def _reflecteur(self):
        while True:
            self._reveil.wait()
            self._reveil.clear()
            while self._a_reflechir and self.en_cours == 0:
                self._reflechir()

    def _reflechir(self):
        """Turn of the online agents, once per series of clicks (not at every small change of the record).
        It gives way as soon as a human clicks: the rest of the reasoning resumes afterwards."""
        self.reflexion_en_cours = True
        self._a_reflechir = False     # consumed; a click during the reasoning sets it back to true (nothing is lost)
        self._photo_medecin = dict(self._photo_medecin or {}, reflexion_en_cours=True)
        try:
            with self.verrou, capturer() as tampon:
                lents = self.lents
                for _ in range(3):        # at most 3 passes: the jurist answering an assistant question…
                    for a in self.agents:
                        if a.nom in lents and self.en_cours == 0 and a.tour():
                            self._photographier()
                    if self.en_cours:
                        break
                    self.orch.stabiliser(exclure=lents)       # the fast agents react (translation…)
                    if self.orch.filet_de_securite():
                        self.orch.stabiliser(exclure=lents)
                    if not any(a.a_du_travail_en_attente() for a in self.agents if a.nom in lents):
                        break
                if any(a.a_du_travail_en_attente() for a in self.agents if a.nom in lents):
                    self._a_reflechir = True
            if self.cfg.verbeux:
                print(tampon.getvalue(), end="")
        except Exception as e:  # noqa: BLE001 — la réflexion ratée ne doit jamais arrêter la consultation
            self.derniere_erreur = f"{e.__class__.__name__} : {e}"
            with self.verrou:
                self.ctx.journal.ajouter("coordinateur", "erreur_reflexion", {"erreur": self.derniere_erreur})
        finally:
            self.reflexion_en_cours = False
            with self.verrou:
                self._photographier()

    def doublon(self, cle, delai: float = 8.0) -> bool:
        """True if the same action was just done (double click, impatience): it is not repeated."""
        import time
        with self._compteur:
            maintenant = time.time()
            self._recents = {k: t for k, t in getattr(self, "_recents", {}).items() if maintenant - t < delai}
            if cle in self._recents:
                return True
            self._recents[cle] = maintenant
            return False

    def _photographier(self):
        try:
            self._photo_medecin = self._vue_medecin()
            self._photo_patient = self._vue_patient()
        except Exception:  # noqa: BLE001 — une photo ratée n'est pas grave : la suivante la remplacera
            pass

    def _traiter(self, evt: dict, exclure=frozenset()) -> str:
        with self.verrou:
            with capturer() as tampon:
                self.ctx.journal.ajouter("coordinateur", "evenement_libere", evt)
                self.orch.appliquer(evt)
                self.orch.stabiliser(exclure)
                if self.orch.filet_de_securite():
                    self.orch.stabiliser(exclure)
            sortie = tampon.getvalue()
            if self.cfg.verbeux:
                print(sortie, end="")
            return " ".join(l.strip() for l in sortie.splitlines() if l.strip().startswith(("✔", "✖", "⚑")))

    def demo_suivant(self) -> dict:
        # Short lock in asynchronous mode: the next demo step does not wait for the online model's reasoning.
        with (self._compteur if self.asynchrone else self.verrou):
            if not self.demo or self.demo_index >= len(self.demo["evenements"]):
                return {"fini": True}
            evt = self.demo["evenements"][self.demo_index]
            self.demo_index += 1
            fini = self.demo_index >= len(self.demo["evenements"])
        retour = self.evenement(evt)
        return {"fini": fini, "description": evt["description"], "retour": retour}

    # ------------------------------------------------------------------ vues
    @staticmethod
    def _decision(d: dict) -> dict:
        x = {k: d.get(k) for k in ("id", "type", "statut", "auteur", "texte", "medicament", "dose", "posologie", "mode",
                                    "contenu_type", "valide_par", "pictogrammes", "non_traduits", "pictogrammes_choisis_par", "source_question",
                                    "source_prescription", "v")}
        x["demande"] = d.get("demande")
        x["maintien"] = d.get("maintien")
        x["precontrole"] = d.get("precontrole")
        x["rapproches"] = d.get("rapproches") or {}
        x["masque"] = bool(d.get("masque"))
        return x

    def _lire(self, construire_vue, photo):
        """Fresh view if the agents are idle; otherwise the latest snapshot (the screen never waits)."""
        if self.verrou.acquire(timeout=0.2):
            try:
                v = construire_vue()
            finally:
                self.verrou.release()
        else:
            v = dict(photo or {})
        v["travail_en_cours"] = self.en_cours > 0
        v["reflexion_en_cours"] = self.reflexion_en_cours
        v["duree_modele"] = getattr(self.ctx, "derniere_duree_modele", None)
        v["derniere_erreur"] = self.derniere_erreur
        return v

    def vue_medecin(self) -> dict:
        return self._lire(self._vue_medecin, self._photo_medecin)

    def vue_patient(self) -> dict:
        return self._lire(self._vue_patient, self._photo_patient)

    def _vue_medecin(self) -> dict:
        with self.verrou:
            d, c = self.ctx.dossier, self.ctx
            prochaine = (self.demo["evenements"][self.demo_index]["description"]
                         if self.demo and self.demo_index < len(self.demo["evenements"]) else None)
            return {
                "session": self.session,
                # name of the online model if there is one (the translator, first agent, stays on its written policy)
                "mode": next((a.cerveau.nom for a in self.agents if not isinstance(a.cerveau, CerveauSimule)), self.agents[0].cerveau.nom),
                "modele": self._etat_modele(),
                "langue": getattr(self.ctx, "langue_medecin", "fr"),
                "documents": getattr(self, "documents", []),
                "ordonnances": self._ordonnances(),
                "dictee": moteur_dictee(self.cfg),
                "journal": c.journal.verifier(), "lignes": len(c.journal.lignes),
                "etat": d.etat, "fil": d.fil[-40:],
                "questions": d.questions_a_poser,
                "decisions": [self._decision(x) for x in d.decisions.values()],
                "suggestions": list(d.suggestions.values()),
                "verdicts": d.verdicts[-30:],
                "messages": [{"id": m.id, "de": m.de, "type": m.type, "contenu": m.contenu}
                             for m in c.messagerie.historique if m.a == "medecin" and m.id not in getattr(self, "messages_masques", ())][-40:],
                "lacunes": d.lacunes,
                "mesures": c.crise.mesures, "incidents": c.crise.incidents,
                "prescripteurs": {k: v["nom"] for k, v in c.regles.kb["prescripteurs"].items() if v.get("actif")},
                "medicaments": sorted(c.regles.kb["medicaments"]),
                "cles_fermees": CLES_FERMEES,
                "demo": {"actif": bool(self.demo), "titre": self.demo["titre"] if self.demo else None,
                         "etape": self.demo_index, "total": len(self.demo["evenements"]) if self.demo else 0,
                         "prochaine": prochaine},
            }

    MAX_DOCUMENTS_PATIENT = 10        # the patient screen is open (no token): limited number per consultation

    def ajouter_document(self, nom: str, type_doc: str, mime: str, contenu: str, auteur: str = "medecin") -> str:
        from medimcom.documents import TYPES, nouveau
        with self.verrou:
            if auteur == "patient" and sum(1 for d in self.documents if d.get("auteur") == "patient") >= self.MAX_DOCUMENTS_PATIENT:
                raise ValueError(f"au plus {self.MAX_DOCUMENTS_PATIENT} documents par consultation")
            doc, octets = nouveau(nom, type_doc, mime, contenu, len(self.documents) + 1)
            if any(d["sha256"] == doc["sha256"] for d in self.documents):
                return "Ce document est déjà dans le dossier."
            doc["auteur"] = auteur
            self.documents.append(doc)
            self._octets_documents[doc["id"]] = octets
            self.ctx.journal.ajouter(auteur, "document_ajoute", {k: doc[k] for k in ("id", "nom", "type", "mime", "taille", "sha256", "auteur")})
            if auteur == "patient":       # the doctor sees it in the conversation, not only in the panel
                self.ctx.dossier.ajouter_echange("patient", f"Le patient a envoyé un document ({TYPES.get(doc['type'], 'autre')}) : "
                                                 "à voir dans « Documents du patient » ; lecture automatique en cours.", None, False)
            if self.asynchrone:
                self._photographier()     # the doctor screen shows the document without waiting for another click
        threading.Thread(target=self._lire_document, args=(doc,), daemon=True, name=f"document-{doc['id']}").start()
        return (f"Document « {doc['nom']} » joint au dossier : lecture en cours." if auteur != "patient"
                else "Document envoyé au médecin.")

    def _lire_document(self, doc: dict):
        """Reading outside the lock (the model may take several seconds); the extracted facts then enter the record
        as UNconfirmed, and the agents check them (risks of the medicine for this patient…)."""
        from medimcom.documents import faits_du_document, lire
        cerveau = next((a.cerveau for a in self.agents if not isinstance(a.cerveau, CerveauSimule)), None)
        session = self.session
        try:
            ex = lire(doc, self._octets_documents.get(doc["id"], b""), cerveau, self.ctx.regles.kb.get("medicaments", {}))
        except Exception as e:  # noqa: BLE001
            ex = {**doc["extraction"], "statut": "erreur", "resume": f"Lecture impossible : {e.__class__.__name__}"}
        if session != self.session:
            return                                          # new consultation meanwhile: nothing is written
        doc["extraction"] = ex
        with self.verrou:
            self.ctx.journal.ajouter("assistant", "document_lu", {"id": doc["id"], "statut": ex["statut"], "par": ex.get("par"),
                                                                  "medicaments": [m["nom"] for m in ex.get("medicaments", [])],
                                                                  "erreur_modele": ex.get("erreur_modele")})
        donnees = faits_du_document(doc)
        if donnees:
            self.evenement({"type": "echange", "auteur": "document", "confirme": False,
                            "texte": f"Lecture du document « {doc['nom']} » ({ex.get('par')}) : à confirmer par le médecin.",
                            "donnees": donnees})

    def _ordonnances(self) -> list[dict]:
        from medimcom.ordonnance import ordonnances
        return ordonnances(self.ctx)

    def _etat_modele(self) -> dict | None:
        """Is the online model answering? (the screen must not say "online" when the provider refuses the key)"""
        a = next((a for a in self.agents if not isinstance(a.cerveau, CerveauSimule)), None)
        if a is None:
            return None
        cle = getattr(a.cerveau, "modele", a.cerveau.nom)
        etat = dict(self.ctx.etat_modele.get(cle) or {"disponible": True, "message": "prêt"})
        if self.ctx.echecs_modele.get(cle, 0) >= self.ctx.seuil_echecs:
            etat["disponible"] = False
        etat["modele"] = cle
        etat["fournisseur"] = fournisseur_lisible(self.cfg)
        return etat

    def _vue_patient(self) -> dict:
        with self.verrou:
            d = self.ctx.dossier
            envoyes = [x for x in d.decisions.values() if x.get("type") == "envoi_patient" and x["statut"] == "envoye"]
            trad = next((a for a in self.agents if a.nom == "traducteur"), None)
            attend = bool(trad and trad._question_ouverte()[0])
            urgence = d.etat.get("urgence")
            urgences = [e for e in d.fil if "urgence" in (e.get("donnees") or {})]
            return {"session": self.session, "messages": [{"id": x["id"], "pictogrammes": x.get("pictogrammes") or [], "contenu_type": x.get("contenu_type"),
                                  "texte": x.get("texte") or ""}
                                 for x in envoyes][-10:],
                    # the patient who reported an emergency sees that the doctor is warned, then that the doctor takes
                    # charge
                    "urgence": ("signalee" if urgence and urgence["valeur"] is True else
                                "prise_en_charge" if urgences and urgences[-1]["donnees"]["urgence"] is False
                                and any(e["donnees"].get("urgence") is True for e in urgences) else None),
                    "attend_reponse": attend, "palette": palette(getattr(self.ctx.pictogrammeur, "notions", None)),
                    "medicaments": sorted(self.ctx.regles.kb["medicaments"]),     # "my medicines" in the guide
                    "ordonnances": self._ordonnances(),
                    # their own uploads: only the type and the state (neither file name nor content)
                    "documents": [{"id": x["id"], "type": x["type"], "lu": x["extraction"]["statut"] == "lu"}
                                  for x in getattr(self, "documents", []) if x.get("auteur") == "patient"]}


def fiche_lisible(ctx, q: str) -> dict | None:
    """Knowledge-base provision found by its identifier or by the short reference displayed
    ("UAE Federal Decree-Law 4/2016 (Medical Liability), Art. 3"): title, text, exact quote, official source,
    verification level, and excerpts of the full text if it was downloaded (base_v2)."""
    base = ctx.regles.base
    norm = lambda t: re.sub(r"\W+", " ", (t or "").lower()).strip()  # noqa: E731
    fid = q if q in base.fiches else next((i for i in base.fiches if norm(base.citer_court(i)) == norm(q)), None)
    if fid is None:
        fid = next((i for i in base.fiches if norm(q) and norm(q) in norm(base.citer_court(i))), None)
    if fid is None:
        return None
    f = base.fiches[fid]
    s = base.sources.get(f["source"], {})
    extraits = []
    if getattr(ctx, "corpus", None):
        try:
            # excerpts of the FULL text of the same source only (same link, or a title sharing its words), never another
            # text
            mots_source = {w for w in re.findall(r"\w{5,}", (s.get("title") or "").lower())}
            extraits = [{"citation": f"{x.get('citation')} : {x.get('texte', '')[:600]}", "lien": x.get("lien")}
                        for x in ctx.corpus.chercher(f"{s.get('title', '')} {f.get('ref', '')} {f.get('title', '')}", k=6, type_="texte_officiel")
                        if (x.get("lien") and x.get("lien") == s.get("url"))
                        or len(mots_source & set(re.findall(r"\w{5,}", (x.get("titre") or "").lower()))) >= 2][:2]
        except Exception:  # noqa: BLE001
            extraits = []
    return {"id": fid, "titre": f.get("title"), "ref": f.get("ref"), "texte": f.get("text"), "citation": f.get("quote"),
            "base": f.get("basis"), "themes": f.get("themes", []), "source": s.get("title"), "lien": s.get("url"),
            "verification": base.NIVEAUX[ctx.regles.langue if ctx.regles.langue in base.NIVEAUX else "fr"].get(s.get("verification"), s.get("verification")),
            "reference": base.citer_court(fid), "extraits": extraits}


def _libelles(ids, langue):
    return {i: libelle(i, langue) for i in ids}


class Gestionnaire(BaseHTTPRequestHandler):
    app: Application = None

    def log_message(self, *a):
        pass

    def _repondre(self, code, corps, type_="application/json; charset=utf-8", cache=False, csp=None):
        try:
            return self._ecrire(code, corps, type_, cache, csp)
        except (BrokenPipeError, ConnectionResetError):
            return None                     # the browser closed the connection (page reloaded): harmless

    def _ecrire(self, code, corps, type_, cache, csp=None):
        donnees = corps if isinstance(corps, bytes) else (json.dumps(corps, ensure_ascii=False, default=str).encode("utf-8")
                                                           if not isinstance(corps, str) else corps.encode("utf-8"))
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(donnees)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if type_.startswith("image/svg"):        # an image opened alone cannot run anything
            self.send_header("Content-Security-Policy", "default-src 'none'; img-src data:; style-src 'unsafe-inline'")
        if type_.startswith("text/html"):
            self.send_header("Referrer-Policy", "no-referrer")       # the doctor's token never leaks in a link
            self.send_header("X-Frame-Options", "DENY")
            if csp or self.app.react:
                self.send_header("Content-Security-Policy", csp or CSP_PAGE)
        self.end_headers()
        self.wfile.write(donnees)

    def _jeton_ok(self) -> bool:
        q = parse_qs(urlparse(self.path).query).get("jeton", [""])[0]
        donne = self.headers.get("X-Jeton") or q
        return bool(donne) and hmac.compare_digest(donne, self.app.jeton)

    def _meme_origine(self) -> bool:
        origine = self.headers.get("Origin")
        return origine is None or origine in (f"http://{self.headers.get('Host')}", f"https://{self.headers.get('Host')}")

    def _hote_ok(self) -> bool:
        """Against "DNS rebinding": only a local host name or an IP address (tablet on the Wi-Fi) is accepted,
        never a domain name that could belong to a website."""
        hote = (self.headers.get("Host") or "").strip()
        if hote.startswith("["):
            nom, _, port = hote[1:].partition("]")
            port = port.lstrip(":")
        else:
            nom, _, port = hote.rpartition(":") if hote.count(":") == 1 else (hote, "", "")
        if port and port != str(self.server.server_address[1]):
            return False
        if nom.lower() == "localhost":
            return True
        # Online hosting: the server's domain names are declared (MEDIMCOM_HOTES, comma-separated); any other name is
        # still refused (protection against "DNS rebinding")
        if nom.lower() in {h.strip().lower() for h in (os.environ.get("MEDIMCOM_HOTES", "") + "," + os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")).split(",") if h.strip()}:
            return True
        try:
            ipaddress.ip_address(nom)
            return True
        except ValueError:
            return False

    def do_GET(self):
        if not self._hote_ok():
            return self._repondre(403, {"erreur": "nom d'hôte refusé"})
        chemin = urlparse(self.path).path
        if chemin == "/":
            return self._page("accueil")
        if chemin == "/patient":
            return self._page("patient")
        if chemin.startswith("/assets/") and self.app.react:
            nom = chemin[len("/assets/"):]
            f = WEB / "assets" / nom
            if "/" in nom or nom.startswith(".") or not f.is_file() or f.suffix not in TYPES:
                return self._repondre(404, {"erreur": "introuvable"})
            return self._repondre(200, f.read_bytes(), TYPES[f.suffix], cache=True)
        if chemin.startswith("/pictos/") and chemin.endswith(".svg"):
            ident = unquote(chemin[len("/pictos/"):-4])
            return self._repondre(200, svg(ident), "image/svg+xml; charset=utf-8", cache=True)
        if chemin == "/api/patient":
            return self._repondre(200, self.app.vue_patient())
        if chemin == "/api/patient/ordonnance.pdf":         # the prescription given to the patient, downloadable
            from medimcom.ordonnance import ordonnances, pdf
            with self.app.verrou:
                ords = ordonnances(self.app.ctx)
                e = self.app.ctx.dossier.etat
                patient = {"sexe": (e.get("sexe") or {}).get("valeur"), "âge": (e.get("age") or {}).get("valeur"),
                           "poids (kg)": (e.get("poids") or {}).get("valeur"), "allergies": (e.get("allergies") or {}).get("valeur")}
            if not ords:
                return self._repondre(404, {"erreur": "aucune ordonnance remise au patient pour l'instant"})
            donnees = pdf(ords, patient, self.app.session, self.app.ctx.regles.pays)
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="ordonnance_{self.app.session}.pdf"')
            self.send_header("Content-Length", str(len(donnees)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(donnees)
            return None
        if chemin == "/credits":
            lignes = "".join(f"<tr><td>{html.escape(c['pictogramme'])}</td><td>{html.escape(c['attribution'])}</td>"
                             f"<td><a href=\"{html.escape(c['source'])}\" rel=\"noopener\">{html.escape(c['source'])}</a></td></tr>"
                             for c in credits())
            page = ("<!doctype html><html lang=fr><meta charset=utf-8><title>Crédits des pictogrammes</title>"
                    "<body style='font:14px system-ui;margin:20px;background:#fff;color:#1E2B31'><h1>Crédits des pictogrammes</h1>"
                    + (f"<table>{lignes}</table>" if lignes else "<p>Icônes de démonstration du prototype (générées par code).</p>")
                    + "</body></html>")
            return self._repondre(200, page, "text/html; charset=utf-8")
        if chemin == "/api/palette":            # every available pictogram, per tab (doctor's editor)
            return self._repondre(200, palette(getattr(self.app.ctx.pictogrammeur, "notions", None)))
        if chemin == "/api/pictogrammes/chercher":   # hybrid search (keywords, spelling, meaning): patient and doctor
            qs = parse_qs(urlparse(self.path).query)
            texte, n = qs.get("q", [""])[0][:120], qs.get("k", ["24"])[0]
            chercher = getattr(self.app.ctx.pictogrammeur, "chercher", None)
            res = chercher(texte, max(1, min(int(n) if n.isdigit() else 24, 60))) if chercher and len(texte.strip()) >= 2 else []
            return self._repondre(200, {"resultats": res, "sens": bool(chercher and self.app.ctx.pictogrammeur.recherche._vect)})
        if chemin == "/api/libelles":
            ids = list(CATALOGUE) + list(VOCABULAIRE) + [i for v in palette(getattr(self.app.ctx.pictogrammeur, "notions", None)).values() for i in v]
            return self._repondre(200, {lg: _libelles(ids, lg) for lg in ("fr", "en", "ar")})
        # ---- everything below is reserved to the doctor (token)
        if chemin in ("/medecin", "/api/medecin", "/journal", "/journal.json") and not self._jeton_ok():
            return self._repondre(403, "Accès médecin : utiliser le lien affiché au démarrage du serveur.", "text/plain; charset=utf-8")
        if chemin == "/medecin":
            return self._page("medecin")
        if chemin == "/api/medecin":
            return self._repondre(200, self.app.vue_medecin())
        if chemin == "/api/medecin/document":          # the doctor reopens an attached document
            ident = int((parse_qs(urlparse(self.path).query).get("id", ["0"])[0] or "0"))
            doc = next((d for d in getattr(self.app, "documents", []) if d["id"] == ident), None)
            if not doc:
                return self._repondre(404, {"erreur": "document introuvable"})
            return self._repondre(200, self.app._octets_documents[ident], doc["mime"])
        if chemin == "/api/fiche":                  # read the law text (or the reference) cited by the jurist
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
            with self.app.verrou:
                f = fiche_lisible(self.app.ctx, q)
            return self._repondre(200 if f else 404, f or {"erreur": f"référence introuvable : {q}"})
        if chemin == "/journal":
            import exporter_journal
            with self.app.verrou, tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "journal.json"
                self.app.ctx.journal.sauver(src)
                exporter_journal.exporter(src, Path(tmp) / "journal.html")
                page = (Path(tmp) / "journal.html").read_text(encoding="utf-8")
            # The journal-filter script is allowed by its hash (and only it): otherwise the interface's security policy
            # blocked it and the "Summary view / Show all" filters did not respond.
            import base64
            import hashlib
            empreintes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(x.encode("utf-8")).digest()).decode() + "'"
                                  for x in re.findall(r"<script>(.*?)</script>", page, flags=re.S))
            csp = CSP_PAGE.replace("script-src 'self'", f"script-src 'self' {empreintes}")
            return self._repondre(200, page, "text/html; charset=utf-8", csp=csp)
        if chemin == "/journal.json":
            with self.app.verrou:
                return self._repondre(200, self.app.ctx.journal.lignes)
        return self._repondre(404, {"erreur": "introuvable"})

    def _page(self, nom: str):
        """React interface (a single page that picks the screen from the address) or classic HTML page."""
        if self.app.react:
            return self._repondre(200, (WEB / "index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        page = (CLASSIQUE / f"{nom}.html").read_text(encoding="utf-8").replace("__JETON__", self.app.jeton)
        return self._repondre(200, page, "text/html; charset=utf-8")

    def do_POST(self):
        if not self._hote_ok():
            return self._repondre(403, {"erreur": "nom d'hôte refusé"})
        chemin = urlparse(self.path).path
        # Protection against requests from other pages: JSON required (triggers the browser's CORS check), same origin,
        # and doctor token for everything except the patient's answers.
        if not (self.headers.get("Content-Type") or "").startswith("application/json") or not self._meme_origine():
            return self._repondre(403, {"erreur": "requête refusée (type ou origine)"})
        if chemin not in ("/api/patient/reponse", "/api/patient/traduire", "/api/patient/document") and not self._jeton_ok():
            return self._repondre(403, {"erreur": "jeton médecin manquant ou invalide"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > (12 * 1024 * 1024 if chemin in ("/api/medecin/document", "/api/patient/document") else 1024 * 1024):
                return self._repondre(413, {"erreur": "requête trop lourde"})
            corps = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(corps, dict):
                raise ValueError("le corps doit être un objet JSON")
            retour = self._action(chemin, corps)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            return self._repondre(400, {"erreur": f"{e.__class__.__name__} : {e}"})
        if retour is None:
            return self._repondre(404, {"erreur": "action inconnue"})
        return self._repondre(200, retour)

    def _action(self, chemin, c):
        app = self.app
        medecin = c.get("medecin", "DR-001")
        texte = lambda k: str(c.get(k, "")).strip()[:600]  # noqa: E731
        if chemin == "/api/medecin/faits":
            brut = c.get("donnees", {})
            if not isinstance(brut, dict):
                raise ValueError("donnees doit être un objet")
            donnees = {str(k)[:60]: (v[:2000] if isinstance(v, str) else v) for k, v in brut.items() if v not in ("", None)}
            if "age" in donnees:
                donnees["age"] = int(donnees["age"])
            # Free-text information (history, other information): the text is kept as is and the facts the agents can
            # use are extracted from it (known diseases, pregnancy, kidney disease…), without imposing a form.
            from medimcom.faits import extraire_faits
            libre = " ".join(str(v) for k, v in donnees.items() if isinstance(v, str) and k not in ("sexe",))
            for k, v in extraire_faits(libre).items():
                donnees.setdefault(k, v)
            return {"retour": app.evenement({"type": "echange", "auteur": "medecin", "confirme": True,
                                             "texte": "Renseignements saisis par le médecin.", "donnees": donnees})}
        if chemin == "/api/medecin/message":
            if not texte("texte"):
                raise ValueError("texte vide")
            if app.doublon(("message", texte("texte"))):
                return {"retour": "Déjà transmis : la traduction arrive (inutile de renvoyer)."}
            return {"retour": app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": texte("texte"),
                                             "contenu_type": "question" if c.get("question") else "information",
                                             "cle": c.get("cle") if c.get("cle") in CLES_FERMEES else None})}
        if chemin == "/api/medecin/prescription":
            evt = {"type": "prescription", "auteur": "medecin", "prescripteur": medecin, "medicament": texte("medicament"),
                   "dose": texte("dose") or None, "posologie": texte("posologie") or None, "mode": texte("mode") or "presentiel",
                   "texte": f"{texte('medicament')} {texte('dose')} {texte('posologie')}".strip(),
                   "issue_de_suggestion": bool(c.get("issue_de_suggestion"))}
            if c.get("remplace_medicament"):
                evt["remplace_medicament"] = texte("remplace_medicament")
            return {"retour": app.evenement(evt)}
        if chemin == "/api/medecin/valider":
            return {"retour": app.evenement({"type": "validation", "auteur": "medecin", "medecin": medecin, "decision_id": int(c["decision_id"]),
                                             "confirme_contexte": bool(c.get("confirme_contexte"))})}
        if chemin == "/api/medecin/pictogrammes":
            return {"retour": app.evenement({"type": "modification_pictogrammes", "auteur": "medecin", "medecin": medecin,
                                             "decision_id": int(c["decision_id"]),
                                             "pictogrammes": [str(p) for p in c.get("pictogrammes", [])][:12]})}
        if chemin == "/api/medecin/langue":          # doctor's language: agents, jurist, translation
            langue = str(c.get("langue", "fr"))[:2]
            if langue not in ("fr", "en", "ar"):
                raise ValueError("langue : fr, en ou ar")
            with app.verrou:
                app.ctx.langue_medecin = langue
                app.ctx.regles.langue = "fr" if langue == "fr" else "en"      # rule texts: French or English
                if hasattr(app.ctx.pictogrammeur, "langue_saisie"):
                    app.ctx.pictogrammeur.langue_saisie = "en" if langue == "en" else "fr"
                app.ctx.journal.ajouter("medecin", "langue", {"langue": langue})
            return {"retour": {"fr": "Langue : français.", "en": "Language: English.", "ar": "اللغة: العربية."}[langue]}
        if chemin == "/api/medecin/accueil":         # inform the patient of the AI's help and of their right to refuse
            if app.doublon(("accueil",)):
                return {"retour": "Déjà transmis : la traduction arrive."}
            return {"retour": app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": MESSAGE_ACCUEIL,
                                             "contenu_type": "question", "cle": "informe_usage_ia"})}
        if chemin == "/api/medecin/urgence_prise_en_charge":
            return {"retour": app.evenement({"type": "echange", "auteur": "medecin", "confirme": True,
                                             "texte": f"Urgence prise en charge par {app.ctx.regles.kb['prescripteurs'].get(medecin, {}).get('nom', medecin)}.",
                                             "donnees": {"urgence": False}})}
        if chemin == "/api/medecin/poser_question":
            return {"retour": app.evenement({"type": "poser_question", "auteur": "medecin", "medecin": medecin,
                                             "question_id": int(c["question_id"]), "modifier": bool(c.get("modifier"))})}
        if chemin == "/api/medecin/refuser_question":
            return {"retour": app.evenement({"type": "refus_question", "auteur": "medecin", "question_id": int(c["question_id"])})}
        if chemin == "/api/medecin/apercu":          # pictogram preview, without proposing or sending anything
            t = texte("texte")
            with app.verrou:
                r = app.ctx.pictogrammeur.traduire(t) if t else {"pictogrammes": [], "non_traduits": []}
            return {"pictogrammes": r["pictogrammes"], "non_traduits": r["non_traduits"]}
        if chemin == "/api/medecin/masquer_agent":   # agent message dismissed by the doctor (logged)
            mid = int(c["message_id"])
            with app.verrou:
                app.messages_masques.add(mid)
                app.ctx.journal.ajouter("medecin", "message_agent_masque", {"message": mid, "par": medecin})
            return {"retour": "Message masqué."}
        if chemin == "/api/patient/document":        # the patient sends a photo or a PDF useful to the doctor
            return {"retour": app.ajouter_document(texte("nom") or "document du patient", texte("type") or "autre",
                                                   str(c.get("mime", ""))[:60], str(c.get("contenu", "")), auteur="patient")}
        if chemin == "/api/medecin/document":        # photo of a prescription, receipt, box, X-ray, lab result… (read in the background)
            return {"retour": app.ajouter_document(texte("nom") or "document", texte("type") or "autre",
                                                   str(c.get("mime", ""))[:60], str(c.get("contenu", "")))}
        if chemin == "/api/medecin/retirer":
            return {"retour": app.evenement({"type": "retrait_message", "auteur": "medecin", "medecin": medecin,
                                             "decision_id": int(c["decision_id"]), "raison": texte("raison")})}
        if chemin == "/api/medecin/masquer":
            return {"retour": app.evenement({"type": "masquage_message", "auteur": "medecin", "decision_id": int(c["decision_id"])})}
        if chemin == "/api/medecin/rejeter":
            return {"retour": app.evenement({"type": "rejet", "auteur": "medecin", "decision_id": int(c["decision_id"]), "raison": texte("raison")})}
        if chemin == "/api/medecin/maintenir":
            return {"retour": app.evenement({"type": "maintien", "auteur": "medecin", "medecin": medecin,
                                             "decision_id": int(c["decision_id"]), "justification": texte("justification")})}
        if chemin == "/api/medecin/ignorer":
            return {"retour": app.evenement({"type": "suggestion_ignoree", "auteur": "medecin", "suggestion_id": int(c["suggestion_id"])})}
        if chemin == "/api/medecin/juriste":
            if not texte("texte"):
                raise ValueError("question vide")
            return {"retour": app.evenement({"type": "question", "auteur": "medecin", "a": "juriste", "texte": texte("texte")})}
        if chemin == "/api/patient/reponse":
            pictos = [str(p) for p in c.get("pictogrammes", [])][:12]
            if not pictos:
                raise ValueError("aucun pictogramme")
            inconnus = [p for p in pictos if not connu(p)]
            if inconnus:
                raise ValueError(f"pictogramme ou combinaison non reconnu(e) : {', '.join(inconnus)}")
            if app.doublon(("patient", tuple(pictos))):
                return {"retour": "Déjà envoyé au médecin."}
            return {"retour": app.evenement({"type": "reponse_patient", "pictogrammes": pictos})}
        if chemin == "/api/patient/traduire":        # the patient types a few words: pictograms are suggested
            t = texte("texte")
            if not t:
                raise ValueError("texte vide")
            r = app.ctx.pictogrammeur.traduire(t)
            return {"pictogrammes": [p for p in r["pictogrammes"] if connu(p)], "non_traduits": r["non_traduits"]}
        if chemin == "/api/medecin/dictee":
            return {"texte": transcrire(c.get("audio", ""), str(c.get("langue", "fr"))[:5], moteur_dictee(app.cfg))}
        if chemin == "/api/demo/suivant":
            return app.demo_suivant()
        if chemin == "/api/reinitialiser":
            app.reinitialiser()
            return {"retour": "Nouvelle consultation."}
        return None


NOMS_FOURNISSEURS = {"xai": "xAI", "groq": "Groq · modèle open source", "openrouter": "OpenRouter", "gemini": "Google",
                     "mistral": "Mistral AI", "anthropic": "Anthropic", "openai": "OpenAI"}


def fournisseur_lisible(cfg) -> str:
    """Who runs the model (shown next to its name): we use a MODEL, not a company's agent."""
    if getattr(cfg, "mode", "") == "ollama":
        return "Ollama · open source, sur cet ordinateur"
    if getattr(cfg, "fournisseur", None):
        return NOMS_FOURNISSEURS.get(cfg.fournisseur, cfg.fournisseur)
    return urlparse(getattr(cfg, "url", "") or "").hostname or "compatible OpenAI"


def moteur_dictee(cfg=None) -> str:
    """Server-side speech recognition: Whisper (open source) at Groq when working with Groq or without an xAI key,
    otherwise xAI; failing that, the browser's (Chrome)."""
    import os
    groq, xai = bool(os.environ.get("GROQ_API_KEY")), bool(os.environ.get("XAI_API_KEY"))
    if groq and (getattr(cfg, "fournisseur", None) == "groq" or not xai):
        return "groq"
    return "xai" if xai else "navigateur"


def transcrire(audio_b64: str, langue: str = "fr", moteur: str | None = None) -> str:
    """Doctor's dictation: WAV audio (base64) -> text, by Whisper large v3 (open-source model) at Groq, or by xAI
    speech recognition. The audio goes to that provider (United States): fictitious patients only."""
    import base64
    import os
    import urllib.error
    import urllib.request
    moteur = moteur or moteur_dictee()
    cle = os.environ.get("GROQ_API_KEY" if moteur == "groq" else "XAI_API_KEY")
    if not cle:
        raise ValueError("dictée indisponible : ni clé GROQ_API_KEY ni clé XAI_API_KEY (fichier .env)")
    audio = base64.b64decode(audio_b64.split(",", 1)[-1] or b"", validate=False)
    if len(audio) < 1000 or not audio.startswith(b"RIFF"):
        raise ValueError("enregistrement vide ou illisible")
    if len(audio) > 8_000_000:
        raise ValueError("enregistrement trop long (2 minutes au plus)")
    borne = "----medimcom" + secrets.token_hex(8)
    champs = ({"language": langue[:2], "model": "whisper-large-v3-turbo", "response_format": "json"} if moteur == "groq"
              else {"language": langue[:2], "format": "true"})
    corps = b"".join([
        *(f"--{borne}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in champs.items()),
        f"--{borne}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"dictee.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode(),
        audio, f"\r\n--{borne}--\r\n".encode()])
    adresse = "https://api.groq.com/openai/v1/audio/transcriptions" if moteur == "groq" else "https://api.x.ai/v1/stt"
    req = urllib.request.Request(adresse, data=corps, method="POST",
                                 headers={"Authorization": f"Bearer {cle}", "Content-Type": f"multipart/form-data; boundary={borne}",
                                          **__import__("medimcom.cerveaux", fromlist=["x"]).AGENT_HTTP})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            rep = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ValueError(f"reconnaissance vocale refusée (HTTP {e.code}) : {e.read()[:200].decode('utf-8', 'replace')}")
    except OSError as e:
        raise ValueError(f"reconnaissance vocale injoignable ({e.__class__.__name__})")
    return str(rep.get("text", "")).strip()


def creer_serveur(app: Application, hote="127.0.0.1", port=8000) -> ThreadingHTTPServer:
    gestionnaire = type("G", (Gestionnaire,), {"app": app})
    return ThreadingHTTPServer((hote, port), gestionnaire)


def main(argv=None):
    p = argparse.ArgumentParser(description="MEDIMCOM IA interface (doctor screen + patient screen)")
    p.add_argument("--mode", choices=["simule", "ollama", "openai"], default=None,
                   help="without --mode or --fournisseur: the key of CLE_API.txt chooses the model (otherwise written rules)")
    p.add_argument("--modele", default="qwen3:8b")
    p.add_argument("--modeles", default=None, help="model per agent, e.g. juriste=grok-4.3,assistant=grok-4.3")
    p.add_argument("--url", default=None)
    p.add_argument("--demo", default=None, help="scenario played step by step ('Next step' button)")
    p.add_argument("--interface", choices=["auto", "react", "classique"], default="auto",
                   help="auto: React interface if built (interface/web/dist), otherwise classic pages")
    p.add_argument("--hote", default=os.environ.get("MEDIMCOM_HOTE", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))      # PORT: set by the host
    p.add_argument("--langue", choices=["fr", "en"], default="fr")
    p.add_argument("--fournisseur", choices=["gemini", "groq", "openrouter", "mistral", "xai", "anthropic", "openai"], default=None,
                   help="preset online model (free tiers possible): gemini, groq, openrouter, mistral, xai, anthropic, openai; "
                        "key in CLE_API.txt or in GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, MISTRAL_API_KEY, XAI_API_KEY…")
    p.add_argument("--base", default=None,
                   help="folder of the built base (default: MEDIMCOM_IA/base_v2 then ~/MEDIMCOM_base_v2); 'aucune' to do without")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh"], default=None,
                   help="reasoning effort of reasoning models (grok-4.7…): low = faster and cheaper, for a demo")
    p.add_argument("--agents-ia", default="assistant",
                   help="agents that use the model, comma-separated (assistant, traducteur, juriste, autorite_sante, "
                        "hopital, cellule_crise) or 'tous' (all); the others follow their written, instant and verified policy "
                        "(default: assistant)")
    p.add_argument("--secours", default="", help="fallback providers in order, e.g. groq,openrouter (quota exhausted or outage)")
    p.add_argument("--pays", choices=["AE", "CM"], default="AE", help="law applied by the jurist: AE (United Arab Emirates, host country) or CM (Cameroon)")
    p.add_argument("--recherche", default=None,
                   help="hybrid keyword + meaning search (texts, WHO fact sheets, pictograms): fastembed:e5 (recommended, local), "
                        "fastembed:mpnet, ollama:bge-m3 or hachage; vectors built by outils/vectoriser_base.py")
    p.add_argument("--donnees-fictives", action="store_true",
                   help="required with an online model: certifies that only fictitious patients are used")
    a = p.parse_args(argv)
    cfg_cle = None
    if a.mode is None and not a.fournisseur:      # usual case: the key pasted in CLE_API.txt decides
        from medimcom.cle_api import appliquer
        from medimcom.session import Config as _C
        cfg_cle = _C(secours=[x for x in a.secours.split(",") if x])
        print(appliquer(cfg_cle))
        a.fournisseur = cfg_cle.fournisseur
        a.donnees_fictives = a.donnees_fictives or cfg_cle.donnees_fictives
        if cfg_cle.fournisseur and a.modele == "qwen3:8b":
            a.modele = cfg_cle.modele
        a.secours = ",".join(cfg_cle.secours)
        if cfg_cle.fournisseur and a.effort is None:
            a.effort = "low"
    a.mode = a.mode or "simule"
    try:      # the key provided with the project (CLE_API.txt, .env) is also kept in ~/.config/medimcom/env
        from medimcom.session import ENV_PERSONNEL, memoriser_cles
        copiees = memoriser_cles()
        if copiees:
            print(f"✓ Key(s) {', '.join(copiees)} kept in {ENV_PERSONNEL} (readable by you only)")
    except OSError as e:
        print(f"(could not keep a copy of the key in ~/.config/medimcom/env: {e.strerror})")
    if a.hote not in ("127.0.0.1", "localhost"):
        print("⚠ The server is visible on the network (HTTP, not encrypted): fictitious data only, trusted network only.\n"
              "  The doctor screen stays protected by its token; the patient screen is open to any device on the network,\n"
              "  and its answers are recorded as confirmed facts: use a trusted network only.")
    cfg = Config(mode=a.mode, modele=a.modele, modeles=dict(x.split("=", 1) for x in (a.modeles or "").split(",") if "=" in x), url=a.url, langue=a.langue, verbeux=False,
                 fournisseur=a.fournisseur, secours=[x for x in a.secours.split(',') if x], effort=a.effort, base=a.base,
                 agents_ia=None if a.agents_ia.strip() in ('tous', 'all', '') else [x.strip() for x in a.agents_ia.split(',') if x.strip()], donnees_fictives=a.donnees_fictives, recherche=a.recherche, pays=a.pays)
    if a.interface == "react" and not (WEB / "index.html").exists():
        print("React interface not built: cd interface/web && npm install && npm run build (or --interface classique).")
        return 2
    app = Application(cfg, Path(a.demo) if a.demo else None, a.interface, asynchrone=True)
    try:
        serveur = creer_serveur(app, a.hote, a.port)
    except OSError as e:
        print(f"Cannot listen on {a.hote}:{a.port} ({e.strerror}). Another server may be running: try --port {a.port + 1}.")
        return 2
    hote = "127.0.0.1" if a.hote in ("0.0.0.0", "") else a.hote
    publique = (os.environ.get("MEDIMCOM_URL_PUBLIQUE") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if publique:
        print(f"DOCTOR screen online (private link): {publique}/medecin?jeton={app.jeton}\nPATIENT screen online: {publique}/patient")
    print(f"DOCTOR screen (private link, do not share): http://{hote}:{a.port}/medecin?jeton={app.jeton}")
    print(f"PATIENT screen: http://{hote}:{a.port}/patient" + ("   (from the tablet: replace 127.0.0.1 with this computer's address)" if a.hote == "0.0.0.0" else ""))
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    sys.exit(main())
