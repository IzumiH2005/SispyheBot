import os
import logging
import asyncio
import tempfile
import requests
from openai import OpenAI
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import unquote
import re

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

            # Improved search query:  Adds more specific keywords and constraints.
            lang_query = "français" if lang.lower() == "fr" else "english" if lang.lower() == "en" else lang
            query = f"""Je cherche des liens de téléchargement gratuits et légaux pour le livre '{title}' en {lang_query}, au format PDF, EPUB ou MOBI.  Les liens doivent pointer directement vers le fichier du livre et ne pas rediriger vers une page web.  Privilégiez les liens vers des fichiers EPUB ou PDF.  Fournir uniquement les URLs des fichiers, sans texte explicatif.  Limiter les résultats aux fichiers de moins de 50MB.
            """

            messages = [
                {
                    "role": "system",
                    "content": f"""Tu es un expert en recherche de livres électroniques gratuits et légaux.  Ta mission est de trouver des liens directs de téléchargement pour le livre '{title}'.  Tu dois être très précis et ne retourner que des liens qui correspondent exactement à ce livre.  Ne retourne que les URLs de téléchargement direct, sans aucun texte explicatif. Vérifie que chaque lien mène directement à un fichier PDF, EPUB ou MOBI et qu'il est inférieur à 50MB.
                    """
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
                    model="llama-3.1-sonar-small-128k-online",
                    messages=messages,
                    temperature=0.1,
                    stream=False
                ),
                timeout=45.0
            )

            content = response.choices[0].message.content

            # Improved URL filtering: uses regex for more robust matching.
            urls = []
            for line in content.split('\n'):
                line = line.strip()
                match = re.match(r"(https?://\S+\.(pdf|epub|mobi))", line, re.IGNORECASE)
                if match:
                    urls.append({
                        'url': match.group(1),
                        'filename': self.get_filename_from_url(match.group(1), title, lang)
                    })

            logger.info(f"Nombre de liens trouvés: {len(urls)}")
            return urls

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la recherche du livre")
            raise TimeoutError("La recherche du livre prend trop de temps")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche du livre: {str(e)}")
            raise

    def get_filename_from_url(self, url: str, title: str, lang: str) -> str:
        """Génère un nom de fichier approprié pour l'ebook"""
        try:
            # Improved filename sanitization:  More comprehensive character removal.
            clean_title = re.sub(r'[\\/:*?"<>|]', "_", title.strip())

            extension = os.path.splitext(url.lower())[1] if os.path.splitext(url.lower())[1] in ['.pdf','.epub','.mobi'] else '.pdf'

            return f"{clean_title}_{lang}{extension}"

        except Exception as e:
            logger.error(f"Erreur lors de la génération du nom de fichier: {str(e)}")
            return f"{title.replace(' ', '_')}_{lang}.pdf"

    async def download_ebook(self, url: str, filename: str) -> Optional[str]:
        """Télécharge l'ebook et retourne le chemin du fichier temporaire"""
        temp_file = None
        try:
            logger.info(f"Téléchargement de l'ebook depuis: {url}")

            # Enhanced error handling: More detailed checks and logging.
            head_response = requests.head(url, allow_redirects=True, timeout=10)
            head_response.raise_for_status() # Raise HTTPError for bad responses


            content_type = head_response.headers.get('content-type', '').lower()
            if not any(t in content_type for t in ['pdf', 'epub', 'mobi', 'octet-stream', 'application']):
                logger.warning(f"Type de contenu non supporté: {content_type}.  Skipping download.")
                return None

            content_length = head_response.headers.get('content-length')
            if content_length and int(content_length) > 50 * 1024 * 1024:
                logger.warning("Fichier trop volumineux (>50MB). Skipping download.")
                return None

            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='_' + filename)
            total_size = 0

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > 50 * 1024 * 1024:
                        temp_file.close()
                        os.unlink(temp_file.name)
                        logger.warning("Fichier trop volumineux pendant le téléchargement.  Download aborted.")
                        return None
                    temp_file.write(chunk)

            temp_file.close()

            # Improved validation: added more robust checks to handle various ebook formats.
            with open(temp_file.name, 'rb') as f:
                header = f.read(1024) # Increased header size for better detection
                if not (header.startswith(b'%PDF') or  # PDF
                        header.startswith(b'\x50\x4b\x03\x04') or # EPUB
                        b'BOOKMOBI' in header):   # MOBI
                    logger.warning("Le fichier ne semble pas être un ebook valide.  Download aborted.")
                    os.unlink(temp_file.name)
                    return None

            return temp_file.name

        except requests.exceptions.HTTPError as e:
            logger.error(f"Erreur HTTP lors du téléchargement de l'ebook: {str(e)}")
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            return None
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de l'ebook: {str(e)}")
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            return None

    async def search_and_download(self, title: str, lang: str = "fr") -> Dict[str, Any]:
        """Recherche et télécharge un ebook"""
        try:
            book_links = await self.extract_book_links(title, lang)

            if not book_links:
                return {"error": "Aucun lien de téléchargement trouvé pour ce livre"}

            for book_link in book_links:
                try:
                    file_path = await self.download_ebook(book_link['url'], book_link['filename'])
                    if file_path:
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