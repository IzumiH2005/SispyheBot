import os
import logging
import asyncio
from openai import OpenAI
from typing import Dict, Any, Optional
from scraper import StartpageImageScraper

logger = logging.getLogger(__name__)

class FicheClient:
    def __init__(self):
        """Initialise le client pour la création de fiches d'animes/séries"""
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        logger.info("Initialisation du client pour les fiches")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.perplexity.ai"
        )
        self.image_scraper = StartpageImageScraper()

    async def create_fiche(self, titre: str) -> Dict[str, Any]:
        """Crée une fiche détaillée pour un anime/série"""
        try:
            if not titre.strip():
                return {"error": "Le titre ne peut pas être vide"}

            logger.info(f"Création d'une fiche pour: {titre}")

            # Rechercher une image de couverture
            logger.info(f"Recherche d'une image pour: {titre}")
            image_urls = await self.image_scraper.search_images(f"{titre} anime official cover")
            image_url = image_urls[0] if image_urls else None
            logger.info(f"Image trouvée: {image_url}")

            template = f"""┌───────────────────────────────────────────────┐
│               ✦ {titre} ✦                    │
│              *[TITRE EN JAPONAIS]*            │
└───────────────────────────────────────────────┘

◈ **Type** : [Type]  
◈ **Créateur** : [Créateur]  
◈ **Studio** : [Studio]  
◈ **Année** : [Année]  
◈ **Genres** : [Genres]  
◈ **Épisodes** : [Nombre d'épisodes]  
◈ **Univers** : [Description de l'univers]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **SYNOPSIS** ✦  
▪ [Résumé du synopsis]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **PERSONNAGES PRINCIPAUX** ✦  
🔹 **[Nom du personnage]** – [Description]  
🔹 **[Nom du personnage]** – [Description]  
🔹 **[Nom du personnage]** – [Description]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **THÈMES MAJEURS** ✦  
◈ [Thème 1]  
◈ [Thème 2]  
◈ [Thème 3]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **ADAPTATIONS & ŒUVRES ANNEXES** ✦  
▪ [Manga/Anime/etc.]  
▪ [Manga/Anime/etc.]"""

            system_content = f"""Tu es un expert en anime, manga, séries et webtoons.
Recherche toutes les informations sur {titre} et remplis directement ce template:

{template}

RÈGLES IMPORTANTES:
1. Remplace chaque [crochet] par l'information réelle correspondante
2. Garde EXACTEMENT la mise en forme (**, *, ◈, etc.)
3. Laisse les sections vides avec [crochet] si information non trouvée
4. N'ajoute rien d'autre en dehors de ce format
5. Conserve tous les symboles spéciaux (┌, └, ━, etc.)
6. N'ajoute PAS de section "Sources:" dans le contenu"""

            messages = [
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": f"Crée une fiche complète pour : {titre}"
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

            # Extraire les sources et les formater correctement
            sources = [url for url in content.split() if url.startswith('http')]

            # Toujours ajouter la section des sources à la fin
            content += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            content += "✦ **LIENS & RÉFÉRENCES** ✦\n"
            if sources:
                for source in sources:
                    content += f"🔗 {source}\n"
            else:
                content += "🔗 Aucune source en ligne disponible\n"

            if image_url:
                content += f"\n\n![Couverture]({image_url})"

            return {
                "fiche": content,
                "sources": sources,
                "image_url": image_url
            }

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la création de la fiche")
            return {"error": "La création de la fiche prend trop de temps. Essayez à nouveau."}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur lors de la création de la fiche: {error_msg}")
            logger.exception("Détails complets de l'erreur:")

            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}

            return {"error": f"Une erreur est survenue: {error_msg}"}