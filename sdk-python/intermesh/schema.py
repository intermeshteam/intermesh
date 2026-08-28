"""
InterMesh Schema Ontology — traduction de payloads entre conventions de nommage.

Ce n'est PAS un modèle de traduction sémantique par IA : c'est une table de
correspondance déterministe entre schémas nommés (`SchemaRegistry`) complétée
par un dictionnaire de synonymes pour les cas non ambigus. Un agent qui
attend `{"prompt": ...}` peut ainsi recevoir un payload écrit `{"user_query":
...}` sans que l'appelant connaisse le format exact de l'autre — mais la
correspondance explicite (schéma déclaré des deux côtés) est toujours
préférée à l'heuristique par synonymes, qui ne s'applique que lorsqu'un champ
n'appartient sans ambiguïté qu'à un seul concept.
"""

from __future__ import annotations

from typing import Dict, Optional, Set


class SchemaError(Exception):
    """Schéma inconnu ou traduction impossible."""


# Concept canonique -> noms de champs connus dans l'écosystème pour ce concept.
# Un nom de champ absent de tous ces ensembles, ou présent dans plusieurs,
# n'est jamais traduit par heuristique : seule une correspondance de schéma
# explicite peut le résoudre (voir `SchemaRegistry.register`).
SYNONYMS: Dict[str, Set[str]] = {
    "input_text": {"prompt", "user_query", "query", "input", "message", "question"},
    "output_text": {"response", "completion", "output", "result", "answer", "reply"},
    "system_prompt": {"system", "system_prompt", "instructions", "system_message"},
    "history": {"messages", "history", "conversation", "chat_history"},
    "temperature": {"temperature", "temp"},
    "max_tokens": {"max_tokens", "max_length", "max_new_tokens"},
}


def _concept_for_field(field: str) -> Optional[str]:
    """Concept canonique pour un nom de champ, seulement s'il est non ambigu."""
    matches = [concept for concept, names in SYNONYMS.items() if field in names]
    return matches[0] if len(matches) == 1 else None


class SchemaDefinition:
    """
    Un schéma nommé : correspondance explicite champ-local -> concept canonique.

    `{"user_query": "input_text", "answer": "output_text"}` déclare que ce
    format appelle `input_text` "user_query", et `output_text` "answer".
    """

    def __init__(self, name: str, fields: Dict[str, str]):
        self.name = name
        self.fields = dict(fields)
        self._concept_to_field = {concept: field for field, concept in fields.items()}

    def field_for_concept(self, concept: str) -> Optional[str]:
        return self._concept_to_field.get(concept)

    def concept_for_field(self, field: str) -> Optional[str]:
        return self.fields.get(field)


class SchemaRegistry:
    """Registre de schémas nommés, utilisé pour traduire un payload de l'un vers l'autre."""

    def __init__(self):
        self._schemas: Dict[str, SchemaDefinition] = {}

    def register(self, name: str, fields: Dict[str, str]) -> SchemaDefinition:
        definition = SchemaDefinition(name, fields)
        self._schemas[name] = definition
        return definition

    def get(self, name: str) -> Optional[SchemaDefinition]:
        return self._schemas.get(name)

    def to_canonical(self, payload: dict, source_schema: Optional[str] = None) -> dict:
        """
        Forme canonique d'un payload : chaque clé remplacée par son concept
        quand il est connu (via le schéma source déclaré, sinon par synonyme
        non ambigu). Les clés non résolues sont conservées telles quelles.
        """
        source = self._schemas.get(source_schema) if source_schema else None
        canonical: dict = {}
        for field, value in (payload or {}).items():
            concept = source.concept_for_field(field) if source else None
            if concept is None:
                concept = _concept_for_field(field)
            canonical[concept or field] = value
        return canonical

    def from_canonical(self, canonical: dict, target_schema: str) -> dict:
        target = self._schemas.get(target_schema)
        if target is None:
            raise SchemaError(f"Schéma inconnu : '{target_schema}'.")

        out: dict = {}
        for concept, value in canonical.items():
            field = target.field_for_concept(concept)
            out[field or concept] = value
        return out

    def translate(self, payload: dict, target_schema: str, source_schema: Optional[str] = None) -> dict:
        """Traduit un payload d'un schéma (ou de champs bruts) vers un schéma cible nommé."""
        canonical = self.to_canonical(payload, source_schema)
        return self.from_canonical(canonical, target_schema)


# Registre par défaut, partagé, avec quelques schémas de référence déjà
# déclarés — un agent peut toujours en enregistrer/écraser un via
# `default_registry().register(...)`.
_default_registry = SchemaRegistry()
_default_registry.register("generic", {"input": "input_text", "output": "output_text"})
_default_registry.register("openai_style", {"prompt": "input_text", "completion": "output_text"})
_default_registry.register("claude_style", {"prompt": "input_text", "response": "output_text"})
_default_registry.register("llama_style", {"user_query": "input_text", "answer": "output_text"})


def default_registry() -> SchemaRegistry:
    return _default_registry


def translate_payload(payload: dict, target_schema: str, source_schema: Optional[str] = None,
                      registry: Optional[SchemaRegistry] = None) -> dict:
    return (registry or _default_registry).translate(payload, target_schema, source_schema)
