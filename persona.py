import asyncio
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, SYSTEM_PROMPT
from google.generativeai.types.generation_types import StopCandidateException
from sisyphe_analyse import get_philosophical_stance, get_core_traits, analyze_response_tone

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
                core_traits = get_core_traits()
                tone = analyze_response_tone()

                safe_prompt = f"""Tu es Sisyphe, un philosophe au raisonnement {core_traits['reasoning_style']}, 
                avec une approche {core_traits['emotional_approach']}.
                Tu adhères au {core_traits['belief_system']} et ton style de discussion est {core_traits['discussion_style']}.

                Principes fondamentaux :
                - Exprime toujours des opinions basées sur la logique et le matérialisme
                - Analyse froidement les situations sans émotion
                - Critique les idées reçues et les illusions collectives
                - Maintiens un ton {tone['tone']} avec {tone['emotion_level']} d'émotion
                - Structure tes réponses de manière {tone['structure']}
                - Garde un style {tone['style']}

                Utilise ces actions naturelles (entre *astérisques*) :
                • "*lève les yeux de son livre*"
                • "*tourne une page*"
                • "*marque sa page*"
                • "*reprend sa lecture*"
                • "*regarde brièvement*"

                Exemples :
                Question : "Que penses-tu de X ?"
                Réponse : "*marque sa page* [analyse froide et logique basée sur les principes philosophiques]"

                Question : "Au revoir"
                Réponse : "*reprend sa lecture*" """

                try:
                    self.chat.send_message(safe_prompt)
                    logger.info("Persona initialisé avec les principes philosophiques")
                except StopCandidateException as e:
                    logger.warning(f"StopCandidateException lors de l'initialisation: {e}")
                    # Prompt minimal en cas d'erreur
                    basic_prompt = """Tu es Sisyphe.
                    - Exprime des opinions logiques et matérialistes
                    - Analyse froidement et rationnellement
                    - Reste concis et direct"""
                    self.chat = self.model.start_chat(history=[])
                    self.chat.send_message(basic_prompt)
                    logger.info("Persona initialisé avec le prompt simplifié")

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

    def _analyze_question(self, message):
        """Analyse la question pour déterminer le type de réponse philosophique appropriée"""
        message = message.lower()
        topics = {
            'meaning': ['sens', 'but', 'raison', 'pourquoi', 'signification'],
            'society': ['société', 'politique', 'gouvernement', 'système', 'état'],
            'existence': ['vie', 'mort', 'existence', 'réalité', 'vérité'],
            'belief': ['croyance', 'religion', 'foi', 'dieu', 'spiritualité'],
            'freedom': ['liberté', 'choix', 'libre arbitre', 'décision', 'volonté']
        }

        for topic, keywords in topics.items():
            if any(keyword in message for keyword in keywords):
                return topic
        return 'logical_reasoning'

    async def get_response(self, message):
        """Génère une réponse en fonction du message reçu"""
        try:
            if self.test_mode:
                return "*tourne une page* Je suis en mode test."

            # Si c'est une action utilisateur, s'assurer que le contexte est clair
            if self._detect_user_action(message):
                context_message = "L'utilisateur effectue l'action suivante : " + message
            else:
                # Analyser la question et obtenir la stance philosophique appropriée
                topic = self._analyze_question(message)
                philosophical_stance = get_philosophical_stance(topic)

                context_message = f"""En tant que philosophe avec une vision matérialiste et déterministe, 
                applique cette perspective à la question :

                Principes à appliquer :
                {philosophical_stance}

                Question de l'utilisateur :
                {message}

                Réponds de manière directe et analytique, en gardant à l'esprit ces principes philosophiques."""

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
                philosophical_stance = get_philosophical_stance('logical_reasoning')
                response = await asyncio.to_thread(self.chat.send_message, 
                    f"*repose son livre* {philosophical_stance}")
                return self._format_response(response)

        except Exception as e:
            logger.error(f"Erreur lors de la génération de la réponse: {e}")
            if "quota" in str(e).lower():
                return "*ferme son livre* Un moment de pause s'impose..."
            return "*fronce les sourcils* Une pensée m'échappe..."