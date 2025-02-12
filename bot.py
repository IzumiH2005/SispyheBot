import asyncio
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram.error import TelegramError
from config import TELEGRAM_TOKEN
from handlers import start_command, help_command, handle_message

# Application de nest_asyncio pour gérer les boucles d'événements imbriquées
nest_asyncio.apply()

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def main():
    """Fonction principale du bot"""
    try:
        # Création de l'application
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Ajout des handlers
        application.add_handler(CommandHandler('start', start_command))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Démarrage du bot
        logger.info("Démarrage du bot...")
        await application.run_polling()

    except TelegramError as e:
        logger.error(f"Erreur Telegram lors du démarrage: {e}")
        raise
    except Exception as e:
        logger.error(f"Erreur critique lors du démarrage: {e}")
        logger.exception("Détails de l'erreur:")
        raise

if __name__ == '__main__':
    try:
        # Utilisation de get_event_loop().run_until_complete au lieu de asyncio.run
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Arrêt du bot par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur critique: {e}")
        logger.exception("Détails de l'erreur:")