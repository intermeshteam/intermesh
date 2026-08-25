import json
import time
import uuid
from enum import Enum
from typing import Any, Optional


class MessageType(str, Enum):
    REGISTER = "register"
    REGISTERED = "registered"
    MESSAGE = "message"
    REQUEST = "request"
    RESPONSE = "response"
    ACK = "ack"
    ERROR = "error"
    WHO_IS = "who_is"
    IDENTITY = "identity"
    DISCOVER = "discover"
    DISCOVER_RESULT = "discover_result"
    TASK_SUBMIT = "task_submit"
    TASK_ASSIGN = "task_assign"
    TASK_UPDATE = "task_update"
    
    # Peering et Fédération Inter-Hubs
    PEER_CONNECT = "peer_connect"          # Hub A ➜ Hub B (Établissement du lien)
    PEER_CONNECTED = "peer_connected"      # Hub B ➜ Hub A (Validation du peering)
    FEDERATION_RELAY = "federation_relay"  # Hub A ➜ Hub B (Routage d'un message tiers)

    # Console d'administration.
    # ADMIN_REQUEST exige une identité authentifiée par clé d'API : les
    # rôles auto-déclarés à l'enregistrement ne suffisent jamais.
    ADMIN_REQUEST = "admin_request"        # Console ➜ Hub (commande)
    ADMIN_RESULT = "admin_result"          # Hub ➜ Console (réponse)
    TELEMETRY = "telemetry_event"          # Hub ➜ Observateurs (flux temps réel)


class NexusMessage:
    def __init__(
        self,
        type: MessageType,
        sender: str,
        to: Optional[str] = None,
        content: Any = None,
        reply_to: Optional[str] = None,
        msg_id: Optional[str] = None,
        timestamp: Optional[float] = None,
        version: str = "nexus/v1",
        token: Optional[str] = None
    ):
        self.id = msg_id or str(uuid.uuid4())
        self.version = version
        self.type = MessageType(type)
        self.sender = sender
        self.to = to
        self.content = content
        self.reply_to = reply_to
        self.timestamp = timestamp or time.time()
        self.token = token

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "version": self.version,
            "type": self.type.value,
            "sender": self.sender,
            "to": self.to,
            "content": self.content,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp,
        }
        if self.token:
            d["token"] = self.token
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "NexusMessage":
        return cls(
            msg_id=data.get("id"),
            version=data.get("version", "nexus/v1"),
            type=MessageType(data["type"]),
            sender=data.get("sender", ""),
            to=data.get("to"),
            content=data.get("content"),
            reply_to=data.get("reply_to"),
            timestamp=data.get("timestamp"),
            token=data.get("token"),
        )

    @classmethod
    def from_json(cls, raw_json: str) -> "NexusMessage":
        return cls.from_dict(json.loads(raw_json))
