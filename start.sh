#!/bin/bash
set -e

echo "-----> Checking Chromium installation"

# Vérifier si Chromium est installé
if [ ! -d "$HOME/.cache/ms-playwright/chromium-1091" ]; then
    echo "-----> Installing Playwright Chromium"
    python -m playwright install chromium
    echo "-----> Chromium installed successfully"
else
    echo "-----> Chromium already installed"
fi

# Démarrer l'application
echo "-----> Starting application"
exec gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --worker-class sync --workers 2 --threads 1 --preload
