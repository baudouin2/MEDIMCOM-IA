"""Interface locale de MEDIMCOM IA : écran médecin + écran patient, branchés sur les agents.

    python interface/serveur.py                                   # affiche le lien privé de l'écran médecin
                                                                  # et http://127.0.0.1:8000/patient
    python interface/serveur.py --demo scenarios/grossesse.json   # bouton « Étape suivante » (pour la vidéo)
    python interface/serveur.py --mode ollama --modele qwen3:8b   # vrais agents
    python interface/serveur.py --hote 0.0.0.0                    # tablette patient sur le même réseau Wi-Fi (voir avertissement)

Aucune dépendance : bibliothèque standard de Python. Données FICTIVES uniquement.
Sécurité : écoute sur 127.0.0.1 par défaut ; l'écran médecin et ses actions exigent un jeton secret (lien affiché
au démarrage) ; toutes les requêtes d'écriture exigent du JSON venant de la même origine ; seuls localhost et les adresses IP sont
acceptés comme nom d'hôte (protection contre le « DNS rebinding »). L'écran patient n'a pas de
jeton : il ne peut qu'envoyer des pictogrammes, que le traducteur rapporte tels quels.
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
WEB = ICI / "web" / "dist"            # interface React compilée (npm run build dans interface/web)
CLASSIQUE = ICI / "classique"         # pages HTML simples, utilisées si l'interface React n'est pas compilée
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
    """Palette du patient : seulement les pictogrammes disponibles (icônes de démonstration ou bases installées).
    Avec base_v2, chaque onglet est complété par les notions du vocabulaire de consultation qui ont une image."""
    p = {k: [i for i in v if connu(i)] for k, v in PALETTE_DEMO.items()}
    if notions:
        from medimcom.base_v2 import ONGLETS_PATIENT, palette_patient
        for onglet, ids in palette_patient(notions).items():
            p[onglet] = list(dict.fromkeys(p.get(onglet, []) + ids))
        ordre = list(ONGLETS_PATIENT) + [k for k in p if k not in ONGLETS_PATIENT]   # ordre de l'écran : réponses, corps, douleur…
        p = {k: p[k] for k in ordre if k in p}
    return {k: v for k, v in p.items() if v}
CLES_FERMEES = ["grossesse", "fievre", "douleur", "nausees", "consentement_traitement", "allergies", "traitements_en_cours",
                "informe_usage_ia"]
# Message d'accueil : le patient sait qu'une IA aide le médecin, que le médecin décide, et qu'il peut refuser (DHA 2021,
# obligation IA-INFORMER). Sa réponse OUI / NON est enregistrée (informe_usage_ia).
MESSAGE_ACCUEIL = ("Bonjour. Je suis votre médecin. Un ordinateur m'aide à traduire. C'est moi qui décide. "
                   "Vous pouvez dire non. Vous êtes d'accord ?")


class _SortieParFil(io.TextIOBase):
    """Sortie standard propre à chaque fil : l'assistant (en ligne) et les agents rapides travaillent en même temps,
    et chacun capture ses propres messages sans mélanger ceux de l'autre (redirect_stdout n'est pas fait pour ça)."""

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
    """Une consultation en cours. Toutes les modifications passent par `evenement` (sous verrou)."""

    def __init__(self, cfg: Config, demo: Path | None = None, interface: str = "auto", asynchrone: bool = False):
        self.cfg, self.demo_chemin = cfg, demo
        self.react = interface == "react" or (interface == "auto" and (WEB / "index.html").exists())
        self.verrou = threading.RLock()
        self.jeton = secrets.token_urlsafe(18)       # accès à l'écran médecin (lien affiché au démarrage)
        # Mode asynchrone (serveur réel) : un clic ne fait qu'ajouter l'événement à une file ; les agents travaillent en
        # arrière-plan et les écrans lisent la dernière photo de la consultation, sans attendre la fin du travail des agents.
        self.asynchrone = asynchrone
        self.file: queue.Queue = queue.Queue()
        self.en_cours = 0
        self._compteur = threading.Lock()   # verrou court, distinct de celui des agents : un clic ne doit jamais attendre l'IA
        self.derniere_erreur = None
        self.reflexion_en_cours = False     # l'agent en ligne (assistant) réfléchit, en arrière-plan
        self._a_reflechir = False           # il reste de la réflexion à faire quand plus aucun humain n'attend
        self._photo_medecin = self._photo_patient = None
        self.reinitialiser()
        self._reveil = threading.Event()
        if asynchrone:
            threading.Thread(target=self._travailleur, daemon=True, name="agents").start()
            threading.Thread(target=self._reflecteur, daemon=True, name="reflexion").start()

    def reinitialiser(self):
        with self.verrou:
            self.ctx, self.agents, self.orch = construire(self.cfg)
            self.session = secrets.token_hex(4)          # change à chaque nouvelle consultation
            self._recents = {}                            # anti-doublons : repart de zéro avec la consultation
            self.demo = json.loads(self.demo_chemin.read_text(encoding="utf-8")) if self.demo_chemin else None
            self.demo_index = 0
            if self.demo:
                self.ctx.journal.ajouter("coordinateur", "scenario", {"titre": self.demo["titre"]})
            self.orch.apres_tour = self._photographier     # l'écran se met à jour après chaque action d'un agent
            # Agents « lents » : ceux qui interrogent un modèle en ligne. En mode asynchrone, ils jouent APRÈS les agents
            # rapides et cèdent la place dès qu'un humain clique : un clic n'attend jamais la réflexion du modèle.
            self.lents = frozenset(a.nom for a in self.agents if not isinstance(a.cerveau, CerveauSimule)) if self.asynchrone else frozenset()
            self.ctx.interrompre = (lambda: self.en_cours > 0) if self.asynchrone else None
            self.ctx.attente_modele = self._hors_verrou if self.asynchrone else None
            self._a_reflechir = False
            self._photographier()

    # ------------------------------------------------------------------ événements
    def evenement(self, evt: dict) -> str:
        if self.asynchrone and threading.current_thread().name not in ("agents", "reflexion"):
            with self._compteur:            # surtout pas self.verrou : il est tenu pendant tout le travail des agents
                self.en_cours += 1
            self.file.put(evt)
            return "Transmis aux agents : traitement en cours (l'écran se met à jour tout seul)."
        return self._traiter(evt)

    def _travailleur(self):
        while True:
            evt = self.file.get()
            try:
                self._traiter(evt, exclure=self.lents)      # d'abord les agents rapides : réponse visible tout de suite
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
                self._reveil.set()            # puis l'agent en ligne réfléchit, dans son propre fil

    @contextmanager
    def _hors_verrou(self):
        """Pendant que le modèle en ligne répond (plusieurs secondes), le verrou est rendu : les clics sont traités."""
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
        """Tour des agents en ligne, une fois par série de clics (et non à chaque petit changement du dossier).
        Il cède la place dès qu'un humain clique : la suite de la réflexion est reprise ensuite."""
        self.reflexion_en_cours = True
        self._a_reflechir = False     # consommé ; un clic pendant la réflexion le remet à vrai (rien n'est perdu)
        self._photo_medecin = dict(self._photo_medecin or {}, reflexion_en_cours=True)
        try:
            with self.verrou, capturer() as tampon:
                lents = self.lents
                for _ in range(3):        # au plus 3 passages : réponse du juriste à une question de l'assistant…
                    for a in self.agents:
                        if a.nom in lents and self.en_cours == 0 and a.tour():
                            self._photographier()
                    if self.en_cours:
                        break
                    self.orch.stabiliser(exclure=lents)       # les agents rapides réagissent (traduction…)
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
        """Vrai si la même action vient d'être faite (double clic, impatience) : elle n'est pas répétée."""
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
        # Verrou court en mode asynchrone : l'étape suivante de la démo n'attend pas la réflexion du modèle en ligne.
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
        """Vue fraîche si les agents sont au repos ; sinon la dernière photo (jamais d'attente côté écran)."""
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
                # nom du modèle en ligne s'il y en a un (le traducteur, premier agent, reste en politique écrite)
                "mode": next((a.cerveau.nom for a in self.agents if not isinstance(a.cerveau, CerveauSimule)), self.agents[0].cerveau.nom),
                "modele": self._etat_modele(),
                "langue": getattr(self.ctx, "langue_medecin", "fr"),
                "ordonnances": self._ordonnances(),
                "dictee": "xai" if __import__("os").environ.get("XAI_API_KEY") else "navigateur",
                "journal": c.journal.verifier(), "lignes": len(c.journal.lignes),
                "etat": d.etat, "fil": d.fil[-40:],
                "questions": d.questions_a_poser,
                "decisions": [self._decision(x) for x in d.decisions.values()],
                "suggestions": list(d.suggestions.values()),
                "verdicts": d.verdicts[-30:],
                "messages": [{"id": m.id, "de": m.de, "type": m.type, "contenu": m.contenu}
                             for m in c.messagerie.historique if m.a == "medecin"][-40:],
                "lacunes": d.lacunes,
                "mesures": c.crise.mesures, "incidents": c.crise.incidents,
                "prescripteurs": {k: v["nom"] for k, v in c.regles.kb["prescripteurs"].items() if v.get("actif")},
                "medicaments": sorted(c.regles.kb["medicaments"]),
                "cles_fermees": CLES_FERMEES,
                "demo": {"actif": bool(self.demo), "titre": self.demo["titre"] if self.demo else None,
                         "etape": self.demo_index, "total": len(self.demo["evenements"]) if self.demo else 0,
                         "prochaine": prochaine},
            }

    def _ordonnances(self) -> list[dict]:
        from medimcom.ordonnance import ordonnances
        return ordonnances(self.ctx)

    def _etat_modele(self) -> dict | None:
        """Le modèle en ligne répond-il ? (l'écran ne doit pas afficher « en ligne » quand Grok refuse la clé)"""
        a = next((a for a in self.agents if not isinstance(a.cerveau, CerveauSimule)), None)
        if a is None:
            return None
        cle = getattr(a.cerveau, "modele", a.cerveau.nom)
        etat = dict(self.ctx.etat_modele.get(cle) or {"disponible": True, "message": "en ligne"})
        if self.ctx.echecs_modele.get(cle, 0) >= self.ctx.seuil_echecs:
            etat["disponible"] = False
        etat["modele"] = cle
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
                    # le patient qui a signalé une urgence voit que le médecin est prévenu, puis qu'il le prend en charge
                    "urgence": ("signalee" if urgence and urgence["valeur"] is True else
                                "prise_en_charge" if urgences and urgences[-1]["donnees"]["urgence"] is False
                                and any(e["donnees"].get("urgence") is True for e in urgences) else None),
                    "attend_reponse": attend, "palette": palette(getattr(self.ctx.pictogrammeur, "notions", None)),
                    "medicaments": sorted(self.ctx.regles.kb["medicaments"]),     # « mes médicaments » dans le guide
                    "ordonnances": self._ordonnances()}


