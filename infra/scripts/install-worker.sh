#!/bin/bash
set -euo pipefail

install_root=/opt/finance-platform
release_dir="$${install_root}/current"
artifact=/tmp/finance-platform-worker.zip

dnf install -y python3.12 python3.12-pip unzip
mkdir -p "$${release_dir}"
aws s3 cp "s3://${artifact_bucket}/${artifact_key}" "$${artifact}"
rm -rf "$${release_dir:?}"/*
unzip -q "$${artifact}" -d "$${release_dir}"
python3.12 -m venv "$${install_root}/venv"
"$${install_root}/venv/bin/python" -m pip install --upgrade pip
"$${install_root}/venv/bin/pip" install "$${release_dir}"

cat >/etc/systemd/system/finance-sofi-hourly.service <<'EOF'
[Unit]
Description=FinanceFriday hourly SOFI one-minute bar ingestion
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/finance-platform/current
Environment=AWS_REGION=${aws_region}
Environment=AWS_DEFAULT_REGION=${aws_region}
Environment=RDS_SECRET_ARN=${rds_secret_arn}
Environment=ALPACA_SECRET_ARN=${alpaca_secret_arn}
Environment=RDS_ENDPOINT=${rds_endpoint}
Environment=RDS_PORT=5432
Environment=DB_NAME=${db_name}
ExecStart=/opt/finance-platform/venv/bin/python /opt/finance-platform/current/scripts/run_hourly.py
TimeoutStartSec=45min

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/finance-sofi-hourly.timer <<'EOF'
[Unit]
Description=Run FinanceFriday SOFI ingestion every hour

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=2min
Unit=finance-sofi-hourly.service

[Install]
WantedBy=timers.target
EOF

cat >/etc/systemd/system/finance-sofi-news-hourly.service <<'EOF'
[Unit]
Description=FinanceFriday hourly SOFI news ingestion
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/finance-platform/current
Environment=AWS_REGION=${aws_region}
Environment=AWS_DEFAULT_REGION=${aws_region}
Environment=RDS_SECRET_ARN=${rds_secret_arn}
Environment=RDS_ENDPOINT=${rds_endpoint}
Environment=RDS_PORT=5432
Environment=DB_NAME=${db_name}
Environment=RAW_BUCKET_NAME=${artifact_bucket}
Environment="SEC_USER_AGENT=FinanceFriday/0.1 finance-data@example.com"
ExecStart=/opt/finance-platform/venv/bin/python /opt/finance-platform/current/scripts/run_news_hourly.py
TimeoutStartSec=30min

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/finance-sofi-news-hourly.timer <<'EOF'
[Unit]
Description=Run FinanceFriday SOFI news ingestion hourly

[Timer]
OnCalendar=*-*-* *:10:00
Persistent=true
Unit=finance-sofi-news-hourly.service

[Install]
WantedBy=timers.target
EOF

cat >/etc/systemd/system/finance-sofi-insiders.service <<'EOF'
[Unit]
Description=FinanceFriday SOFI SEC insider transaction ingestion
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/finance-platform/current
Environment=AWS_REGION=${aws_region}
Environment=AWS_DEFAULT_REGION=${aws_region}
Environment=RDS_SECRET_ARN=${rds_secret_arn}
Environment=RDS_ENDPOINT=${rds_endpoint}
Environment=RDS_PORT=5432
Environment=DB_NAME=${db_name}
Environment=RAW_BUCKET_NAME=${artifact_bucket}
Environment="SEC_USER_AGENT=FinanceFriday/0.1 finance-data@example.com"
ExecStart=/opt/finance-platform/venv/bin/python /opt/finance-platform/current/scripts/run_insiders.py
TimeoutStartSec=30min

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/finance-sofi-insiders.timer <<'EOF'
[Unit]
Description=Poll SEC SOFI Forms 3, 4, and 5 every 15 minutes

[Timer]
OnCalendar=*:0/15
Persistent=true
Unit=finance-sofi-insiders.service

[Install]
WantedBy=timers.target
EOF

cat >/etc/systemd/system/finance-sofi-congress.service <<'EOF'
[Unit]
Description=FinanceFriday SOFI congressional transaction ingestion
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/finance-platform/current
Environment=AWS_REGION=${aws_region}
Environment=AWS_DEFAULT_REGION=${aws_region}
Environment=RDS_SECRET_ARN=${rds_secret_arn}
Environment=RDS_ENDPOINT=${rds_endpoint}
Environment=RDS_PORT=5432
Environment=DB_NAME=${db_name}
Environment=RAW_BUCKET_NAME=${artifact_bucket}
ExecStart=/opt/finance-platform/venv/bin/python /opt/finance-platform/current/scripts/run_congress.py
TimeoutStartSec=2h

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/finance-sofi-congress.timer <<'EOF'
[Unit]
Description=Poll official House and Senate SOFI disclosures daily

[Timer]
OnCalendar=*-*-* 06:30:00 UTC
Persistent=true
RandomizedDelaySec=15min
Unit=finance-sofi-congress.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now finance-sofi-hourly.timer
systemctl enable --now finance-sofi-news-hourly.timer
systemctl enable --now finance-sofi-insiders.timer
systemctl enable --now finance-sofi-congress.timer
systemctl start finance-sofi-hourly.service

cat >/etc/systemd/system/finance-sofi-analyst-ratings.service <<'EOF'
[Unit]
Description=FinanceFriday daily SOFI analyst-rating ingestion
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/finance-platform/current
Environment=AWS_REGION=${aws_region}
Environment=AWS_DEFAULT_REGION=${aws_region}
Environment=RDS_SECRET_ARN=${rds_secret_arn}
Environment=FMP_SECRET_ARN=${fmp_secret_arn}
Environment=RDS_ENDPOINT=${rds_endpoint}
Environment=RDS_PORT=5432
Environment=DB_NAME=${db_name}
Environment=RAW_BUCKET_NAME=${artifact_bucket}
ExecStart=/opt/finance-platform/venv/bin/python /opt/finance-platform/current/scripts/run_analyst_ratings.py
TimeoutStartSec=30min

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/finance-sofi-analyst-ratings.timer <<'EOF'
[Unit]
Description=Poll FMP SOFI analyst ratings daily

[Timer]
OnCalendar=*-*-* 07:00:00 UTC
Persistent=true
RandomizedDelaySec=20min
Unit=finance-sofi-analyst-ratings.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now finance-sofi-analyst-ratings.timer
