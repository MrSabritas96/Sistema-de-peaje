#!/bin/sh
set -eu
umask 077
destination="${1:?indique una carpeta privada de respaldo}"
mkdir -p "$destination"
name=$(date -u +%Y%m%dT%H%M%SZ)
tmp=$(mktemp "$destination/db.XXXXXXXX")
trap 'rm -f "$tmp"' EXIT
docker compose exec -T db pg_dump -U peaje -d peaje -Fc > "$tmp"
docker compose exec -T db pg_restore --list < "$tmp" >/dev/null
mv "$tmp" "$destination/$name.dump"
docker compose exec -T api tar -cz - -C /data evidencias > "$destination/$name-evidencias.tar.gz"
