import hashlib
import json
import os
import platform
import uuid


def get_machine_fingerprint() -> str:
    """
    Génère une empreinte matérielle SHA-256 unique et déterministe basée sur le PC hôte.
    Combine : Adresse MAC, Processeur, Architecture, Nom d'hôte, Système d'exploitation.
    """
    try:
        mac_addr = hex(uuid.getnode())
    except Exception:
        mac_addr = "unknown_mac"

    hardware_info = {
        "mac": mac_addr,
        "system": platform.system(),
        "node": platform.node(),
        "machine": platform.machine(),
        "processor": platform.processor() or "generic_cpu",
    }

    raw = json.dumps(hardware_info, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_machine_fingerprint(expected_fingerprint: str) -> bool:
    """Vérifie si l'empreinte de la machine actuelle correspond à l'empreinte attendue."""
    return get_machine_fingerprint() == expected_fingerprint
