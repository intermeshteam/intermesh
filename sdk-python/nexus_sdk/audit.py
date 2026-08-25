import hashlib
import json
import time
from typing import Optional, List, Dict, Any


class AuditEntry:
    """
    Une entrée immuable dans le journal d'audit Nexus.
    Chaque entrée est scellée par son empreinte SHA-256 incluant le hash de l'entrée précédente.
    """

    def __init__(
        self,
        index: int,
        event_type: str,
        sender: str,
        target: Optional[str],
        metadata: Dict[str, Any],
        prev_hash: str,
        timestamp: Optional[float] = None,
        entry_hash: Optional[str] = None
    ):
        self.index = index
        self.timestamp = timestamp or time.time()
        self.event_type = event_type
        self.sender = sender
        self.target = target
        self.metadata = metadata
        self.prev_hash = prev_hash
        self.hash = entry_hash or self.compute_hash()

    def compute_hash(self) -> str:
        """Calcule le hash SHA-256 de cette entrée lié à l'entrée précédente."""
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "sender": self.sender,
            "target": self.target,
            "metadata": self.metadata,
            "prev_hash": self.prev_hash
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "sender": self.sender,
            "target": self.target,
            "metadata": self.metadata,
            "prev_hash": self.prev_hash,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEntry":
        """
        Reconstruit une entrée depuis sa forme sérialisée.

        Le hash stocké est conservé tel quel, sans être recalculé : c'est
        précisément l'écart entre le hash stocké et le hash recalculé qui
        révèle une altération lors de verify_integrity().
        """
        return cls(
            index=data["index"],
            event_type=data["event_type"],
            sender=data["sender"],
            target=data.get("target"),
            metadata=data.get("metadata", {}),
            prev_hash=data["prev_hash"],
            timestamp=data.get("timestamp"),
            entry_hash=data.get("hash"),
        )


class ImmutableAuditLog:
    """
    Registre d'audit chaîné (Merkle-Chain).
    Permet d'ajouter des événements et de vérifier l'intégrité globale du journal.
    """

    def __init__(self, entries: Optional[List[dict]] = None, on_append=None):
        """
        Args:
            entries:   Chaîne existante à reprendre (forme sérialisée). Si elle
                       est vide ou absente, un bloc genesis est créé.
            on_append: Callback appelé avec chaque nouvelle AuditEntry, pour
                       l'écrire dans un stockage durable.
        """
        self.chain: List[AuditEntry] = []
        self._on_append = on_append

        if entries:
            self.chain = [AuditEntry.from_dict(e) for e in entries]
        else:
            self._create_genesis_block()

    def _create_genesis_block(self):
        """Crée le bloc racine (Genesis) de la chaîne d'audit."""
        genesis = AuditEntry(
            index=0,
            event_type="GENESIS",
            sender="nexus_system",
            target=None,
            metadata={"system": "Nexus Protocol Immutable Audit Log Initialized"},
            prev_hash="0" * 64,
            timestamp=time.time()
        )
        self.chain.append(genesis)
        if self._on_append:
            self._on_append(genesis)

    def log(self, event_type: str, sender: str, target: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """Ajoute un nouvel événement au journal et le scelle cryptographiquement."""
        prev_entry = self.chain[-1]
        new_entry = AuditEntry(
            index=len(self.chain),
            event_type=event_type,
            sender=sender,
            target=target,
            metadata=metadata or {},
            prev_hash=prev_entry.hash
        )
        self.chain.append(new_entry)
        if self._on_append:
            self._on_append(new_entry)
        return new_entry

    def verify_integrity(self) -> bool:
        """
        Vérifie l'intégrité mathématique complète de toute la chaîne d'audit.
        Retourne False si une quelconque entrée a été modifiée ou supprimée.
        """
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]

            # 1. Vérifier la liaison avec le bloc précédent
            if curr.prev_hash != prev.hash:
                return False

            # 2. Vérifier que le hash correspond au contenu actuel
            if curr.hash != curr.compute_hash():
                return False

        return True

    def export_json(self) -> str:
        return json.dumps([e.to_dict() for e in self.chain], indent=2)
