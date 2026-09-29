#!/usr/bin/env bash
#
# Convenience wrapper for the UFCEP6-0-3 hospital external workers.
#
#   ./run-workers.sh                 # build if needed, then run
#   REBUILD=1 ./run-workers.sh       # force a clean rebuild first
#   DEMO_PAYMENT_STATUS=DECLINED ./run-workers.sh
#   ./run-workers.sh --config=/path/to/application.yaml
#
# Every configuration key can be set as an environment variable; see DEPLOYMENT.md.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

JAR="target/hospital-external-workers-1.0.0.jar"

if [[ ! -f "$JAR" || "${REBUILD:-0}" == "1" ]]; then
  echo "==> building $JAR"
  mvn -q clean package
fi

if [[ -z "${CAMUNDA_CLIENT_ZEEBE_GATEWAY_ADDRESS:-}" && -z "${ZEEBE_GATEWAY_ADDRESS:-}" ]]; then
  echo "==> using the default gRPC gateway from application.yaml (localhost:26500)"
  echo "    set CAMUNDA_CLIENT_ZEEBE_GATEWAY_ADDRESS to point somewhere else"
fi

# JAVA_OPTS is intentionally unquoted so it can carry several flags.
# On JDK 22+ add --enable-native-access=ALL-UNNAMED to silence the netty/protobuf warnings:
#   JAVA_OPTS="--enable-native-access=ALL-UNNAMED" ./run-workers.sh
exec java ${JAVA_OPTS:-} -jar "$JAR" "$@"
