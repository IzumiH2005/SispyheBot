import os
import logging
import asyncio
import tempfile
import requests
from openai import OpenAI
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import unquote

logger = logging.getLogger(__name__)

class EbookClient:
    def __init__(self):
        """Initialise le client pour la recherche et le téléchargement d'ebooks"""
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        logger.info("Initialisation du client pour les ebooks")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.perplexity.ai"
        )

    async def extract_book_links(self, title: str, lang: str) -> List[Dict[str, str]]:
        """Recherche des liens de téléchargement pour un livre donné"""
        try:
            if not title.strip():
                return []

            logger.info(f"Recherche du livre: {title} en {lang}")

            # Construction de la requête en fonction de la langue
            lang_query = "français" if lang.lower() == "fr" else "english" if lang.lower() == "en" else lang
            query = f"Trouve des liens de téléchargement gratuits et légaux pour le livre '{title}' en {lang_query}. " \
                   f"Retourne uniquement les URLs directes de téléchargement."

            messages = [
                {
                    "role": "system",
                    "content": "Tu es un assistant spécialisé dans la recherche de livres électroniques gratuits et légaux. "
                              "Retourne uniquement les URLs de téléchargement direct, sans texte explicatif."
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            logger.info("Envoi de la requête à l'API Perplexity")
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="sonar-pro",
                    messages=messages,
                    temperature=0.1,
                    stream=False
                ),
                timeout=45.0
            )

            content = response.choices[0].message.content
            
            # Extraction des URLs
            urls = []
            for line in content.split('\n'):
                if line.strip().startswith(('http://', 'https://')):
                    urls.append({
                        'url': line.strip(),
                        'filename': self.get_filename_from_url(line.strip(), title, lang)
                    })

            return urls

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la recherche du livre")
            raise TimeoutError("La recherche du livre prend trop de temps")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche du livre: {str(e)}")
            raise

    def get_filename_from_url(self, url: str, title: str, lang: str) -> str:
        """Génère un nom de fichier approprié pour l'ebook"""
        # Essaie d'extraire le nom du fichier de l'URL
        filename = url.split('/')[-1]
        filename = unquote(filename)
        
        # Si le nom de fichier n'a pas d'extension, ajoute .pdf par défaut
        if '.' not in filename:
            filename = f"{title.replace(' ', '_')}_{lang}.pdf"
        
        return filename

    async def download_ebook(self, url: str, filename: str) -> str:
        """Télécharge l'ebook et retourne le chemin du fichier temporaire"""
        try:
            logger.info(f"Téléchargement de l'ebook depuis: {url}")
            
            # Création d'un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='_' + filename) as temp_file:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                # Téléchargement du fichier par morceaux
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                
                return temp_file.name

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de l'ebook: {str(e)}")
            raise

    async def search_and_download(self, title: str, lang: str = "fr") -> Dict[str, Any]:
        """Recherche et télécharge un ebook"""
        try:
            # Recherche des liens
            book_links = await self.extract_book_links(title, lang)
            
            if not book_links:
                return {"error": "Aucun lien de téléchargement trouvé pour ce livre"}

            # Tentative de téléchargement pour chaque lien
            for book_link in book_links:
                try:
                    file_path = await self.download_ebook(book_link['url'], book_link['filename'])
                    return {
                        "success": True,
                        "file_path": file_path,
                        "filename": book_link['filename']
                    }
                except Exception as e:
                    logger.warning(f"Échec du téléchargement depuis {book_link['url']}: {str(e)}")
                    continue

            return {"error": "Impossible de télécharger le livre depuis les liens trouvés"}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur lors de la recherche et du téléchargement: {error_msg}")
            
            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}
            
            return {"error": f"Une erreur est survenue: {error_msg}"}
