import asyncio
import logging
import nest_asyncio
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    image_command,
    yt_command,
    fiche_command,
    handle_message,
    handle_callback
)

# Application de nest_asyncio pour gérer les boucles d'événements imbriquées
nest_asyncio.apply()

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def main():
    """Fonction principale du bot avec gestion améliorée des instances"""
    try:
        # Vérification qu'une seule instance tourne
        pid_file = "/tmp/telegram_bot.pid"

        try:
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    old_pid = int(f.read())
                try:
                    # Vérifier si le processus existe encore
                    os.kill(old_pid, 0)
                    logger.error("Une instance du bot est déjà en cours d'exécution")
                    sys.exit(1)
                except OSError:
                    # Le processus n'existe plus, on peut continuer
                    pass

            # Écrire notre PID
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du PID: {e}")
            sys.exit(1)

        # Création de l'application avec une meilleure gestion des timeouts
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Ajout des handlers avec logging amélioré
        handlers = [
            ('start', start_command),
            ('help', help_command),
            ('menu', menu_command),
            ('search', search_command),
            ('image', image_command),
            ('yt', yt_command),
            ('fiche', fiche_command)
        ]

        for command, handler in handlers:
            application.add_handler(CommandHandler(command, handler))
            logger.info(f"Handler ajouté pour la commande /{command}")

        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        ))

        # Démarrage du bot avec gestion d'erreur améliorée
        logger.info("Démarrage du bot...")
        await application.run_polling(
            drop_pending_updates=True,  # Ignorer les messages reçus pendant l'arrêt
            allowed_updates=['message', 'callback_query']  # Limiter les types de mises à jour
        )

    except TelegramError as e:
        logger.error(f"Erreur Telegram lors du démarrage: {e}")
        raise
    except Exception as e:
        logger.error(f"Erreur critique lors du démarrage: {e}")
        logger.exception("Détails de l'erreur:")
        raise
    finally:
        # Nettoyage du fichier PID à la fin
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du fichier PID: {e}")

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Arrêt du bot par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")
        logger.exception("Détails de l'erreur:")
    finally:
        # S'assurer que le bot se termine proprement
        try:
            loop.close()
        except Exception:
            pass