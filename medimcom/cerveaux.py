"""« Cerveaux » des agents : ce qui choisit les outils à chaque tour.

- CerveauSimule  : aucune IA ; chaque agent suit sa politique écrite à la main (`politique_simulee`).
- CerveauOllama  : un modèle local servi par Ollama (https://ollama.com), avec appel d'outils.
- CerveauOpenAI  : tout serveur compatible avec l'API « chat/completions » d'OpenAI : llama.cpp
                   (llama-server), LM Studio, vLLM, ou un bac à sable qui expose cette API.

Tous renvoient {"content": str, "reflexion": str, "tool_calls": [(nom, arguments)]}.
Les messages internes suivent ce format :
    {"role": "assistant", "content": ..., "tool_calls": [{"id": "a1", "function": {"name": ..., "arguments": {...}}}]}
    {"role": "tool", "tool_call_id": "a1", "name": ..., "content": ...}
Chaque cerveau les convertit pour son serveur.
"""
import http.client
import io
import json
import ssl
import threading
import time
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse


def _champ(obj, nom, defaut=None):
    if obj is None:
        return defaut
    if isinstance(obj, dict):
        return obj.get(nom, defaut)
    return getattr(obj, nom, defaut)


def _args(brut) -> dict:
    if isinstance(brut, dict):
        return dict(brut)
    if isinstance(brut, str):
        try:
            v = json.loads(brut or "{}")
            return v if isinstance(v, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def separer_reflexion(texte: str) -> tuple[str, str]:
    """Sépare les balises <think>…</think> (modèles « raisonneurs ») du reste du texte."""
    texte = texte or ""
    reflexion = "\n".join(m.strip() for m in re.findall(r"<think>(.*?)</think>", texte, flags=re.S))
    return re.sub(r"<think>.*?</think>", "", texte, flags=re.S).strip(), reflexion


def appels_dans_le_texte(texte: str, noms_connus: set[str]) -> list[tuple[str, dict]]:
    """Certains petits modèles écrivent l'appel d'outil dans le texte au lieu du champ prévu.
    Formes reconnues : <tool_call>{...}</tool_call>, bloc ```json {...}```, objet JSON nu."""
    candidats = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", texte, flags=re.S)
    candidats += re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", texte, flags=re.S)
    if not candidats and texte.strip().startswith("{"):
        candidats = [texte.strip()]
    appels = []
    for c in candidats:
        try:
            obj = json.loads(c)
        except json.JSONDecodeError:
            continue
        nom = obj.get("name") or obj.get("outil") or _champ(obj.get("function"), "name")
        args = obj.get("arguments", obj.get("parameters", _champ(obj.get("function"), "arguments", {})))
        if nom in noms_connus:
            appels.append((nom, _args(args)))
    return appels


class CerveauSimule:
    nom = "simulé"


class CerveauOllama:
    nom = "ollama"

    def __init__(self, modele: str = "qwen3:8b", temperature: float = 0.0, contexte: int = 8192, delai: int = 300,
                 reflexion: bool = False):
        try:
            import ollama
        except ImportError as e:
            raise SystemExit("Le paquet 'ollama' n'est pas installé : pip install -r requirements.txt") from e
        self.modele, self.temperature, self.contexte, self.reflexion = modele, temperature, contexte, reflexion
        try:
            import httpx
            limite = httpx.Timeout(delai, connect=10.0)
        except ImportError:
            limite = delai
        self.client = ollama.Client(timeout=limite)   # hôte : variable OLLAMA_HOST, sinon http://localhost:11434

    def verifier(self) -> tuple[bool, str]:
        """Le serveur répond-il et le modèle est-il téléchargé ?"""
        try:
            liste = self.client.list()
        except Exception as e:
            return False, f"Ollama ne répond pas ({e.__class__.__name__}) : lancer Ollama, vérifier OLLAMA_HOST."
        noms = {(_champ(m, "model") or _champ(m, "name") or "") for m in (_champ(liste, "models", []) or [])}
        if noms and self.modele not in noms and f"{self.modele}:latest" not in noms:
            return False, f"Modèle {self.modele} absent d'Ollama : « ollama pull {self.modele} »."
        return True, "ok"

    @staticmethod
    def _convertir(messages):
        sortie = []
        for m in messages:
            if m["role"] == "assistant":
                sortie.append({"role": "assistant", "content": m.get("content", ""),
                               "tool_calls": [{"function": a["function"]} for a in m.get("tool_calls", [])]})
            elif m["role"] == "tool":
                sortie.append({"role": "tool", "content": m["content"], "tool_name": m.get("name", "")})
            else:
                sortie.append({"role": m["role"], "content": m["content"]})
        return sortie

    def chat(self, messages: list[dict], outils: list[dict]) -> dict:
        args = dict(model=self.modele, messages=self._convertir(messages), tools=outils,
                    options={"temperature": self.temperature, "num_ctx": self.contexte})
        try:   # « think » coupe la longue réflexion des modèles comme qwen3 (clients récents)
            rep = self.client.chat(**args, think=self.reflexion)
        except TypeError:
            rep = self.client.chat(**args)
        msg = _champ(rep, "message")
        contenu, reflexion = separer_reflexion(_champ(msg, "content", "") or "")
        reflexion = "\n".join(x for x in (_champ(msg, "thinking", "") or "", reflexion) if x)
        appels = [(_champ(_champ(a, "function"), "name"), _args(_champ(_champ(a, "function"), "arguments", {})))
                  for a in (_champ(msg, "tool_calls", []) or [])]
        return {"content": contenu, "reflexion": reflexion, "tool_calls": appels}


class CerveauSecours:
    """Plusieurs fournisseurs à la suite : si le premier échoue (quota épuisé, panne, clé refusée), le suivant répond.
    Le nom du fournisseur qui a vraiment répondu est gardé dans `dernier`."""

    def __init__(self, cerveaux: list):
        self.cerveaux = cerveaux
        self.modele = " → ".join(f"{c.nom}:{c.modele}" for c in cerveaux)
        self.nom = "secours : " + " → ".join(c.nom for c in cerveaux)
        self.dernier = None

    def verifier(self) -> tuple[bool, str]:
        messages = []
        for c in self.cerveaux:
            ok, m = c.verifier()
            if ok:
                return True, "ok" + (f" (indisponibles : {' ; '.join(messages)})" if messages else "")
            messages.append(f"{c.nom} : {m}")
        return False, " ; ".join(messages)

    def chat(self, messages: list[dict], outils: list[dict]) -> dict:
        erreurs = []
        for c in self.cerveaux:
            try:
                rep = c.chat(messages, outils)
                self.dernier = c.nom
                return rep
            except Exception as e:  # noqa: BLE001 — on passe au fournisseur suivant
                erreurs.append(f"{c.nom} : {e.__class__.__name__} {e}")
        raise RuntimeError("tous les fournisseurs ont échoué — " + " | ".join(erreurs))


class CerveauOpenAI:
    nom = "openai-compatible"

    def __init__(self, url: str, modele: str, cle: str | None = None, temperature: float = 0.0, delai: int = 180,
                 effort: str | None = None):
        self.base = url.rstrip("/")
        self.url = self.base + "/chat/completions"
        self.modele, self.cle, self.temperature, self.delai = modele, cle, temperature, delai
        self.effort = effort   # « reasoning_effort » : moins d'effort = réponses plus rapides et moins chères
        self._connexion = None          # connexion gardée ouverte d'un appel à l'autre (voir _poster)
        self._verrou = threading.Lock()

    def _poster(self, corps: bytes, entetes: dict) -> dict:
        """Envoie la requête en GARDANT la connexion ouverte : sans cela, chaque appel refait la poignée de main
        TLS avec le serveur (plusieurs allers-retours ; depuis Yaoundé vers les États-Unis, souvent 0,5 à 1 s de plus).
        Si un mandataire (proxy) est configuré, on passe par urllib, qui sait le traverser."""
        u = urlparse(self.url)
        if urllib.request.getproxies() and not urllib.request.proxy_bypass(u.hostname or ""):
            req = urllib.request.Request(self.url, data=corps, headers=entetes, method="POST")
            with urllib.request.urlopen(req, timeout=self.delai) as r:
                return json.loads(r.read().decode("utf-8"))
        with self._verrou:
            for essai in range(2):
                if self._connexion is None:
                    if u.scheme == "https":
                        self._connexion = http.client.HTTPSConnection(u.hostname, u.port, timeout=self.delai,
                                                                      context=ssl.create_default_context())
                    else:
                        self._connexion = http.client.HTTPConnection(u.hostname, u.port, timeout=self.delai)
                try:
                    self._connexion.request("POST", u.path + (f"?{u.query}" if u.query else ""), body=corps, headers=entetes)
                    r = self._connexion.getresponse()
                    brut = r.read()
                except (http.client.RemoteDisconnected, http.client.CannotSendRequest, http.client.BadStatusLine,
                        ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                    self._connexion.close()           # connexion fermée par le serveur entre deux appels : on la refait
                    self._connexion = None
                    if essai:
                        raise
                    continue
                except Exception:
                    self._connexion.close()
                    self._connexion = None
                    raise
                if r.getheader("Connection", "").lower() == "close":
                    self._connexion.close()
                    self._connexion = None
                if r.status >= 400:
                    raise urllib.error.HTTPError(self.url, r.status, r.reason, r.headers, io.BytesIO(brut))
                return json.loads(brut.decode("utf-8"))

    @staticmethod
    def _convertir(messages):
        sortie = []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                sortie.append({"role": "assistant", "content": m.get("content") or "",
                               "tool_calls": [{"id": a["id"], "type": "function",
                                               "function": {"name": a["function"]["name"],
                                                            "arguments": json.dumps(a["function"]["arguments"], ensure_ascii=False)}}
                                              for a in m["tool_calls"]]})
            elif m["role"] == "tool":
                sortie.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                sortie.append({"role": m["role"], "content": m.get("content") or ""})
        return sortie

    def verifier(self) -> tuple[bool, str]:
        req = urllib.request.Request(self.base + "/models",
                                     headers={"Authorization": f"Bearer {self.cle}"} if self.cle else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                brut = r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False, f"{self.base} refuse la clé d'API (HTTP {e.code}) : vérifier la clé."
            return False, f"{self.base} répond HTTP {e.code} : vérifier --url."
        except Exception as e:
            return False, f"Le serveur {self.base} ne répond pas ({e.__class__.__name__}) : le lancer ou vérifier --url."
        try:
            noms = sorted({m.get("id") for m in json.loads(brut).get("data", []) if isinstance(m, dict) and m.get("id")})
        except (ValueError, AttributeError):
            noms = []
        if noms and self.modele not in noms and f"models/{self.modele}" not in noms:
            return False, f"Modèle « {self.modele} » introuvable chez {self.base}. Disponibles : {', '.join(noms[:20])}"
        return True, "ok"

    def chat(self, messages: list[dict], outils: list[dict]) -> dict:
        demande = {"model": self.modele, "messages": self._convertir(messages), "tools": outils,
                   "tool_choice": "auto", "temperature": self.temperature}
        if self.effort:
            demande["reasoning_effort"] = self.effort
        corps = json.dumps(demande).encode("utf-8")
        entetes = {"Content-Type": "application/json"}
        if self.cle:
            entetes["Authorization"] = f"Bearer {self.cle}"
        rep = None
        for essai in range(4):   # offres gratuites : quota par minute (HTTP 429) ou surcharge (503) -> on patiente un peu
            try:
                rep = self._poster(corps, entetes)
                break
            except urllib.error.HTTPError as e:
                if e.code == 400 and self.effort:   # modèle qui n'accepte pas reasoning_effort : on réessaie sans
                    self.effort = None
                    demande.pop("reasoning_effort", None)
                    corps = json.dumps(demande).encode("utf-8")
                    continue
                if e.code not in (429, 500, 502, 503) or essai == 3:
                    raise
                try:
                    attente = float(e.headers.get("Retry-After") or 0)
                except (TypeError, ValueError):
                    attente = 0
                time.sleep(min(30.0, attente or 2.0 * 2 ** essai))
        msg = rep["choices"][0]["message"]
        contenu, reflexion = separer_reflexion(msg.get("content") or "")
        reflexion = "\n".join(x for x in (msg.get("reasoning_content") or "", reflexion) if x)
        appels = [(a["function"]["name"], _args(a["function"].get("arguments"))) for a in (msg.get("tool_calls") or [])]
        return {"content": contenu, "reflexion": reflexion, "tool_calls": appels}
