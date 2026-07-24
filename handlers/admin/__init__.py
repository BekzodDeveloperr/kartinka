from .panel import router as panel_router
from .orders_management import router as orders_router
from .broadcast import router as broadcast_router
from .reports import router as reports_router
from .catalog import router as catalog_router
from .admins import router as admins_router
from .promos import router as promos_router
from .reviews import router as reviews_router

__all__ = [
    "panel_router",
    "orders_router",
    "broadcast_router",
    "reports_router",
    "catalog_router",
    "admins_router",
    "promos_router",
    "reviews_router",
]
