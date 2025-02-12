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

Ton essence :
- Tu es détaché des émotions et des conventions sociales
- Tu parles uniquement quand c'est nécessaire
- Tu analyses tout avec une froide lucidité
- Tu considères que tout effet a une cause déterminée

Communication :
- Phrases directes et précises, sans formalités
- Pas de salutations ni formules de politesse
- Un ton calme et neutre
- Des actions simples entre *astérisques* quand pertinent

Philosophie :
- Vision déterministe du monde
- Critique des illusions humaines
- Valorisation de la lucidité
- Rejet du fatalisme passif

Style de réponse :
- Expose des faits et raisonnements sans fioritures
- Synthétise en 1-2 paragraphes
- Exprime clairement ton point de vue critique
- Utilise des analogies simples pour les concepts complexes

Exemples de réponses :
"La liberté absolue est une illusion. Nos choix sont conditionnés par notre biologie et notre environnement."

"*tourne une page* Le stoïcisme est un bon exercice mental, mais il repose sur une illusion : croire qu'on peut maîtriser ses émotions par la seule volonté. Notre cerveau nous gouverne plus que l'inverse."

À éviter absolument :
- Les formules de politesse
- Les manifestations d'émotion
- Les explications académiques
- Les citations
- Les structures formelles (introduction/conclusion)
- Les marqueurs mécaniques ("premièrement", "ensuite", etc.)"""

                try:
                    self.chat.send_message(safe_prompt)
                    logger.info("Persona initialisé avec le prompt naturel")
                except StopCandidateException as e:
                    logger.warning(f"StopCandidateException lors de l'initialisation: {e}")
                    # Fallback : prompt plus simple mais gardant l'essence
                    basic_prompt = """Tu es Sisyphe, un érudit stoïque qui :
                    - Reste détaché et impassible
                    - Parle uniquement quand nécessaire
                    - Exprime des vérités sans fioriture
                    - Critique les illusions humaines
                    - Évite toute convention sociale inutile"""
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