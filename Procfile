# Procfile — defines process types for PaaS deployment (Render, Railway, Heroku)
#
# "web" = the main API server
# "worker" = the Celery background worker
# "release" = runs once on each deploy (database migrations)

web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.workers.celery_app worker --loglevel=info -Q default,high_priority,dead_letter --concurrency=2
release: alembic upgrade head
