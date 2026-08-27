import hashlib
import json
import time
import uuid
from typing import Optional, List


class AgentIdentity:
    def __init__(
        self,
        name: str,
        org_id: str = "default",
        capabilities: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        agent_id: Optional[str] = None,
        created_at: Optional[float] = None,
        metadata: Optional[dict] = None,
        public_key: Optional[str] = None
    ):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.org_id = org_id
        self.name = name
        # Qualification systématique : org_id/name (ex: default/1line_worker)
        self.qualified_name = f"{org_id}/{name}" if "/" not in name else name
        self.capabilities = capabilities or []
        self.roles = roles or ["standard"]
        self.permissions = permissions or []
        self.created_at = created_at or time.time()
        self.metadata = metadata or {}
        self.public_key = public_key
        self.fingerprint = self._compute_fingerprint()

    def _compute_fingerprint(self) -> str:
        data = {
            "agent_id": self.agent_id,
            "org_id": self.org_id,
            "name": self.name,
            "capabilities": sorted(self.capabilities),
            "roles": sorted(self.roles),
            "permissions": sorted(self.permissions),
            "created_at": self.created_at
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def verify_fingerprint(self) -> bool:
        return self.fingerprint == self._compute_fingerprint()

    def has_role(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles

    def has_permission(self, permission: str) -> bool:
        if "admin:*" in self.permissions or "admin" in self.roles:
            return True
        return permission in self.permissions

    def to_dict(self) -> dict:
        d = {
            "agent_id": self.agent_id,
            "org_id": self.org_id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "capabilities": self.capabilities,
            "roles": self.roles,
            "permissions": self.permissions,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "fingerprint": self.fingerprint
        }
        if self.public_key:
            d["public_key"] = self.public_key
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AgentIdentity":
        identity = cls(
            name=data["name"],
            org_id=data.get("org_id", "default"),
            capabilities=data.get("capabilities", []),
            roles=data.get("roles", ["standard"]),
            permissions=data.get("permissions", []),
            agent_id=data.get("agent_id"),
            created_at=data.get("created_at"),
            metadata=data.get("metadata", {}),
            public_key=data.get("public_key")
        )
        if "fingerprint" in data:
            identity.fingerprint = data["fingerprint"]
        return identity
