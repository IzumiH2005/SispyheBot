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

async def main():
    """Fonction principale du bot"""
    pid_file = "/tmp/telegram_bot.pid"
    application = None

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

        # Démarrage du polling avec des options de configuration explicites
        await application.updater.start_polling(
            bootstrap_retries=-1,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            read_timeout=30,
            write_timeout=30
        )

        # Attendre indéfiniment
        try:
            await application.updater.running
        except Exception as e:
            logger.error(f"Erreur pendant l'exécution: {e}")

    except TelegramError as e:
        logger.error(f"Erreur Telegram: {e}")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        # Nettoyage
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
        loop = asyncio.get_event_loop()
        if loop.is_closed():
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
        try:
            loop.close()
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la boucle: {e}")