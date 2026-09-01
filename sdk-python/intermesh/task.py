import time
import uuid
from enum import Enum
from typing import Any, Optional


class TaskValidationError(ValueError):
    """Exception levee en cas de violation de schema ou de type sur une tache."""
    pass


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InterMeshTask:
    def __init__(
        self,
        title: str,
        orchestrator: str,
        assignee: str,
        input_data: Any,
        task_id: Optional[str] = None,
        status: TaskStatus = TaskStatus.PENDING,
        output_data: Any = None,
        error_message: Optional[str] = None,
        summary: Optional[str] = None,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.title = title
        self.orchestrator = orchestrator
        self.assignee = assignee
        self.input_data = input_data
        self.status = TaskStatus(status)
        self.output_data = output_data
        self.error_message = error_message
        # Résumé en clair de ce que l'agent a fait : contrairement à
        # input_data/output_data (chiffrés de bout en bout), ce champ est
        # lisible par le Hub et la console, pour la page de résumés.
        self.summary = summary
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()

    def update_status(self, status: TaskStatus, output_data: Any = None, error_message: Optional[str] = None, summary: Optional[str] = None):
        self.status = TaskStatus(status)
        self.output_data = output_data
        self.error_message = error_message
        if summary is not None:
            self.summary = summary
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "orchestrator": self.orchestrator,
            "assignee": self.assignee,
            "input_data": self.input_data,
            "status": self.status.value,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InterMeshTask":
        if not isinstance(data, dict):
            raise TaskValidationError("Le payload de la tache doit etre un dictionnaire JSON.")

        # Validation des champs obligatoires
        mandatory = ["title", "orchestrator", "assignee", "input_data"]
        for field in mandatory:
            if field not in data:
                raise TaskValidationError(f"Champ obligatoire absent dans la tache : '{field}'")

        # Validation de l'identifiant de la tache
        task_id = data.get("task_id")
        if task_id is not None and not isinstance(task_id, str):
            raise TaskValidationError("Le champ 'task_id' doit etre une chaine de caracteres.")

        # Validation du titre
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            raise TaskValidationError("Le champ 'title' doit etre une chaine de caracteres non vide.")

        # Validation de l'orchestrateur
        orchestrator = data["orchestrator"]
        if not isinstance(orchestrator, str) or not orchestrator.strip():
            raise TaskValidationError("Le champ 'orchestrator' doit etre une chaine de caracteres non vide.")

        # Validation de l'executant
        assignee = data["assignee"]
        if not isinstance(assignee, str) or not assignee.strip():
            raise TaskValidationError("Le champ 'assignee' doit etre une chaine de caracteres non vide.")

        # Validation du statut
        status_raw = data.get("status", "pending")
        try:
            status = TaskStatus(status_raw)
        except ValueError:
            raise TaskValidationError(f"Statut de tache invalide : '{status_raw}'")

        # Validation des timestamps
        created_at = data.get("created_at")
        if created_at is not None and not isinstance(created_at, (int, float)):
            raise TaskValidationError("Le champ 'created_at' doit etre un timestamp numerique.")

        updated_at = data.get("updated_at")
        if updated_at is not None and not isinstance(updated_at, (int, float)):
            raise TaskValidationError("Le champ 'updated_at' doit etre un timestamp numerique.")

        summary = data.get("summary")
        if summary is not None and not isinstance(summary, str):
            raise TaskValidationError("Le champ 'summary' doit etre une chaine de caracteres.")

        return cls(
            task_id=task_id,
            title=title,
            orchestrator=orchestrator,
            assignee=assignee,
            input_data=data["input_data"],
            status=status,
            output_data=data.get("output_data"),
            error_message=data.get("error_message"),
            summary=summary,
            created_at=created_at,
            updated_at=updated_at
        )
