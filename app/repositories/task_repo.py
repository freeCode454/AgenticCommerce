from .base import BaseRepository
from app.models.task import Task

class TaskRepository(BaseRepository[Task]):
    def __init__(self, session):
        super().__init__(Task, session)
