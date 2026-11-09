"""Agents' "brains": what chooses the tools at each turn.

- CerveauSimule  : no AI; each agent follows its hand-written policy (`politique_simulee`).
- CerveauOllama  : a local model served by Ollama (https://ollama.com), with tool calling.
- CerveauOpenAI  : any server compatible with OpenAI's "chat/completions" API: Groq, OpenRouter, Gemini, Mistral,
                   xAI, Anthropic (compatibility layer), OpenAI, llama.cpp (llama-server), LM Studio, vLLM, or a sandbox.

All return {"content": str, "reflexion": str, "tool_calls": [(name, arguments)]}.
Internal messages follow this format:
    {"role": "assistant", "content": ..., "tool_calls": [{"id": "a1", "function": {"name": ..., "arguments": {...}}}]}
    {"role": "tool", "tool_call_id": "a1", "name": ..., "content": ...}
Each brain converts them for its server.
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
    """Separates <think>…</think> tags ("reasoning" models) from the rest of the text."""
    texte = texte or ""
    reflexion = "\n".join(m.strip() for m in re.findall(r"<think>(.*?)</think>", texte, flags=re.S))
    return re.sub(r"<think>.*?</think>", "", texte, flags=re.S).strip(), reflexion


def appels_dans_le_texte(texte: str, noms_connus: set[str]) -> list[tuple[str, dict]]:
    """Some small models write the tool call in the text instead of the dedicated field.
    Recognised forms: <tool_call>{...}</tool_call>, ```json {...}``` block, bare JSON object."""
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
            raise SystemExit("The 'ollama' package is not installed: pip install ollama") from e
        self.modele, self.temperature, self.contexte, self.reflexion = modele, temperature, contexte, reflexion
        try:
            import httpx
            limite = httpx.Timeout(delai, connect=10.0)
        except ImportError:
            limite = delai
        self.client = ollama.Client(timeout=limite)   # host: OLLAMA_HOST variable, otherwise http://localhost:11434

    def verifier(self) -> tuple[bool, str]:
        """Is the server answering and is the model downloaded?"""
        try:
            liste = self.client.list()
        except Exception as e:
            return False, f"Ollama is not responding ({e.__class__.__name__}): start Ollama, check OLLAMA_HOST."
        noms = {(_champ(m, "model") or _champ(m, "name") or "") for m in (_champ(liste, "models", []) or [])}
        if noms and self.modele not in noms and f"{self.modele}:latest" not in noms:
            return False, f"Model {self.modele} is not in Ollama: run 'ollama pull {self.modele}'."
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
        try:   # "think" cuts the long reasoning of models such as qwen3 (recent clients)
            rep = self.client.chat(**args, think=self.reflexion)
        except TypeError:
            rep = self.client.chat(**args)
        msg = _champ(rep, "message")
        contenu, reflexion = separer_reflexion(_champ(msg, "content", "") or "")
        reflexion = "\n".join(x for x in (_champ(msg, "thinking", "") or "", reflexion) if x)
        appels = [(_champ(_champ(a, "function"), "name"), _args(_champ(_champ(a, "function"), "arguments", {})))
                  for a in (_champ(msg, "tool_calls", []) or [])]
        return {"content": contenu, "reflexion": reflexion, "tool_calls": appels}

    def lire_document(self, octets: bytes | None, mime: str, consigne: str, texte: str = "") -> str:
        """Reads a patient document on THIS computer: nothing leaves it. A photo needs a model that sees images
        (e.g. qwen3-vl:8b, chosen by the variable MEDIMCOM_MODELE_VISION); otherwise only the text is read."""
        import base64
        import os
        modele = os.environ.get("MEDIMCOM_MODELE_VISION") or self.modele
        if octets and not os.environ.get("MEDIMCOM_MODELE_VISION") and "vl" not in modele and "vision" not in modele:
            raise RuntimeError(f"model {modele} cannot read images: run 'ollama pull qwen3-vl:8b', then "
                               "MEDIMCOM_MODELE_VISION=qwen3-vl:8b")
        message = {"role": "user", "content": consigne + (f"\n\nTEXTE DU DOCUMENT :\n{texte[:12000]}" if texte else "")}
        if octets:
            message["images"] = [base64.b64encode(octets).decode()]
        self.modele_document = modele
        args = dict(model=modele, messages=[message], options={"temperature": 0, "num_ctx": max(self.contexte, 8192)})
        try:
            rep = self.client.chat(**args, think=False)
        except TypeError:
            rep = self.client.chat(**args)
        return separer_reflexion(_champ(_champ(rep, "message"), "content", "") or "")[0]


class CerveauSecours:
    """Several providers in a row: if the first fails (quota exhausted, outage, key refused), the next one answers.
    The name of the provider that actually answered is kept in `dernier`."""

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

    def lire_document(self, *a, **k) -> str:
        erreurs = []
        for c in self.cerveaux:
            if hasattr(c, "lire_document"):
                try:
                    return c.lire_document(*a, **k)
                except Exception as e:  # noqa: BLE001
                    erreurs.append(f"{c.nom} : {e}")
        raise RuntimeError("aucun fournisseur n'a pu lire le document — " + " | ".join(erreurs))

    def chat(self, messages: list[dict], outils: list[dict]) -> dict:
        erreurs = []
        for c in self.cerveaux:
            try:
                rep = c.chat(messages, outils)
                self.dernier = c.nom
                return rep
            except Exception as e:  # noqa: BLE001 — on passe au fournisseur suivant
                erreurs.append(f"{c.nom} : {e.__class__.__name__} {e}")
        raise RuntimeError("all providers failed — " + " | ".join(erreurs))


def choisir_modele(donnees: list[dict], demande: str) -> str | None:
    """Requested model missing for this key: a model of the same family is taken (prefix "grok", "gemini"…),
    preferably fast ("non-reasoning", "fast", "mini") for a live consultation, newest first."""
    famille = re.split(r"[-_.]", demande)[0].lower()
    ids = [m["id"] for m in donnees if m["id"].lower().startswith(famille)
           and not any(x in m["id"].lower() for x in ("image", "vision", "imagine", "video", "embed", "tts", "audio",
                                                    "realtime", "transcribe", "search", "moderation", "whisper", "dall"))]
    if not ids:
        return None
    rapides = [i for i in ids if any(x in i.lower() for x in ("non-reasoning", "fast", "mini"))]
    return sorted(rapides or ids, key=lambda i: [int(n) for n in re.findall(r"\d+", i)][:3], reverse=True)[0]


# HTTP identity of the requests: without it, urllib announces itself as "Python-urllib/3.x", a signature that the
# Cloudflare firewall in front of some providers (Groq…) blocks with "error code: 1010" (HTTP 403), while curl gets
# through.
AGENT_HTTP = {"User-Agent": "MEDIMCOM-IA/1.0 (prototype hackathon AI for Good)", "Accept": "application/json"}


def contexte_tls():
    """Certificates for HTTPS: those of "certifi" if installed (python.org's Python on macOS often lacks the
    system certificates, and ALL providers then fail with CERTIFICATE_VERIFY_FAILED)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _conseil_http(texte: str) -> str:
    m = re.match(r"HTTP (\d+)", texte)
    code = int(m.group(1)) if m else 0
    bas = texte.lower()
    if "error code: 10" in bas:
        return texte + (" — the provider's Cloudflare firewall blocked the request signature, not the key "
                        "(fixed in this version; otherwise switch off VPN or proxy, or use another network)")
    if code == 429 or "rate limit" in bas or "quota" in bas:
        return texte + " — quota reached (free tier: per minute or per day): wait, or add CLE_SECOURS= in CLE_API.txt"
    if "credit" in bas or "billing" in bas or "spending limit" in bas:
        return texte + " — no credits left or spending limit reached (provider console)"
    if code in (401, 403):
        return texte + " — key refused: check it or create a new one"
    if code == 404 or "model" in bas and ("not found" in bas or "does not exist" in bas or "decommission" in bas):
        return texte + " — model retired or unknown: choose another one (MODELE= in CLE_API.txt)"
    return texte


