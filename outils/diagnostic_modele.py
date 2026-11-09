"""Why is the model "unavailable"? For each provider whose key is present, tests the whole path:
Internet -> address -> HTTPS (certificates) -> key -> model -> call with tools (as the assistant does).

    python3 outils/diagnostic_modele.py                     # every provider whose key is found (CLE_API.txt first)
    python3 outils/diagnostic_modele.py groq                # one provider only
    python3 outils/diagnostic_modele.py xai --modele grok-4.20-0309-non-reasoning

Never prints the keys. Copy the whole output to share it.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from medimcom.cerveaux import CerveauOpenAI, choisir_modele, contexte_tls, expliquer  # noqa: E402
from medimcom.session import ENV_PERSONNEL, FOURNISSEURS, RACINE, charger_env  # noqa: E402

OUTIL = [{"type": "function", "function": {"name": "noter", "description": "Records a fact.",
                                           "parameters": {"type": "object", "properties": {"fait": {"type": "string"}},
                                                          "required": ["fait"]}}}]


def ligne(ok: bool | None, texte: str):
    print(f"  {'✓' if ok else ('✗' if ok is False else '·')} {texte}")


def tester(nom: str, modele: str | None, effort: str | None) -> bool:
    f = FOURNISSEURS[nom]
    cle = os.environ.get(f["variable_cle"])
    print(f"\n== {f['nom']} ==")
    if not cle:
        ligne(None, f"no key {f['variable_cle']}: not tested")
        return False
    ligne(True, f"key {f['variable_cle']} found ({len(cle)} characters, starts with '{cle[:4]}…')")
    if cle != cle.strip() or " " in cle or "\"" in cle:
        ligne(False, "the key contains spaces or quotes: copy it again with nothing around it")
    hote = urlparse(f["url"]).hostname
    try:
        ip = socket.getaddrinfo(hote, 443)[0][4][0]
        ligne(True, f"address {hote} found ({ip})")
    except OSError as e:
        ligne(False, f"address {hote} not found ({e}): no Internet, or DNS failure")
        return False
    debut = time.time()
    cerveau = CerveauOpenAI(f["url"], modele or f["modele"], cle=cle, delai=90, effort=effort)
    req = urllib.request.Request(f["url"] + "/models", headers=cerveau._entetes(json_=False))   # same headers as the server
    try:
        with urllib.request.urlopen(req, timeout=30, context=contexte_tls()) as r:
            donnees = json.loads(r.read()).get("data", [])
            date = r.headers.get("Date")
        ligne(True, f"HTTPS and key accepted ({time.time() - debut:.1f} s, {len(donnees)} models)")
    except urllib.error.HTTPError as e:
        date = e.headers.get("Date") if e.headers else None
        ligne(False, f"model list refused: {expliquer(e)}")
        donnees = None
    except Exception as e:  # noqa: BLE001
        ligne(False, f"HTTPS connection impossible: {expliquer(e)}")
        return False
    if date:
        ecart = abs(parsedate_to_datetime(date).timestamp() - time.time())
        ligne(ecart < 300, f"computer clock: {ecart:.0f} s off" + (" — too far: set the time right" if ecart >= 300 else ""))
    if donnees is None:
        return False
    demande = modele or f["modele"]
    noms = {m.get("id") for m in donnees if isinstance(m, dict)} | {a for m in donnees if isinstance(m, dict) for a in (m.get("aliases") or [])}
    if noms and demande not in noms:
        rempl = choisir_modele([m for m in donnees if isinstance(m, dict) and m.get("id")], demande)
        ligne(False, f"model '{demande}' not available for this key" + (f": '{rempl}' will be used" if rempl else ""))
        if rempl:
            demande = rempl
        else:
            print("    available:", ", ".join(sorted(n for n in noms if n)[:25]))
            return False
    else:
        ligne(True, f"model '{demande}' available")
    cerveau.modele = demande
    debut = time.time()
    try:
        rep = cerveau.chat([{"role": "system", "content": "This is a test. Call the tool noter with the fact 'test'."},
                            {"role": "user", "content": "Connection test."}], OUTIL)
        ligne(True, f"model call succeeded ({time.time() - debut:.1f} s); tool called: {'yes' if rep.get('tool_calls') else 'no (text answer)'}")
        return True
    except Exception as e:  # noqa: BLE001
        ligne(False, f"model call refused ({time.time() - debut:.1f} s): {expliquer(e)}")
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fournisseur", nargs="?", choices=list(FOURNISSEURS))
    p.add_argument("--modele")
    p.add_argument("--effort", default="low")
    a = p.parse_args()
    from medimcom.cle_api import appliquer
    from medimcom.session import Config
    print(appliquer(Config()))          # the key of CLE_API.txt first (it is the one the server will use)
    n = charger_env()
    print(f"Python {platform.python_version()} ({sys.executable}) · {platform.system()} {platform.release()}")
    try:
        import certifi  # noqa: F401
        ligne(True, "HTTPS certificates: certifi installed")
    except ImportError:
        ligne(None, "HTTPS certificates: the system's (if CERTIFICATE_VERIFY_FAILED appears: pip install certifi)")
    ligne(None, f"other keys read: {n} (files {RACINE / '.env'} and {ENV_PERSONNEL})")
    proxies = {k: v for k, v in urllib.request.getproxies().items() if k in ("http", "https", "all")}
    if proxies:
        ligne(None, f"proxy configured: {', '.join(proxies)} — if it is down, every provider fails")
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=8).close()
        ligne(True, "Internet access")
    except OSError as e:
        ligne(False, f"no Internet access ({e}): check the Wi-Fi or mobile data")
    resultats = {nom: tester(nom, a.modele, a.effort) for nom in ([a.fournisseur] if a.fournisseur else FOURNISSEURS)}
    print("\nSummary:", ", ".join(f"{k} {'OK' if v else 'FAILED'}" for k, v in resultats.items()
                                  if os.environ.get(FOURNISSEURS[k]["variable_cle"]) or a.fournisseur))
    if any(resultats.values()):
        print("Start MEDIMCOM IA: bash lancer_local.sh   (the provider of CLE_API.txt is used)")


if __name__ == "__main__":
    main()
