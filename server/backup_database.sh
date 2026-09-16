#!/bin/sh
set -eu

backup_dir="${1:-./backups}"
mkdir -p "$backup_dir"
timestamp="$(date -u +%Y-%m-%d_%H%M%S)"
output="$backup_dir/printorders_$timestamp.sql.gz"

docker compose exec -T database pg_dump -U printorders -d printorders | gzip > "$output"
echo "Backup created: $output"

