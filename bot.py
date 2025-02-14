import asyncio
import logging
import os
import sys
from datetime import datetime

# Regroupement des imports telegram
try:
    from telegram import Update
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        filters
    )
    from telegram.error import NetworkError, TelegramError
except ImportError as e:
    logging.error(f"Erreur d'importation des modules telegram: {e}")
    sys.exit(1)

from config import TELEGRAM_TOKEN

# Configuration des intervalles via les variables d'environnement
KEEP_ALIVE_INTERVAL = int(os.environ.get("KEEP_ALIVE_INTERVAL", "60"))  # Intervalle par défaut: 60 secondes
MAX_RECONNECT_ATTEMPTS = int(os.environ.get("MAX_RECONNECT_ATTEMPTS", "5"))
RECONNECT_DELAY = int(os.environ.get("RECONNECT_DELAY", "5"))  # Délai par défaut: 5 secondes

# Variables globales pour le monitoring
last_activity = datetime.now()

from handlers import (
    start_command,
    help_command,
    menu_command,
    search_command,
    yt_command,
    fiche_command,
    ebook_command,
    handle_message,
    handle_callback
)

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def setup_handlers(application):
    """Configure les handlers de l'application"""
    handlers = [
        ('start', start_command),
        ('help', help_command),
        ('menu', menu_command),
        ('search', search_command),
        ('yt', yt_command),
        ('fiche', fiche_command),
        ('ebook', ebook_command)
    ]

    for command, handler in handlers:
        application.add_handler(CommandHandler(command, handler))
        logger.info(f"Handler ajouté pour la commande /{command}")

    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

async def keep_alive():
    """Fonction de keep-alive qui maintient le bot actif"""
    global last_activity
    while True:
        try:
            current_time = datetime.now()
            time_diff = (current_time - last_activity).total_seconds()

            if time_diff > KEEP_ALIVE_INTERVAL:
                logger.info("Exécution du keep-alive...")
                last_activity = current_time

            await asyncio.sleep(KEEP_ALIVE_INTERVAL)
        except Exception as e:
            logger.error(f"Erreur dans le keep-alive: {e}")
            await asyncio.sleep(5)

async def start_polling(application):
    """Démarre le polling avec gestion des reconnexions"""
    attempt = 0
    while attempt < MAX_RECONNECT_ATTEMPTS:
        try:
            await application.updater.start_polling(
                bootstrap_retries=-1,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
                read_timeout=60,  # Augmentation des timeouts
                write_timeout=60,
                pool_timeout=60
            )
            logger.info("Polling démarré avec succès")
            return True
        except NetworkError as e:
            attempt += 1
            logger.error(f"Erreur réseau (tentative {attempt}/{MAX_RECONNECT_ATTEMPTS}): {e}")
            await asyncio.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.error(f"Erreur inattendue lors du polling: {e}")
            raise

    logger.error("Nombre maximum de tentatives de reconnexion atteint")
    return False

async def main():
    """Fonction principale du bot"""
    pid_file = "/tmp/telegram_bot.pid"
    application = None
    keep_alive_task = None
    loop = asyncio.get_running_loop()  # Initialisation explicite de la boucle

    try:
        # Vérification du token
        if not TELEGRAM_TOKEN:
            logger.error("Token Telegram manquant")
            return

        # Vérification du PID
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                old_pid = int(f.read())
            try:
                os.kill(old_pid, 0)
                logger.error("Une instance du bot est déjà en cours d'exécution")
                return
            except OSError:
                logger.info("Ancien processus terminé")

        # Écriture du PID
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
            logger.info(f"PID {os.getpid()} écrit dans {pid_file}")

        # Configuration de l'application
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        setup_handlers(application)

        logger.info("Démarrage du bot...")
        await application.initialize()
        await application.start()

        # Démarrer le keep-alive dans une tâche séparée
        keep_alive_task = asyncio.create_task(keep_alive())

        # Démarrer le polling avec gestion des reconnexions
        if not await start_polling(application):
            logger.error("Impossible de démarrer le polling")
            return

        # Attendre indéfiniment avec gestion des erreurs
        while True:
            try:
                await asyncio.sleep(1)
                last_activity = datetime.now()
            except asyncio.CancelledError:
                logger.info("Arrêt demandé du bot")
                break
            except Exception as e:
                logger.error(f"Erreur pendant l'exécution: {e}")
                if isinstance(e, NetworkError):
                    # Tentative de redémarrage du polling en cas d'erreur réseau
                    if not await start_polling(application):
                        break
                else:
                    break

    except TelegramError as e:
        logger.error(f"Erreur Telegram: {e}")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        # Nettoyage
        if keep_alive_task is not None:
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass

        if application:
            try:
                await application.stop()
                await application.shutdown()
            except Exception as e:
                logger.error(f"Erreur lors de l'arrêt de l'application: {e}")

        if os.path.exists(pid_file):
            os.remove(pid_file)
            logger.info(f"Fichier PID {pid_file} supprimé")

if __name__ == '__main__':
    try:
        # Obtenir la boucle d'événements existante ou en créer une nouvelle
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Exécuter la fonction principale
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Arrêt du bot par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur au niveau principal: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        # Fermeture propre de la boucle
        if 'loop' in locals() and not loop.is_closed():
            loop.close()