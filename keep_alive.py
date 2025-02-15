import threading
import time
import logging
import requests
import json
import os
from flask import Flask, jsonify
from threading import Thread

app = Flask(__name__)
logger = logging.getLogger(__name__)
is_bot_responding = True

@app.route('/')
def home():
    """
    Endpoint principal optimisé pour Uptime Robot
    Renvoie un statut 200 avec des informations détaillées
    """
    status = {
        "status": "up",
        "timestamp": time.time(),
        "service": "Sisyphe Bot",
        "is_responding": is_bot_responding
    }
    return jsonify(status), 200

def run():
    """Démarre le serveur web avec les options optimisées"""
    app.run(
        host='0.0.0.0',
        port=8080,
        threaded=True,
        use_reloader=False  # Désactive le reloader pour éviter les doubles processus
    )

def keep_alive():
    """Démarre le serveur web en arrière-plan"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    logger.info("Serveur keep-alive démarré sur le port 8080")

def ping_bot():
    """Surveillance continue du bot sans timeout"""
    global is_bot_responding
    consecutive_failures = 0
    max_consecutive_failures = 3
    health_check_url = 'http://127.0.0.1:5002/health'

    while True:
        try:
            # Vérifie l'état du bot via l'API Telegram avec un timeout plus long
            response = requests.post(
                f'https://api.telegram.org/bot{os.getenv("TELEGRAM_TOKEN")}/getMe',
                timeout=30
            )

            # Vérifie aussi le health check
            try:
                health_response = requests.get(health_check_url, timeout=5)
                if health_response.status_code == 200:
                    logger.debug("Health check successful")
            except:
                logger.warning("Health check failed, but continuing")

            if response.status_code == 200:
                logger.debug("Bot status check successful")
                consecutive_failures = 0
                is_bot_responding = True
            else:
                consecutive_failures += 1
                logger.warning(f"Bot status check failed with status: {response.status_code}")
        except Exception as e:
            consecutive_failures += 1
            logger.warning(f"Bot status check failed: {str(e)}")

        if consecutive_failures >= max_consecutive_failures:
            is_bot_responding = False
            logger.error("Bot appears to be unresponsive")
            try:
                # Essaie de redémarrer le bot via le health check
                requests.post('http://127.0.0.1:5002/restart', timeout=5)
            except:
                logger.error("Failed to trigger bot restart")

        # Attend moins longtemps entre les vérifications
        time.sleep(15)  # Vérifie toutes les 15 secondes au lieu de 30

def start_keep_alive():
    """Initialise le système keep-alive complet"""
    keep_alive()
    ping_thread = threading.Thread(target=ping_bot)
    ping_thread.daemon = True
    ping_thread.start()
    logger.info("Système keep-alive initialisé avec surveillance continue")