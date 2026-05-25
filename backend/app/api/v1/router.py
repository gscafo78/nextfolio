from fastapi import APIRouter

from app.api.v1.endpoints import auth, assets, accounts, transactions, fx, prices, portfolio, admin, user_settings, tax, alerts, import_ghostfolio

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(assets.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(fx.router)
api_router.include_router(prices.router)
api_router.include_router(portfolio.router)
api_router.include_router(admin.router)
api_router.include_router(user_settings.router)
api_router.include_router(tax.router)
api_router.include_router(alerts.router)
api_router.include_router(import_ghostfolio.router)
