"""Direct messaging between agents (and to the doctor / the translator)."""
from dataclasses import dataclass, field
from itertools import count

TYPES = {"demande", "information", "alerte", "proposition", "desaccord"}
_ids = count(1)


@dataclass
class Message:
    de: str
    a: str
    type: str
    contenu: str
    repond_a: int | None = None
    id: int = field(default_factory=lambda: next(_ids))

    def __str__(self) -> str:
        return f"[{self.type}] {self.de} → {self.a} : {self.contenu}"


class Messagerie:
    def __init__(self, journal, destinataires: set[str]):
        self.journal = journal
        self.boites: dict[str, list[Message]] = {d: [] for d in destinataires}
        self.historique: list[Message] = []

    def envoyer(self, de: str, a: str, type_msg: str, contenu: str, repond_a: int | None = None) -> str:
        if type_msg not in TYPES:
            return f"Refusé : type « {type_msg} » inconnu (types permis : {', '.join(sorted(TYPES))})."
        if a not in self.boites:
            return f"Refusé : destinataire « {a} » inconnu (permis : {', '.join(sorted(self.boites))})."
        if a == de:
            return "Refusé : un agent ne s'écrit pas à lui-même."
        m = Message(de, a, type_msg, contenu, repond_a)
        self.boites[a].append(m)
        self.historique.append(m)
        self.journal.ajouter(de, "message", {"id": m.id, "a": a, "type": type_msg, "contenu": contenu, "repond_a": repond_a})
        return f"Message {m.id} envoyé à {a}."

    def lire(self, agent: str) -> list[Message]:
        msgs, self.boites[agent] = self.boites[agent], []
        return msgs
