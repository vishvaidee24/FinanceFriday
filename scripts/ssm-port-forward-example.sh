#!/usr/bin/env bash
set -euo pipefail

INSTANCE_ID="${INSTANCE_ID:-i-xxxxxxxxxxxxxxxxx}"
RDS_HOST="${RDS_HOST:-your-db.xxxxxxxxx.us-east-1.rds.amazonaws.com}"

aws ssm start-session \
  --target "$INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"$RDS_HOST\"],\"portNumber\":[\"5432\"],\"localPortNumber\":[\"5433\"]}"
