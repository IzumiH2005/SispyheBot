import asyncio
import logging
import os
import sys
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from telegram.error import TelegramError, NetworkError, TimedOut
from config import TELEGRAM_TOKEN
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
from keep_alive import start_keep_alive

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

async def check_existing_instance():
    """Vérifie si une autre instance du bot est en cours d'exécution"""
    pid_file = "/tmp/telegram_bot.pid"

    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, 0)
                if old_pid != os.getpid():
                    logger.error(f"Une instance du bot est déjà en cours d'exécution (PID: {old_pid})")
                    return True
            except OSError:
                logger.info("Ancien processus terminé, suppression du fichier PID")
                os.remove(pid_file)
        except (ValueError, IOError) as e:
            logger.error(f"Erreur lors de la lecture du fichier PID: {e}")
            os.remove(pid_file)

    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID {os.getpid()} écrit dans {pid_file}")
    except IOError as e:
        logger.error(f"Impossible d'écrire le fichier PID: {e}")
        return True

    return False

async def handle_network_error(update: Update, context, error: Exception):
    """Gère les erreurs réseau de manière appropriée"""
    if isinstance(error, (NetworkError, TimedOut)):
        logger.warning(f"Erreur réseau temporaire: {error}")
        await asyncio.sleep(1)  # Attente courte avant de réessayer
        return True
    return False

async def main():
    """Fonction principale du bot avec meilleure gestion des erreurs"""
    restart_attempts = 0
    max_restart_attempts = 3

    while restart_attempts < max_restart_attempts:
        try:
            if not TELEGRAM_TOKEN:
                logger.error("Token Telegram manquant")
                return

            if await check_existing_instance():
                return

            # Démarrage du keep-alive
            start_keep_alive()
            logger.info("Service keep-alive démarré")

            # Configuration de l'application avec des timeouts plus longs
            application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
            setup_handlers(application)

            logger.info("Démarrage du bot...")
            await application.initialize()
            await application.start()

            # Configuration du polling avec des paramètres optimisés
            await application.updater.start_polling(
                bootstrap_retries=-1,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
                read_timeout=60,  # Augmenté à 60 secondes
                write_timeout=60,  # Augmenté à 60 secondes
                pool_timeout=60,   # Nouveau timeout pour le pool
                connect_timeout=60  # Nouveau timeout pour la connexion
            )

            # Boucle principale avec gestion des erreurs améliorée
            while True:
                try:
                    await asyncio.sleep(1)
                except Exception as e:
                    if not await handle_network_error(None, None, e):
                        raise

        except TelegramError as e:
            logger.error(f"Erreur Telegram: {e}")
            restart_attempts += 1
            if restart_attempts < max_restart_attempts:
                logger.info(f"Tentative de redémarrage {restart_attempts}/{max_restart_attempts}")
                await asyncio.sleep(5)  # Attente avant redémarrage
                continue
            break

        except Exception as e:
            logger.error(f"Erreur critique: {e}")
            logger.exception("Détails de l'erreur:")
            restart_attempts += 1
            if restart_attempts < max_restart_attempts:
                logger.info(f"Tentative de redémarrage {restart_attempts}/{max_restart_attempts}")
                await asyncio.sleep(5)
                continue
            break

        finally:
            if 'application' in locals():
                try:
                    await application.stop()
                    await application.shutdown()
                except Exception as e:
                    logger.error(f"Erreur lors de l'arrêt de l'application: {e}")

            pid_file = "/tmp/telegram_bot.pid"
            if os.path.exists(pid_file):
                try:
                    with open(pid_file, 'r') as f:
                        pid = int(f.read().strip())
                    if pid == os.getpid():
                        os.remove(pid_file)
                        logger.info(f"Fichier PID {pid_file} supprimé")
                except (ValueError, IOError) as e:
                    logger.error(f"Erreur lors de la suppression du fichier PID: {e}")

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Arrêt du bot par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur au niveau principal: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        try:
            loop.close()
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la boucle: {e}")