#!/bin/bash
echo "Starting Zero-Downtime Migration Demo..."
docker-compose up -d
sleep 15
python src/migration.py
