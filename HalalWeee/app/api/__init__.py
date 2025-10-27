from __future__ import annotations

from fastapi import FastAPI

from . import certifications, outbox, orders, products, suppliers, warehouses


def register_routers(app: FastAPI) -> None:
    app.include_router(certifications.router)
    app.include_router(products.products_router)
    app.include_router(products.inventory_router)
    app.include_router(products.pricing_router)
    app.include_router(suppliers.router)
    app.include_router(warehouses.router)
    app.include_router(orders.router)
    app.include_router(outbox.router)

