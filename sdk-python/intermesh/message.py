import json
import time
import uuid
from enum import Enum
from typing import Any, Optional


class ValidationError(ValueError):
    """Exception levee en cas de violation de schema ou de type sur un message."""
    pass


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
    
    # Peering et Federation Inter-Hubs
    PEER_CONNECT = "peer_connect"          # Hub A -> Hub B
    PEER_CONNECTED = "peer_connected"      # Hub B -> Hub A
    FEDERATION_RELAY = "federation_relay"  # Hub A -> Hub B

    # Console d'administration
    ADMIN_REQUEST = "admin_request"        # Console -> Hub
    ADMIN_RESULT = "admin_result"          # Hub -> Console
    TELEMETRY = "telemetry_event"          # Hub -> Observateurs


class InterMeshMessage:
    def __init__(
        self,
        type: MessageType,
        sender: str,
        to: Optional[str] = None,
        content: Any = None,
        reply_to: Optional[str] = None,
        msg_id: Optional[str] = None,
        timestamp: Optional[float] = None,
        version: str = "intermesh/v1",
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
    def from_dict(cls, data: dict) -> "InterMeshMessage":
        if not isinstance(data, dict):
            raise ValidationError("Le payload du message doit etre un dictionnaire JSON.")

        # Verification des champs obligatoires
        mandatory = ["type", "sender"]
        for field in mandatory:
            if field not in data:
                raise ValidationError(f"Champ obligatoire absent : '{field}'")

        # Validation de la version
        version = data.get("version", "intermesh/v1")
        if version != "intermesh/v1":
            raise ValidationError(f"Version de protocole non supportee : '{version}'")

        # Validation du type de message
        type_raw = data["type"]
        try:
            msg_type = MessageType(type_raw)
        except ValueError:
            raise ValidationError(f"Type de message inconnu ou invalide : '{type_raw}'")

        # Validation de l'identifiant
        msg_id = data.get("id")
        if msg_id is not None and not isinstance(msg_id, str):
            raise ValidationError("Le champ 'id' doit etre une chaine de caracteres.")

        # Validation de l'expediteur
        sender = data["sender"]
        if not isinstance(sender, str) or not sender.strip():
            raise ValidationError("Le champ 'sender' doit etre une chaine de caracteres non vide.")

        # Validation du destinataire optionnel
        to = data.get("to")
        if to is not None and not isinstance(to, str):
            raise ValidationError("Le champ 'to' doit etre une chaine de caracteres.")

        # Validation de la liaison de message
        reply_to = data.get("reply_to")
        if reply_to is not None and not isinstance(reply_to, str):
            raise ValidationError("Le champ 'reply_to' doit etre une chaine de caracteres.")

        # Validation du timestamp
        timestamp = data.get("timestamp")
        if timestamp is not None and not isinstance(timestamp, (int, float)):
            raise ValidationError("Le champ 'timestamp' doit etre un timestamp numerique.")

        # Validation du jeton de securite optionnel
        token = data.get("token")
        if token is not None and not isinstance(token, str):
            raise ValidationError("Le champ 'token' doit etre une chaine de caracteres.")

        return cls(
            msg_id=msg_id,
            version=version,
            type=msg_type,
            sender=sender,
            to=to,
            content=data.get("content"),
            reply_to=reply_to,
            timestamp=timestamp,
            token=token,
        )

    @classmethod
    def from_json(cls, raw_json: str) -> "InterMeshMessage":
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValidationError(f"JSON invalide : {str(e)}")
        return cls.from_dict(data)