def fiche_lisible(ctx, q: str) -> dict | None:
    """Fiche de la base de connaissances retrouvée par son identifiant ou par la référence courte affichée
    (« UAE Federal Decree-Law 4/2016 (Medical Liability), Art. 3 ») : titre, texte, citation exacte, source officielle,
    niveau de vérification, et extraits du texte complet s'il a été téléchargé (base_v2)."""
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
            # extraits du texte COMPLET de la même source seulement (même lien, ou titre qui partage ses mots), jamais un autre texte
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
            return None                     # le navigateur a fermé la connexion (page rechargée) : rien de grave

    def _ecrire(self, code, corps, type_, cache, csp=None):
        donnees = corps if isinstance(corps, bytes) else (json.dumps(corps, ensure_ascii=False, default=str).encode("utf-8")
                                                           if not isinstance(corps, str) else corps.encode("utf-8"))
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(donnees)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if type_.startswith("image/svg"):        # une image ouverte seule ne peut rien exécuter
            self.send_header("Content-Security-Policy", "default-src 'none'; img-src data:; style-src 'unsafe-inline'")
        if type_.startswith("text/html"):
            self.send_header("Referrer-Policy", "no-referrer")       # le jeton du médecin ne fuit jamais dans un lien
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
        """Contre le « DNS rebinding » : seul un nom d'hôte local ou une adresse IP (tablette sur le Wi-Fi) est accepté,
        jamais un nom de domaine qui pourrait appartenir à un site web."""
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
        if chemin == "/api/patient/ordonnance.pdf":         # l'ordonnance remise au patient, téléchargeable
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
        if chemin == "/api/palette":            # tous les pictogrammes disponibles, par onglet (éditeur du médecin)
            return self._repondre(200, palette(getattr(self.app.ctx.pictogrammeur, "notions", None)))
        if chemin == "/api/pictogrammes/chercher":   # recherche hybride (mots-clés, écriture, sens) : patient et médecin
            qs = parse_qs(urlparse(self.path).query)
            texte, n = qs.get("q", [""])[0][:120], qs.get("k", ["24"])[0]
            chercher = getattr(self.app.ctx.pictogrammeur, "chercher", None)
            res = chercher(texte, max(1, min(int(n) if n.isdigit() else 24, 60))) if chercher and len(texte.strip()) >= 2 else []
            return self._repondre(200, {"resultats": res, "sens": bool(chercher and self.app.ctx.pictogrammeur.recherche._vect)})
        if chemin == "/api/libelles":
            ids = list(CATALOGUE) + list(VOCABULAIRE) + [i for v in palette(getattr(self.app.ctx.pictogrammeur, "notions", None)).values() for i in v]
            return self._repondre(200, {lg: _libelles(ids, lg) for lg in ("fr", "en", "ar")})
        # ---- tout ce qui suit est réservé au médecin (jeton)
        if chemin in ("/medecin", "/api/medecin", "/journal", "/journal.json") and not self._jeton_ok():
            return self._repondre(403, "Accès médecin : utiliser le lien affiché au démarrage du serveur.", "text/plain; charset=utf-8")
        if chemin == "/medecin":
            return self._page("medecin")
        if chemin == "/api/medecin":
            return self._repondre(200, self.app.vue_medecin())
        if chemin == "/api/fiche":                  # lire le texte de loi (ou la référence) cité par le juriste
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
            # Le script des filtres du journal est autorisé par son empreinte (et seulement lui) : sans cela, la politique
            # de sécurité de l'interface le bloquait et les filtres « Vue résumée / Tout afficher » ne répondaient pas.
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
        """Interface React (une seule page, qui choisit l'écran selon l'adresse) ou page HTML classique."""
        if self.app.react:
            return self._repondre(200, (WEB / "index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        page = (CLASSIQUE / f"{nom}.html").read_text(encoding="utf-8").replace("__JETON__", self.app.jeton)
        return self._repondre(200, page, "text/html; charset=utf-8")

    def do_POST(self):
        if not self._hote_ok():
            return self._repondre(403, {"erreur": "nom d'hôte refusé"})
        chemin = urlparse(self.path).path
        # Protection contre les requêtes venues d'autres pages : JSON obligatoire (déclenche le contrôle CORS du
        # navigateur), même origine, et jeton médecin pour tout ce qui n'est pas la réponse du patient.
        if not (self.headers.get("Content-Type") or "").startswith("application/json") or not self._meme_origine():
            return self._repondre(403, {"erreur": "requête refusée (type ou origine)"})
        if chemin not in ("/api/patient/reponse", "/api/patient/traduire") and not self._jeton_ok():
            return self._repondre(403, {"erreur": "jeton médecin manquant ou invalide"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
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
            # Renseignements libres (antécédents, autres informations) : on garde le texte tel quel et on en tire les faits
            # que les agents savent utiliser (maladies connues, grossesse, maladie rénale…), sans imposer de formulaire.
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
        if chemin == "/api/medecin/langue":          # langue d'expression du médecin : agents, juriste, traduction
            langue = str(c.get("langue", "fr"))[:2]
            if langue not in ("fr", "en", "ar"):
                raise ValueError("langue : fr, en ou ar")
            with app.verrou:
                app.ctx.langue_medecin = langue
                app.ctx.regles.langue = "fr" if langue == "fr" else "en"      # textes des règles : français ou anglais
                if hasattr(app.ctx.pictogrammeur, "langue_saisie"):
                    app.ctx.pictogrammeur.langue_saisie = "en" if langue == "en" else "fr"
                app.ctx.journal.ajouter("medecin", "langue", {"langue": langue})
            return {"retour": {"fr": "Langue : français.", "en": "Language: English.", "ar": "اللغة: العربية."}[langue]}
        if chemin == "/api/medecin/accueil":         # informer le patient de l'aide de l'IA et de son droit de refuser
            if app.doublon(("accueil",)):
                return {"retour": "Déjà transmis : la traduction arrive."}
            return {"retour": app.evenement({"type": "texte_medecin", "auteur": "medecin", "texte": MESSAGE_ACCUEIL,
                                             "contenu_type": "question", "cle": "informe_usage_ia"})}
        if chemin == "/api/medecin/urgence_prise_en_charge":
            return {"retour": app.evenement({"type": "echange", "auteur": "medecin", "confirme": True,
                                             "texte": f"Urgence prise en charge par {app.ctx.regles.kb['prescripteurs'].get(medecin, {}).get('nom', medecin)}.",
                                             "donnees": {"urgence": False}})}
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
        if chemin == "/api/patient/traduire":        # le patient écrit quelques mots : on lui propose les pictogrammes
            t = texte("texte")
            if not t:
                raise ValueError("texte vide")
            r = app.ctx.pictogrammeur.traduire(t)
            return {"pictogrammes": [p for p in r["pictogrammes"] if connu(p)], "non_traduits": r["non_traduits"]}
        if chemin == "/api/medecin/dictee":
            return {"texte": transcrire(c.get("audio", ""), str(c.get("langue", "fr"))[:5])}
        if chemin == "/api/demo/suivant":
            return app.demo_suivant()
        if chemin == "/api/reinitialiser":
            app.reinitialiser()
            return {"retour": "Nouvelle consultation."}
        return None


def transcrire(audio_b64: str, langue: str = "fr") -> str:
    """Dictée du médecin : audio WAV (base64) -> texte, par la reconnaissance vocale de xAI (même clé que Grok).
    L'audio part chez xAI (États-Unis) : patients fictifs uniquement, comme pour les agents en ligne."""
    import base64
    import os
    import urllib.error
    import urllib.request
    cle = os.environ.get("XAI_API_KEY")
    if not cle:
        raise ValueError("dictée indisponible : clé XAI_API_KEY absente (fichier .env)")
    audio = base64.b64decode(audio_b64.split(",", 1)[-1] or b"", validate=False)
    if len(audio) < 1000 or not audio.startswith(b"RIFF"):
        raise ValueError("enregistrement vide ou illisible")
    if len(audio) > 8_000_000:
        raise ValueError("enregistrement trop long (2 minutes au plus)")
    borne = "----medimcom" + secrets.token_hex(8)
    corps = b"".join([
        f"--{borne}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{langue[:2]}\r\n".encode(),
        f"--{borne}\r\nContent-Disposition: form-data; name=\"format\"\r\n\r\ntrue\r\n".encode(),
        f"--{borne}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"dictee.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode(),
        audio, f"\r\n--{borne}--\r\n".encode()])
    req = urllib.request.Request("https://api.x.ai/v1/stt", data=corps, method="POST",
                                 headers={"Authorization": f"Bearer {cle}", "Content-Type": f"multipart/form-data; boundary={borne}"})
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
    p = argparse.ArgumentParser(description="Interface MEDIMCOM IA (écran médecin + écran patient)")
    p.add_argument("--mode", choices=["simule", "ollama", "openai"], default="simule")
    p.add_argument("--modele", default="qwen3:8b")
    p.add_argument("--modeles", default=None, help="modèle par agent, ex. juriste=grok-4.3,assistant=grok-4.3")
    p.add_argument("--url", default=None)
    p.add_argument("--demo", default=None, help="scénario à dérouler pas à pas (bouton « Étape suivante »)")
    p.add_argument("--interface", choices=["auto", "react", "classique"], default="auto",
                   help="auto : interface React si elle est compilée (interface/web/dist), sinon pages classiques")
    p.add_argument("--hote", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--langue", choices=["fr", "en"], default="fr")
    p.add_argument("--fournisseur", choices=["gemini", "groq", "openrouter", "mistral", "xai"], default=None,
                   help="modèle en ligne préréglé (offre gratuite possible) : gemini, groq, openrouter, mistral, xai ; "
                        "clé dans GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, MISTRAL_API_KEY ou XAI_API_KEY")
    p.add_argument("--base", default=None,
                   help="dossier de la base constituée (défaut : MEDIMCOM_IA/base_v2 puis ~/MEDIMCOM_base_v2) ; « aucune » pour s'en passer")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh"], default=None,
                   help="effort de réflexion des modèles qui raisonnent (grok-4.7…) : low = plus rapide et moins cher, pour une démo")
    p.add_argument("--agents-ia", default="assistant",
                   help="agents qui utilisent le modèle, séparés par des virgules (assistant, traducteur, juriste, autorite_sante, "
                        "hopital, cellule_crise) ou « tous » ; les autres suivent leur politique écrite, instantanée et vérifiée "
                        "(défaut : assistant)")
    p.add_argument("--secours", default="", help="fournisseurs de secours dans l'ordre, ex. groq,openrouter (quota épuisé ou panne)")
    p.add_argument("--pays", choices=["AE", "CM"], default="AE", help="droit appliqué par le juriste : AE (Émirats, pays hôte) ou CM (Cameroun)")
    p.add_argument("--recherche", default=None,
                   help="recherche hybride mots-clés + sens (textes, fiches OMS, pictogrammes) : fastembed:e5 (recommandé, local), "
                        "fastembed:mpnet, ollama:bge-m3 ou hachage ; vecteurs construits par outils/vectoriser_base.py")
    p.add_argument("--donnees-fictives", action="store_true",
                   help="obligatoire avec un modèle en ligne : atteste que seuls des patients fictifs sont utilisés")
    a = p.parse_args(argv)
    if a.hote not in ("127.0.0.1", "localhost"):
        print("⚠ Le serveur est visible sur le réseau (HTTP, sans chiffrement) : données fictives uniquement, réseau de confiance.\n"
              "  L'écran médecin reste protégé par son jeton ; l'écran patient est ouvert à tout appareil du réseau,\n"
              "  et ses réponses sont enregistrées comme des faits confirmés : n'utiliser qu'un réseau de confiance.")
    cfg = Config(mode=a.mode, modele=a.modele, modeles=dict(x.split("=", 1) for x in (a.modeles or "").split(",") if "=" in x), url=a.url, langue=a.langue, verbeux=False,
                 fournisseur=a.fournisseur, secours=[x for x in a.secours.split(',') if x], effort=a.effort, base=a.base,
                 agents_ia=None if a.agents_ia.strip() in ('tous', 'all', '') else [x.strip() for x in a.agents_ia.split(',') if x.strip()], donnees_fictives=a.donnees_fictives, recherche=a.recherche, pays=a.pays)
    if a.interface == "react" and not (WEB / "index.html").exists():
        print("Interface React non compilée : cd interface/web && npm install && npm run build (ou --interface classique).")
        return 2
    app = Application(cfg, Path(a.demo) if a.demo else None, a.interface, asynchrone=True)
    try:
        serveur = creer_serveur(app, a.hote, a.port)
    except OSError as e:
        print(f"Impossible d'écouter sur {a.hote}:{a.port} ({e.strerror}). Un autre serveur tourne peut-être : essayer --port {a.port + 1}.")
        return 2
    hote = "127.0.0.1" if a.hote in ("0.0.0.0", "") else a.hote
    print(f"Écran MÉDECIN (lien privé, ne pas partager) : http://{hote}:{a.port}/medecin?jeton={app.jeton}")
    print(f"Écran PATIENT : http://{hote}:{a.port}/patient" + ("   (depuis la tablette : remplacer 127.0.0.1 par l'adresse de cet ordinateur)" if a.hote == "0.0.0.0" else ""))
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("Arrêt.")


if __name__ == "__main__":
    sys.exit(main())
