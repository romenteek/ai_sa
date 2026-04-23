from dataclasses import dataclass, field
from queue import Queue
from typing import Any


@dataclass
class Job:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


class InMemoryQueue:
    def __init__(self) -> None:
        self._queue: Queue[Job] = Queue()

    def push(self, job: Job) -> None:
        self._queue.put(job)

    def pop(self) -> Job:
        return self._queue.get_nowait()
