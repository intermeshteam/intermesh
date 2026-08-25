import time
import uuid
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NexusTask:
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
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()

    def update_status(self, status: TaskStatus, output_data: Any = None, error_message: Optional[str] = None):
        self.status = TaskStatus(status)
        self.output_data = output_data
        self.error_message = error_message
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
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NexusTask":
        return cls(
            task_id=data.get("task_id"),
            title=data["title"],
            orchestrator=data["orchestrator"],
            assignee=data["assignee"],
            input_data=data["input_data"],
            status=TaskStatus(data.get("status", "pending")),
            output_data=data.get("output_data"),
            error_message=data.get("error_message"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )
