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
from telegram.error import TelegramError
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

async def check_existing_instance():
    """Vérifie si une autre instance du bot est en cours d'exécution"""
    pid_file = "/tmp/telegram_bot.pid"

    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, 0)  # Vérifie si le processus existe
                if old_pid != os.getpid():
                    logger.error(f"Une instance du bot est déjà en cours d'exécution (PID: {old_pid})")
                    return True
            except OSError:
                logger.info("Ancien processus terminé, suppression du fichier PID")
                os.remove(pid_file)
        except (ValueError, IOError) as e:
            logger.error(f"Erreur lors de la lecture du fichier PID: {e}")
            os.remove(pid_file)

    # Écriture du nouveau PID
    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID {os.getpid()} écrit dans {pid_file}")
    except IOError as e:
        logger.error(f"Impossible d'écrire le fichier PID: {e}")
        return True

    return False

async def main():
    """Fonction principale du bot"""
    try:
        # Vérification du token
        if not TELEGRAM_TOKEN:
            logger.error("Token Telegram manquant")
            return

        # Vérification des instances multiples
        if await check_existing_instance():
            return

        # Démarrage du keep-alive
        start_keep_alive()
        logger.info("Service keep-alive démarré")

        # Configuration de l'application
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        setup_handlers(application)

        logger.info("Démarrage du bot...")
        await application.initialize()
        await application.start()

        # Démarrage du polling avec des options de configuration explicites
        await application.updater.start_polling(
            bootstrap_retries=-1,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            read_timeout=30,
            write_timeout=30
        )

        try:
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Erreur pendant l'exécution: {e}")

    except TelegramError as e:
        logger.error(f"Erreur Telegram: {e}")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        # Nettoyage
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
                if pid == os.getpid():  # Ne supprimer que si c'est notre PID
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