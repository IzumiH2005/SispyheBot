import asyncio
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class SisyphePersona:
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
        self.chat = self.model.start_chat(history=[])
        self._initialize_persona()

    def _initialize_persona(self):
        """Initialise le persona avec le prompt système"""
        try:
            self.chat = self.model.start_chat(history=[])
            self.chat.send_message(SYSTEM_PROMPT)
            logger.info("Persona initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du persona: {e}")
            raise

    def _format_response(self, response):
        """Formate la réponse pour respecter le style de Sisyphe"""
        text = response.text
        if not text.strip():
            return "*tourne une page sans répondre*"

        # Si la réponse est trop longue, la raccourcir
        if len(text) > 200 and not any(marker in text.lower() for marker in ['explique', 'développe']):
            text = text.split('.')[0] + '.'

        # Ajouter des actions si nécessaire
        if 'explique' in text.lower():
            text = "*pose son livre* " + text

        return text

    async def get_response(self, message):
        """Génère une réponse en fonction du message reçu de manière asynchrone"""
        try:
            # Utiliser asyncio.to_thread pour exécuter l'appel API de manière asynchrone
            response = await asyncio.to_thread(self.chat.send_message, message)
            formatted_response = self._format_response(response)
            logger.debug(f"Message reçu: {message[:50]}...")
            logger.debug(f"Réponse générée: {formatted_response[:50]}...")
            return formatted_response
        except Exception as e:
            logger.error(f"Erreur lors de la génération de la réponse: {e}")
            if "quota" in str(e).lower():
                return "*ferme son livre* Un moment de pause s'impose..."
            return "*fronce les sourcils* Une pensée m'échappe..."