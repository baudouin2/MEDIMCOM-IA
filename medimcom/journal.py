"""Tamper-evident journal: each line contains the fingerprint of the previous one.

Any later change (of a line or of the order of lines) is detected by `verifier()`.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _empreinte(ligne: dict) -> str:
    copie = {k: v for k, v in ligne.items() if k != "empreinte"}
    brut = json.dumps(copie, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(brut).hexdigest()


class Journal:
    def __init__(self):
        self.lignes: list[dict] = []

    def ajouter(self, agent: str, type_evt: str, contenu) -> dict:
        ligne = {
            "n": len(self.lignes) + 1,
            "heure": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "agent": agent,
            "type": type_evt,          # raisonnement, action, message, evenement, verdict...
            # frozen copy: an object modified later must not change what was logged
            "contenu": json.loads(json.dumps(contenu, ensure_ascii=False, default=str)),
            "precedent": self.lignes[-1]["empreinte"] if self.lignes else "0" * 64,
        }
        ligne["empreinte"] = _empreinte(ligne)
        self.lignes.append(ligne)
        return ligne

    def verifier(self) -> str:
        for i, ligne in enumerate(self.lignes):
            if _empreinte(ligne) != ligne["empreinte"]:
                return f"Ligne {ligne['n']} modifiée"
            attendu = self.lignes[i - 1]["empreinte"] if i else "0" * 64
            if ligne["precedent"] != attendu:
                return f"Chaîne rompue à la ligne {ligne['n']}"
        return "Journal intact"

    def sauver(self, chemin: str | Path) -> None:
        Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        Path(chemin).write_text(json.dumps(self.lignes, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    @classmethod
    def charger(cls, chemin: str | Path) -> "Journal":
        j = cls()
        j.lignes = json.loads(Path(chemin).read_text(encoding="utf-8"))
        return j
