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
KEEP_ALIVE_INTERVAL = int(os.environ.get("KEEP_ALIVE_INTERVAL", "30"))
MAX_RECONNECT_ATTEMPTS = int(os.environ.get("MAX_RECONNECT_ATTEMPTS", "10"))
RECONNECT_DELAY = int(os.environ.get("RECONNECT_DELAY", "10"))
PID_FILE = "/tmp/telegram_bot.pid"  # Définition constante du fichier PID

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

# Configuration du logging améliorée
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def cleanup_pid_file():
    """Nettoie le fichier PID si il existe"""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            logger.info(f"Fichier PID {PID_FILE} supprimé avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du fichier PID: {e}")

def write_pid_file():
    """Écrit le PID dans le fichier avec gestion d'erreurs"""
    try:
        with open(PID_FILE, 'w') as f:
            current_pid = os.getpid()
            f.write(str(current_pid))
            logger.info(f"PID {current_pid} écrit dans {PID_FILE}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'écriture du PID: {e}")
        return False

def check_existing_process():
    """Vérifie si une instance du bot est déjà en cours d'exécution"""
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, 0)
                logger.error(f"Instance du bot déjà en cours d'exécution (PID: {old_pid})")
                return True
            except OSError:
                logger.info(f"Ancien processus (PID: {old_pid}) terminé, suppression du fichier PID")
                cleanup_pid_file()
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du processus existant: {e}")
        return False

async def keep_alive():
    """Fonction de keep-alive améliorée avec gestion des erreurs"""
    global last_activity
    logger.info("Démarrage de la tâche keep-alive")
    while True:
        try:
            current_time = datetime.now()
            time_diff = (current_time - last_activity).total_seconds()

            if time_diff > KEEP_ALIVE_INTERVAL:
                logger.info(f"Keep-alive actif - Dernière activité il y a {time_diff:.1f} secondes")
                last_activity = current_time

                # Vérification du fichier PID
                if not os.path.exists(PID_FILE):
                    logger.warning("Fichier PID non trouvé, réécriture...")
                    write_pid_file()

            await asyncio.sleep(KEEP_ALIVE_INTERVAL)
        except Exception as e:
            logger.error(f"Erreur dans le keep-alive: {e}")
            await asyncio.sleep(5)

async def start_polling(application):
    """Démarre le polling avec gestion des reconnexions"""
    attempt = 0
    while attempt < MAX_RECONNECT_ATTEMPTS:
        try:
            logger.info(f"Tentative de connexion {attempt + 1}/{MAX_RECONNECT_ATTEMPTS}")
            await application.updater.start_polling(
                bootstrap_retries=-1,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
                read_timeout=60,
                write_timeout=60,
                pool_timeout=60
            )
            logger.info("Polling démarré avec succès")
            return True
        except NetworkError as e:
            attempt += 1
            logger.error(f"Erreur réseau (tentative {attempt}/{MAX_RECONNECT_ATTEMPTS}): {e}")
            if attempt < MAX_RECONNECT_ATTEMPTS:
                logger.info(f"Nouvelle tentative dans {RECONNECT_DELAY} secondes...")
            await asyncio.sleep(RECONNECT_DELAY)
        except Exception as e:
            logger.error(f"Erreur inattendue lors du polling: {e}")
            raise
    logger.error("Nombre maximum de tentatives de reconnexion atteint")
    return False

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


async def main():
    """Fonction principale du bot avec gestion améliorée des erreurs"""
    application = None
    keep_alive_task = None

    try:
        # Vérification du token
        if not TELEGRAM_TOKEN:
            logger.error("Token Telegram manquant")
            return

        # Nettoyage initial du fichier PID
        cleanup_pid_file()

        # Vérification du processus existant
        if check_existing_process():
            return

        # Écriture du nouveau PID
        if not write_pid_file():
            logger.error("Impossible d'écrire le fichier PID")
            return

        # Configuration et démarrage de l'application
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        setup_handlers(application)

        logger.info("Initialisation du bot...")
        await application.initialize()
        await application.start()

        # Démarrage du keep-alive
        keep_alive_task = asyncio.create_task(keep_alive())
        logger.info("Tâche keep-alive démarrée")

        # Démarrage du polling
        if not await start_polling(application):
            logger.error("Impossible de démarrer le polling")
            return

        logger.info("Bot démarré avec succès")

        # Boucle principale
        while True:
            try:
                await asyncio.sleep(1)
                last_activity = datetime.now()
            except asyncio.CancelledError:
                logger.info("Arrêt demandé du bot")
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle principale: {e}")
                if isinstance(e, NetworkError):
                    if not await start_polling(application):
                        break
                else:
                    break

    except Exception as e:
        logger.error(f"Erreur critique dans main(): {e}")
        logger.exception("Détails de l'erreur:")

    finally:
        # Nettoyage
        if keep_alive_task:
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

        cleanup_pid_file()

if __name__ == '__main__':
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Arrêt du bot par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur au niveau principal: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        if 'loop' in locals() and not loop.is_closed():
            loop.close()
        cleanup_pid_file()