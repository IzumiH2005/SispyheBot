import asyncio
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class SisyphePersona:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        if not test_mode:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            self.chat = self.model.start_chat(history=[])
            self._initialize_persona()

    def _initialize_persona(self):
        """Initialise le persona avec le prompt système"""
        try:
            if not self.test_mode:
                self.chat = self.model.start_chat(history=[])
                action_prompt = SYSTEM_PROMPT + "\n\nLorsque tu effectues une action physique, mets-la entre astérisques. " + \
                              "Exemple: '*prend un livre*' pour une action seule, ou '*pose son livre* et commence à parler' " + \
                              "pour une action suivie d'une réponse."
                self.chat.send_message(action_prompt)
            logger.info("Persona initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du persona: {e}")
            raise

    def _detect_user_action(self, message):
        """Détecte si le message contient une action utilisateur entre astérisques"""
        message = message.strip()
        return message.startswith('*') and message.endswith('*')

    def _format_response(self, response):
        """Formate la réponse pour respecter le style de Sisyphe"""
        text = response.text.strip()
        if not text:
            return "*tourne une page sans répondre*"

        # Si le texte contient déjà une action formatée
        if text.startswith('*') and '*' in text[1:]:
            return text  # Garder le format original

        # Liste des mots-clés indiquant une action physique
        action_keywords = ['tourne', 'pose', 'lit', 'ferme', 'ouvre', 'fronce', 'lève', 'baisse', 'prend']

        # Si le texte commence par une action non formatée
        words = text.split()
        if (len(words) > 0 and 
            any(keyword in words[0].lower() for keyword in action_keywords) and
            len(' '.join(words[:3])) < 30 and  # Limiter la longueur de l'action
            not any(word in ' '.join(words[:3]).lower() for word in ['pense', 'dit', 'répond'])):

            action = ' '.join(words[:3])
            remaining = ' '.join(words[3:]).strip()
            if remaining:
                return f"*{action}* {remaining}"
            return f"*{action}*"

        return text

    async def get_response(self, message):
        """Génère une réponse en fonction du message reçu"""
        try:
            if self.test_mode:
                # En mode test, retourner une réponse simulée
                return "*tourne une page* Je suis en mode test."

            # Si c'est une action utilisateur, s'assurer que le contexte est clair pour Gemini
            if self._detect_user_action(message):
                context_message = "L'utilisateur effectue l'action suivante : " + message
            else:
                context_message = message

            response = await asyncio.to_thread(self.chat.send_message, context_message)
            formatted_response = self._format_response(response)
            logger.debug(f"Message reçu: {message[:50]}...")
            logger.debug(f"Réponse générée: {formatted_response[:50]}...")
            return formatted_response
        except Exception as e:
            logger.error(f"Erreur lors de la génération de la réponse: {e}")
            if "quota" in str(e).lower():
                return "*ferme son livre* Un moment de pause s'impose..."
            return "*fronce les sourcils* Une pensée m'échappe..."