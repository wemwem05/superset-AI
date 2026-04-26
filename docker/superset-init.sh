#!/bin/bash
set -e

echo "Running database migrations..."
superset db upgrade

echo "Creating admin user (if not exists)..."
superset fab create-admin \
  --username "$SUPERSET_ADMIN_USERNAME" \
  --firstname "$SUPERSET_ADMIN_FIRSTNAME" \
  --lastname "$SUPERSET_ADMIN_LASTNAME" \
  --email "$SUPERSET_ADMIN_EMAIL" \
  --password "$SUPERSET_ADMIN_PASSWORD" \
  || true

echo "Initializing Superset..."
superset init

if [ "$SUPERSET_LOAD_EXAMPLES" = "yes" ]; then
  echo "Loading example data..."
  superset load_examples
fi

echo "Initialization complete."
