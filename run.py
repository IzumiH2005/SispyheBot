import os
import sys
import signal
import subprocess
import time
import logging
from multiprocessing import Process

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('run.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def run_health_check():
    """Lance le health check"""
    try:
        subprocess.run([sys.executable, "health_check.py"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors du lancement du health check: {e}")
    except KeyboardInterrupt:
        logger.info("Arrêt du health check")

def run_telegram_bot():
    """Lance le bot Telegram"""
    try:
        subprocess.run([sys.executable, "bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors du lancement du bot: {e}")
    except KeyboardInterrupt:
        logger.info("Arrêt du bot Telegram")

def signal_handler(signum, frame):
    """Gère l'arrêt propre des processus"""
    logger.info(f"Signal reçu: {signum}")
    sys.exit(0)

def main():
    """Fonction principale"""
    try:
        # Enregistrement du gestionnaire de signaux
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Démarrage des services...")

        # Lancement du health check en arrière-plan
        health_check_process = Process(target=run_health_check)
        health_check_process.start()
        logger.info("Health check démarré")

        # Attendre que le health check soit prêt
        time.sleep(2)

        # Lancement du bot Telegram
        bot_process = Process(target=run_telegram_bot)
        bot_process.start()
        logger.info("Bot Telegram démarré")

        # Attendre la fin des processus
        health_check_process.join()
        bot_process.join()

    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        # Nettoyage
        if 'health_check_process' in locals():
            health_check_process.terminate()
            health_check_process.join()
        if 'bot_process' in locals():
            bot_process.terminate()
            bot_process.join()
        logger.info("Services arrêtés")

if __name__ == "__main__":
    main()
