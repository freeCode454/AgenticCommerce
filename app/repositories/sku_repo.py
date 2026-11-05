from .base import BaseRepository
from app.models.sku import Sku

class SkuRepository(BaseRepository[Sku]):
    def __init__(self, session):
        super().__init__(Sku, session)
