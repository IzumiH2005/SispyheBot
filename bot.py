import asyncio
import logging
import nest_asyncio
import os
import sys
import threading
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
    yt_command,
    fiche_command,
    ebook_command,
    handle_message,
    handle_callback
)

# Application de nest_asyncio pour gérer les boucles d'événements imbriquées
nest_asyncio.apply()

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

async def main():
    """Fonction principale du bot avec gestion améliorée des instances et logging"""
    try:
        # Vérification du PID de manière plus robuste
        pid_file = "/tmp/telegram_bot.pid"

        # Toujours supprimer l'ancien fichier PID au démarrage
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
                logger.info("Ancien fichier PID supprimé")
        except Exception as e:
            logger.warning(f"Erreur lors de la suppression de l'ancien PID: {str(e)}")

        # Écriture du nouveau PID
        try:
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
                logger.info(f"PID {os.getpid()} écrit dans {pid_file}")
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture du PID: {str(e)}")
            # Continue même si on ne peut pas écrire le PID

        # Vérifier le token Telegram
        if not TELEGRAM_TOKEN:
            logger.error("Token Telegram manquant")
            return
        logger.info("Token Telegram validé")

        # Création de l'application avec une meilleure gestion des timeouts
        logger.info("Initialisation de l'application Telegram")
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Ajout des handlers avec logging amélioré
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
        logger.info("Tous les handlers ont été configurés")

        # Démarrage du bot avec gestion d'erreur améliorée
        logger.info("Démarrage du bot...")
        await application.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )

    except TelegramError as e:
        logger.error(f"Erreur Telegram lors du démarrage: {str(e)}")
        logger.exception("Détails de l'erreur Telegram:")
    except Exception as e:
        logger.error(f"Erreur critique lors du démarrage: {str(e)}")
        logger.exception("Détails de l'erreur:")
    finally:
        # Nettoyage du fichier PID à la fin
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
                logger.info(f"Fichier PID {pid_file} supprimé")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du fichier PID: {str(e)}")

if __name__ == '__main__':
    try:
        logger.info("Démarrage du script principal")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Arrêt du bot par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur critique: {str(e)}")
        logger.exception("Détails de l'erreur:")