def expliquer(e: BaseException) -> str:
    """Plain cause of a network failure, with what to do (never the key)."""
    import socket
    if isinstance(e, urllib.error.HTTPError):
        return _conseil_http(f"HTTP {e.code} : {lire_erreur(e) or e.reason}")
    if isinstance(e, RuntimeError) and str(e).startswith("HTTP"):
        return _conseil_http(str(e))
    raison = getattr(e, "reason", e)
    texte = re.sub(r"\b(xai|sk|gsk)[-_][A-Za-z0-9_\-]{6,}", "[clé masquée]", f"{raison}")
    if isinstance(raison, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in texte:
        return ("HTTPS certificates missing on this computer (CERTIFICATE_VERIFY_FAILED): 'pip install certifi' "
                "in the Python in use, or on macOS run 'Install Certificates.command' (Applications/Python folder)")
    if isinstance(raison, socket.gaierror) or "Name or service not known" in texte or "nodename" in texte:
        return "provider address not found: no Internet access or DNS failure on this computer"
    if isinstance(raison, (socket.timeout, TimeoutError)) or "timed out" in texte:
        return "timed out: Internet connection too slow or cut (the model will be retried automatically)"
    if isinstance(raison, (ConnectionRefusedError, ConnectionResetError)):
        return f"connection refused or reset ({raison.__class__.__name__}): firewall, proxy or VPN?"
    return f"{raison.__class__.__name__}: {texte}"[:300]


def lire_erreur(e) -> str:
    """Error message returned by the provider (JSON body of the HTTP answer), never quoting the key."""
    try:
        brut = e.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    try:
        j = json.loads(brut)
        msg = j.get("error") if isinstance(j, dict) else None
        msg = (msg.get("message") if isinstance(msg, dict) else msg) or j.get("message") or j.get("detail") or brut
    except (ValueError, AttributeError):
        msg = brut
    msg = re.sub(r"\b(xai|sk|gsk)[-_][A-Za-z0-9_\-]{6,}", "[clé masquée]", str(msg))
    msg = re.sub(r"(provided:\s*)(?!\[)\S+", r"\1[clé masquée]", msg)
    return " ".join(msg.split())[:300].rstrip(". ")


class CerveauOpenAI:
    nom = "openai-compatible"

    def __init__(self, url: str, modele: str, cle: str | None = None, temperature: float = 0.0, delai: int = 180,
                 effort: str | None = None):
        self.base = url.rstrip("/")
        self.url = self.base + "/chat/completions"
        self.modele, self.cle, self.temperature, self.delai = modele, cle, temperature, delai
        self.effort = effort   # "reasoning_effort": less effort = faster and cheaper answers
        self._connexion = None          # connection kept open from one call to the next (see _poster)
        self._verrou = threading.Lock()
        # Claude (Anthropic) through its OpenAI-compatible layer: no "temperature" below 1 on recent models (otherwise
        # HTTP 400), "max_tokens" advised, key also accepted in "x-api-key".
        self.anthropic = "anthropic.com" in self.base
        self.sans_temperature = self.anthropic

    def _entetes(self, json_: bool = True) -> dict:
        e = {**AGENT_HTTP, **({"Content-Type": "application/json"} if json_ else {})}
        if self.cle:
            e["Authorization"] = f"Bearer {self.cle}"
            if self.anthropic:
                e["x-api-key"], e["anthropic-version"] = self.cle, "2023-06-01"
        return e

    def _reglages(self, demande: dict, temperature: float) -> dict:
        if not self.sans_temperature:
            demande["temperature"] = temperature
        if self.anthropic:
            demande.setdefault("max_tokens", 4096)
        return demande

    def _poster(self, corps: bytes, entetes: dict) -> dict:
        """Sends the request KEEPING the connection open: otherwise each call redoes the TLS handshake with the
        server (several round trips; from Yaoundé to the United States, often 0.5 to 1 s more).
        If a proxy is configured, urllib is used, as it knows how to go through it."""
        u = urlparse(self.url)
        if urllib.request.getproxies() and not urllib.request.proxy_bypass(u.hostname or ""):
            req = urllib.request.Request(self.url, data=corps, headers=entetes, method="POST")
            with urllib.request.urlopen(req, timeout=self.delai, context=contexte_tls()) as r:
                return json.loads(r.read().decode("utf-8"))
        with self._verrou:
            for essai in range(2):
                if self._connexion is None:
                    if u.scheme == "https":
                        self._connexion = http.client.HTTPSConnection(u.hostname, u.port, timeout=self.delai,
                                                                      context=contexte_tls())
                    else:
                        self._connexion = http.client.HTTPConnection(u.hostname, u.port, timeout=self.delai)
                try:
                    self._connexion.request("POST", u.path + (f"?{u.query}" if u.query else ""), body=corps, headers=entetes)
                    r = self._connexion.getresponse()
                    brut = r.read()
                except (http.client.RemoteDisconnected, http.client.CannotSendRequest, http.client.BadStatusLine,
                        ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                    self._connexion.close()           # connection closed by the server between two calls: it is reopened
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
        req = urllib.request.Request(self.base + "/models", headers=self._entetes(json_=False))
        try:
            with urllib.request.urlopen(req, timeout=30, context=contexte_tls()) as r:   # 30 s : connexions lentes
                brut = r.read()
        except urllib.error.HTTPError as e:
            detail = lire_erreur(e)
            if "1010" in detail or "1020" in detail:
                return False, f"{self.base} blocks the request (HTTP {e.code}, {detail}): {_conseil_http('HTTP 403 : ' + detail).split(' — ', 1)[-1]}."
            if e.code in (401, 403) or "key" in detail.lower() or "clé" in detail.lower():
                return False, (f"{self.base} refuses the API key (HTTP {e.code}): {detail or 'key missing or invalid'}. "
                               "Check the key in CLE_API.txt (active key, credits or quota left).")
            return False, f"{self.base} answers HTTP {e.code}: {detail or 'check the URL and the model name'}."
        except Exception as e:
            return False, f"{self.base} unreachable: {expliquer(e)}."
        try:
            donnees = [m for m in json.loads(brut).get("data", []) if isinstance(m, dict) and m.get("id")]
        except (ValueError, AttributeError):
            donnees = []
        noms = sorted({m["id"] for m in donnees} | {a for m in donnees for a in (m.get("aliases") or [])})   # alias compris
        if noms and self.modele not in noms and f"models/{self.modele}" not in noms:
            remplacant = choisir_modele(donnees, self.modele)
            if remplacant:
                demande, self.modele = self.modele, remplacant
                return True, f"Model '{demande}' is not available for this key: '{remplacant}' used instead."
            return False, f"Model '{self.modele}' not found at {self.base}. Available: {', '.join(noms[:20])}"
        return True, "ok"

    def lire_document(self, octets: bytes | None, mime: str, consigne: str, texte: str = "") -> str:
        """Reads a patient document: image (photo of a prescription, box, receipt) sent to the model if it accepts
        images, or text. Returns the model's raw answer (JSON expected by the instruction)."""
        import base64
        contenu = [{"type": "text", "text": consigne + (f"\n\nTEXTE DU DOCUMENT :\n{texte[:12000]}" if texte else "")}]
        if octets:
            contenu.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(octets).decode()}",
                                                               "detail": "high"}})
        demande = self._reglages({"model": self.modele, "messages": [{"role": "user", "content": contenu}]}, 0)
        try:
            rep = self._poster(json.dumps(demande).encode("utf-8"), self._entetes())
        except urllib.error.HTTPError as e:
            detail = lire_erreur(e)
            if e.code == 400 and "temperature" in detail.lower() and "temperature" in demande:
                self.sans_temperature = True
                return self.lire_document(octets, mime, consigne, texte)
            raise RuntimeError(f"HTTP {e.code} : {detail or e.reason}") from None
        return separer_reflexion(rep["choices"][0]["message"].get("content") or "")[0]

    def chat(self, messages: list[dict], outils: list[dict]) -> dict:
        demande = self._reglages({"model": self.modele, "messages": self._convertir(messages), "tools": outils,
                                  "tool_choice": "auto"}, self.temperature)
        if self.effort and not self.anthropic:
            demande["reasoning_effort"] = self.effort
        corps = json.dumps(demande).encode("utf-8")
        entetes = self._entetes()
        rep = None
        for essai in range(4):   # free tiers: quota per minute (HTTP 429) or overload (503) -> wait a little
            try:
                rep = self._poster(corps, entetes)
                break
            except urllib.error.HTTPError as e:
                detail = lire_erreur(e)
                # model refusing "temperature" (reasoning models, recent Claude): retry without it
                if e.code == 400 and "temperature" in detail.lower() and "temperature" in demande:
                    self.sans_temperature = True
                    demande.pop("temperature", None)
                    corps = json.dumps(demande).encode("utf-8")
                    continue
                if e.code == 400 and self.effort:   # model not accepting reasoning_effort: retry without it
                    self.effort = None
                    demande.pop("reasoning_effort", None)
                    corps = json.dumps(demande).encode("utf-8")
                    continue
                if e.code not in (429, 500, 502, 503) or essai == 3:
                    raise RuntimeError(f"HTTP {e.code} : {detail or e.reason}") from None
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
