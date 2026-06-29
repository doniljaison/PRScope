# Day 3-4 Report

## What we did:
- **Database Models**: Created SQLAlchemy ORM models for `Repository`, `PullRequest`, `AnalysisJob`, and `ReviewComment`.
- **Database Schema**: Set up Pydantic schemas for the models.
- **Alembic Migrations**: Added the new models to `alembic/env.py` and ran our first database migration.
- **Testing**: Added Pytest unit tests for all models and verified relationships (e.g., User -> Repository -> PullRequest -> AnalysisJob -> ReviewComment).
- **Seed Script**: Created a `seed.py` script to generate mock data for local development.

The core database is now fully modeled and ready to store PRs!
