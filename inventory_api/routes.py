from aiohttp import web

from inventory_api import handlers


def setup_routes(app: web.Application) -> None:
    app.router.add_post("/receipts", handlers.create_receipt)
    app.router.add_post("/issues", handlers.create_issue)
    app.router.add_get("/stock", handlers.get_stock)
    app.router.add_get("/stock/summary", handlers.get_stock_summary)
