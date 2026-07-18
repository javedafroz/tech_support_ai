#!/bin/sh
set -e
cd /app/apps/api
alembic upgrade head
exec tech-support-api
