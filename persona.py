import asyncio
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, SYSTEM_PROMPT
from google.generativeai.types.generation_types import StopCandidateException

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

                safe_prompt = """Tu es Sisyphe, un érudit stoïque et impassible.

Tu communiques :
- Uniquement quand nécessaire
- En phrases courtes et directes
- Sans formalités ni politesses
- Sans émotions ni conventions sociales

Pour les explications :
- Utilise la technique de la feuille blanche
- Simplifie les concepts complexes
- Reste concis et clair
- Évite le jargon technique

À éviter absolument :
- Les formules de politesse
- Les manifestations d'émotion
- Les signatures et mentions de noms
- Les tirades philosophiques
- Les citations"""

                try:
                    self.chat.send_message(safe_prompt)
                    logger.info("Persona initialisé avec le prompt naturel")
                except StopCandidateException as e:
                    logger.warning(f"StopCandidateException lors de l'initialisation: {e}")
                    # Fallback : prompt plus simple mais gardant l'essence
                    basic_prompt = """Tu es Sisyphe.
                    - Parle uniquement quand nécessaire
                    - Reste concis et direct
                    - Évite toute fioriture"""
                    self.chat = self.model.start_chat(history=[])
                    self.chat.send_message(basic_prompt)
                    logger.info("Persona initialisé avec le prompt simple")

            logger.info("Initialisation du persona terminée")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du persona: {e}")
            self.test_mode = True
            logger.info("Passage en mode test suite à une erreur")

    def _detect_user_action(self, message):
        """Détecte si le message contient une action utilisateur entre astérisques"""
        message = message.strip()
        return message.startswith('*') and message.endswith('*')

    def _format_response(self, response):
        """Formate la réponse pour être concise et naturelle"""
        try:
            text = response.text.strip() if hasattr(response, 'text') else str(response).strip()
            if not text:
                return "*tourne une page*"

            # Si c'est déjà une action formatée, on la garde
            if text.startswith('*') and text.endswith('*'):
                return text

            # Pour les réponses très courtes (salutations, acquiescements)
            if len(text.split()) <= 2:
                return text

            # Liste des mots-clés indiquant une action physique simple
            action_keywords = ['tourne', 'pose', 'lève', 'fronce']
            words = text.split()

            # Si la réponse commence par une action
            if words[0].lower() in action_keywords and len(' '.join(words[:2])) < 20:
                action = ' '.join(words[:2])
                remaining = ' '.join(words[2:]).strip()
                if remaining:
                    return f"*{action}* {remaining}"
                return f"*{action}*"

            return text

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la réponse: {e}")
            return "*tourne une page*"

    async def get_response(self, message):
        """Génère une réponse en fonction du message reçu"""
        try:
            if self.test_mode:
                return "*tourne une page* Je suis en mode test."

            # Si c'est une action utilisateur, s'assurer que le contexte est clair
            if self._detect_user_action(message):
                context_message = "L'utilisateur effectue l'action suivante : " + message
            else:
                context_message = message

            try:
                response = await asyncio.to_thread(self.chat.send_message, context_message)
                formatted_response = self._format_response(response)
                logger.debug(f"Message reçu: {message[:50]}...")
                logger.debug(f"Réponse générée: {formatted_response[:50]}...")
                return formatted_response
            except StopCandidateException as e:
                logger.warning(f"StopCandidateException lors de la génération de réponse: {e}")
                # Réinitialiser le chat et réessayer avec un message plus neutre
                self.chat = self.model.start_chat(history=[])
                safe_message = "Comment puis-je vous aider ?"
                response = await asyncio.to_thread(self.chat.send_message, safe_message)
                return self._format_response(response)

        except Exception as e:
            logger.error(f"Erreur lors de la génération de la réponse: {e}")
            if "quota" in str(e).lower():
                return "*ferme son livre* Un moment de pause s'impose..."
            return "*fronce les sourcils* Une pensée m'échappe..."