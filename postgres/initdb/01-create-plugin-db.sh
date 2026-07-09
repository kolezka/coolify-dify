#!/bin/bash
# Create the plugin daemon's database (`dify_plugin`) if it does not exist.
#
# The Dify plugin daemon normally creates this database itself, but doing it
# here removes any dependency on that behavior / on CREATEDB timing. This script
# is run by the postgres image only on first initialization of an empty data
# directory, so it is a no-op on subsequent restarts.
set -e

PLUGIN_DB="${DB_PLUGIN_DATABASE:-dify_plugin}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	SELECT 'CREATE DATABASE "${PLUGIN_DB}"'
	WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${PLUGIN_DB}')\gexec
EOSQL

echo "[initdb] ensured database '${PLUGIN_DB}' exists"
