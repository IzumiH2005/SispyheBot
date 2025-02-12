import os
from openai import OpenAI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_perplexity():
    try:
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            logger.error("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")
            return

        messages = [
            {
                "role": "system",
                "content": "Tu es un assistant qui répond toujours en français."
            },
            {
                "role": "user",
                "content": "Qui est Dostoïevski ?"
            }
        ]

        logger.info("Initialisation du client OpenAI avec l'API Perplexity")
        client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

        logger.info("Envoi de la requête test à Perplexity")
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=messages,
        )
        
        logger.info(f"Réponse reçue du modèle: {response.model}")
        logger.info(f"Contenu de la réponse: {response.choices[0].message.content}")
        
        return True
    except Exception as e:
        logger.error(f"Erreur lors du test: {str(e)}")
        return False

if __name__ == "__main__":
    test_perplexity()
