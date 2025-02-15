import threading
import time
import logging
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Démarre un serveur web en arrière-plan pour garder le bot actif"""
    t = Thread(target=run)
    t.daemon = True  # Le thread s'arrêtera quand le programme principal s'arrête
    t.start()
    logger.info("Serveur keep-alive démarré sur le port 8080")

def ping_bot():
    """Ping périodique pour maintenir le bot actif"""
    retry_count = 0
    max_retries = 5
    while True:
        try:
            response = requests.get('http://127.0.0.1:8080')
            if response.status_code == 200:
                logger.info("Keep-alive ping successful")
                retry_count = 0  # Réinitialiser le compteur après un succès
            else:
                logger.warning(f"Keep-alive ping returned status: {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            retry_count += 1
            logger.warning(f"Keep-alive ping failed (attempt {retry_count}/{max_retries}): {e}")
            if retry_count >= max_retries:
                logger.error("Maximum retry attempts reached for keep-alive ping")
                retry_count = 0  # Réinitialiser pour la prochaine série
        except Exception as e:
            logger.error(f"Erreur inattendue lors du ping keep-alive: {e}")
        finally:
            time.sleep(180)  # Ping toutes les 3 minutes

def start_keep_alive():
    """Initialise le système keep-alive"""
    keep_alive()
    ping_thread = threading.Thread(target=ping_bot)
    ping_thread.daemon = True
    ping_thread.start()
    logger.info("Système keep-alive initialisé avec succès")