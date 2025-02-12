import os
import httpx
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class PerplexityClient:
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")
        
        self.base_url = "https://api.perplexity.ai"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, messages: List[Dict[str, str]], model: str = "llama-3.1-sonar-small-128k-online") -> Dict[Any, Any]:
        """Fait une requête à l'API Perplexity"""
        url = f"{self.base_url}/chat/completions"
        data = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "top_p": 0.9,
            "return_citations": True,
            "stream": False,
            "frequency_penalty": 1
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Erreur lors de la requête Perplexity: {e}")
            raise

    async def search(self, query: str, context: Optional[str] = None) -> Dict[str, str]:
        """Effectue une recherche avec l'API Perplexity"""
        system_prompt = """En tant que Sisyphe, tu dois:
        - Être concis et précis dans tes réponses
        - Donner des informations vérifiées et sourcées
        - Rester objectif et factuel
        - Traduire la réponse en français si nécessaire
        - Organiser l'information de manière claire et structurée
        - Citer les sources en bas de la réponse
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Recherche et synthétise les informations sur: {query}"}
        ]
        
        if context:
            messages[1]["content"] += f"\nContexte additionnel: {context}"

        try:
            response = await self._make_request(messages)
            
            # Extraire la réponse et les citations
            content = response["choices"][0]["message"]["content"]
            citations = response.get("citations", [])
            
            # Formater la réponse avec les sources
            formatted_response = content
            if citations:
                formatted_response += "\n\nSources:\n"
                formatted_response += "\n".join([f"- {citation}" for citation in citations])
            
            return {"response": formatted_response}
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            return {"error": f"Une erreur est survenue: {str(e)}"}

    async def search_images(self, query: str, site: str) -> List[str]:
        """Recherche des images sur Pinterest ou Zerochan via Perplexity"""
        system_prompt = f"""En tant qu'assistant de recherche d'images, tu dois :
        1. Rechercher uniquement sur {site}
        2. Retourner UNIQUEMENT les liens directs vers les images (pas de texte supplémentaire)
        3. Ne sélectionner que les images de haute qualité
        4. Format de réponse : un lien par ligne, commençant par http ou https
        5. Ignorer tout ce qui n'est pas un lien direct vers une image
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Trouve les 5 meilleures images pour '{query}' sur {site}. "
                                    f"Retourne UNIQUEMENT les liens directs vers les images, un par ligne."}
        ]

        try:
            response = await self._make_request(messages)
            content = response["choices"][0]["message"]["content"]

            # Extraire uniquement les URLs valides
            urls = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith(('http://', 'https://')) and any(ext in line.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    urls.append(line)

            logger.info(f"Trouvé {len(urls)} images sur {site} pour la requête '{query}'")
            return urls[:5]  # Retourne les 5 premiers liens valides

        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'images sur {site}: {e}")
            return []

    async def search_youtube(self, query: str) -> List[Dict[str, str]]:
        """Recherche des vidéos YouTube via Perplexity"""
        system_prompt = """En tant qu'assistant de recherche YouTube, tu dois :
        1. Rechercher uniquement des vidéos YouTube pertinentes
        2. Retourner les informations au format Markdown : [Titre](URL)
        3. Ne sélectionner que des vidéos de qualité et pertinentes
        4. Vérifier que les URLs sont bien des liens YouTube valides
        5. Retourner uniquement les 5 meilleurs résultats
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Trouve les 5 meilleures vidéos YouTube pour: {query}. "
                                    f"Format de réponse: [Titre](URL), une vidéo par ligne"}
        ]

        try:
            response = await self._make_request(messages)
            content = response["choices"][0]["message"]["content"]

            # Parse la réponse pour extraire les titres et URLs
            videos = []
            for line in content.split('\n'):
                line = line.strip()
                if '[' in line and '](' in line and ')' in line:
                    # Extraire le titre et l'URL du format Markdown
                    title = line[line.find('[')+1:line.find(']')]
                    url = line[line.find('(')+1:line.find(')')]

                    # Vérifier que c'est bien une URL YouTube
                    if 'youtube.com/watch?v=' in url or 'youtu.be/' in url:
                        videos.append({"title": title, "url": url})

            logger.info(f"Trouvé {len(videos)} vidéos YouTube pour la requête '{query}'")
            return videos[:5]  # Retourner les 5 premières vidéos

        except Exception as e:
            logger.error(f"Erreur lors de la recherche YouTube: {e}")
            return []