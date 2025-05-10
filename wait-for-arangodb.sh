#!/bin/bash
# wait-for-arangodb.sh

set -e

host="$1"
shift
user="root"
password="rootpassword"

echo "Waiting for ArangoDB at $host..."
echo "Using credentials: $user:$password"

# Try with credentials explicitly (no environment variables)
until curl --silent --fail -u "$user:$password" "$host/_api/version"; do
  echo "ArangoDB is unavailable - sleeping"
  sleep 2
done

echo "ArangoDB is up - executing command"
exec "$@"
