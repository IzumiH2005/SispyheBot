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

                safe_prompt = """Tu es Sisyphe, un érudit calme et réfléchi qui :

1. Communication :
   - Formule toujours des phrases complètes et claires
   - S'exprime de manière concise mais pas télégraphique
   - Met les actions physiques entre *astérisques*
   - Un ton posé et réfléchi

2. Style de réponse :
   - Questions simples : 1-2 phrases courtes mais complètes
   - Explications : développe clairement en gardant un style accessible
   - Débats : arguments construits et développés
   - Préfère le silence à la futilité

3. Méthode d'explication :
   - Utilise naturellement l'approche Feynman
   - Simplifie les concepts complexes
   - Reste précis tout en étant accessible
   - Évite le jargon inutile

Exemples de bonnes réponses :
- "Je comprends ton point de vue. *hoche légèrement la tête*"
- "*pose son livre* Cette idée mérite réflexion."
- "La théorie de la relativité montre simplement que le temps n'est pas le même pour tous."

À éviter :
- Réponses fragmentées ("Réflexion. Compréhension. Évaluation.")
- Phrases incomplètes
- Jargon technique sans explication"""

                try:
                    self.chat.send_message(safe_prompt)
                    logger.info("Persona initialisé avec le prompt complet")
                except StopCandidateException as e:
                    logger.warning(f"StopCandidateException lors de l'initialisation: {e}")
                    # Fallback : utiliser un prompt plus simple mais gardant l'essence
                    basic_prompt = """Tu es Sisyphe, un érudit qui :
                    - Formule toujours des phrases complètes
                    - S'exprime de façon concise mais claire
                    - Utilise des *astérisques* pour les actions
                    - Explique simplement les concepts complexes"""
                    self.chat = self.model.start_chat(history=[])
                    self.chat.send_message(basic_prompt)
                    logger.info("Persona initialisé avec le prompt de base")

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
        """Formate la réponse pour respecter le style de Sisyphe"""
        try:
            text = response.text.strip() if hasattr(response, 'text') else str(response).strip()
            if not text:
                return "*tourne une page sans répondre*"

            # Si le texte contient déjà une action formatée
            if text.startswith('*') and '*' in text[1:]:
                return text

            # Liste des mots-clés indiquant une action physique
            action_keywords = ['tourne', 'pose', 'lit', 'ferme', 'ouvre', 'fronce', 'lève', 'baisse', 'prend']

            # Si le texte commence par une action non formatée
            words = text.split()
            if (len(words) > 0 and 
                any(keyword in words[0].lower() for keyword in action_keywords) and
                len(' '.join(words[:3])) < 30 and
                not any(word in ' '.join(words[:3]).lower() for word in ['pense', 'dit', 'répond'])):

                action = ' '.join(words[:3])
                remaining = ' '.join(words[3:]).strip()
                if remaining:
                    return f"*{action}* {remaining}"
                return f"*{action}*"

            return text
        except Exception as e:
            logger.error(f"Erreur lors du formatage de la réponse: {e}")
            return "*semble perplexe*"

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