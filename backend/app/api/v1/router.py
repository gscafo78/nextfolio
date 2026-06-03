from fastapi import APIRouter

from app.api.v1.endpoints import auth, assets, accounts, transactions, fx, prices, portfolio, admin, user_settings, tax, alerts, import_ghostfolio, import_nextfolio, export, watchlist, rebalance, bonds

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(assets.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(fx.router)
api_router.include_router(prices.router)
api_router.include_router(portfolio.router)
api_router.include_router(export.router)
api_router.include_router(admin.router)
api_router.include_router(user_settings.router)
api_router.include_router(tax.router)
api_router.include_router(alerts.router)
api_router.include_router(import_ghostfolio.router)
api_router.include_router(import_nextfolio.router)
api_router.include_router(watchlist.router)
api_router.include_router(rebalance.router)
api_router.include_router(bonds.router)
