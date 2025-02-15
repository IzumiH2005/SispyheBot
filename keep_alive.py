import threading
import time
import logging
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)
logger = logging.getLogger(__name__)
is_bot_responding = True  # Flag global pour suivre l'état du bot

@app.route('/')
def home():
    global is_bot_responding
    return "Bot is alive!" if is_bot_responding else "Bot needs restart"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Démarre un serveur web en arrière-plan pour garder le bot actif"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    logger.info("Serveur keep-alive démarré sur le port 8080")

def ping_bot():
    """Ping périodique pour maintenir le bot actif avec meilleure gestion des erreurs"""
    global is_bot_responding
    consecutive_failures = 0
    max_consecutive_failures = 3

    while True:
        try:
            response = requests.get('http://127.0.0.1:8080', timeout=10)
            if response.status_code == 200:
                logger.info("Keep-alive ping successful")
                consecutive_failures = 0
                is_bot_responding = True
            else:
                consecutive_failures += 1
                logger.warning(f"Keep-alive ping returned status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            consecutive_failures += 1
            logger.warning(f"Keep-alive ping failed: {e}")

        if consecutive_failures >= max_consecutive_failures:
            is_bot_responding = False
            logger.error("Bot appears to be unresponsive, marking as needing restart")
            # Essayer de redémarrer le bot ici si possible
            try:
                # Envoyer un signal pour redémarrer le bot
                requests.post('http://127.0.0.1:5002/restart', timeout=5)
            except:
                logger.error("Failed to trigger bot restart")

        # Réduire l'intervalle de ping à 60 secondes
        time.sleep(60)

def start_keep_alive():
    """Initialise le système keep-alive avec surveillance améliorée"""
    keep_alive()
    ping_thread = threading.Thread(target=ping_bot)
    ping_thread.daemon = True
    ping_thread.start()
    logger.info("Système keep-alive initialisé avec surveillance améliorée")