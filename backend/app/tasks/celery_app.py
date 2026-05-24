from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "nextfolio",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.prices"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Rome",
    enable_utc=True,
    task_track_started=True,
)

celery_app.conf.beat_schedule = {
    # Azioni/ETF: ogni 15 min lunedì-venerdì 9:00-17:45 (orario Borsa Italiana)
    "update-stock-prices-realtime": {
        "task": "app.tasks.prices.update_stock_prices",
        "schedule": crontab(minute="*/15", hour="9-17", day_of_week="mon-fri"),
    },
    # Crypto: ogni 5 minuti, sempre (mercato 24/7)
    "update-crypto-prices": {
        "task": "app.tasks.prices.update_crypto_prices",
        "schedule": crontab(minute="*/5"),
    },
    # Prezzi di chiusura EOD: ogni giorno alle 18:30
    "update-prices-eod": {
        "task": "app.tasks.prices.update_prices_eod",
        "schedule": crontab(hour=18, minute=30, day_of_week="mon-fri"),
    },
    # Pulizia storico > 5 anni: ogni domenica a mezzanotte
    "cleanup-old-prices": {
        "task": "app.tasks.prices.cleanup_old_prices",
        "schedule": crontab(hour=0, minute=0, day_of_week="sun"),
    },
}
