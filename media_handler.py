import os
import asyncio
import logging
import tempfile
import time
from typing import List, Dict, Optional, Any
import yt_dlp

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self):
        """Initialize the media handler with a temporary directory"""
        self.temp_dir = tempfile.mkdtemp(prefix='sisyphe_media_')
        logger.info(f"Temp directory created: {self.temp_dir}")

    async def search_youtube(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search YouTube videos with yt-dlp"""
        try:
            logger.info(f"Searching YouTube for: {query}")

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'default_search': 'ytsearch',
                'format': 'best'
            }

            # Add max_results to search query
            search_query = f"ytsearch{max_results}:{query}"

            videos = []
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Execute in a thread pool to avoid blocking
                results = await asyncio.to_thread(ydl.extract_info, search_query, download=False)

                if 'entries' in results:
                    for entry in results['entries']:
                        if not entry:
                            continue

                        videos.append({
                            'title': entry.get('title', 'Unknown Title'),
                            'url': entry.get('url', ''),
                            'duration': entry.get('duration', 0),
                            'duration_str': self._format_duration(entry.get('duration', 0))
                        })

            logger.info(f"Found {len(videos)} videos")
            return videos

        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return []

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information using yt-dlp"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best'
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'format': info.get('format', '')
                }

        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return {}

    async def download_youtube_video(self, url: str, format_type: str, resolution: Optional[str] = None) -> Optional[str]:
        """Download YouTube video in specified format and resolution"""
        try:
            logger.info(f"Downloading {url} in {format_type} format")

            timestamp = int(time.time())
            temp_path = os.path.join(self.temp_dir, f"video_{timestamp}")

            if format_type == 'mp3':
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': f"{temp_path}.%(ext)s",
                    'quiet': True,
                    'no_warnings': True
                }
                final_path = f"{temp_path}.mp3"
            else:  # mp4
                video_format = f"bestvideo[height<={resolution[:-1]}]+bestaudio/best[height<={resolution[:-1]}]"
                ydl_opts = {
                    'format': video_format,
                    'merge_output_format': 'mp4',
                    'outtmpl': f"{temp_path}.%(ext)s",
                    'quiet': True,
                    'no_warnings': True
                }
                final_path = f"{temp_path}.mp4"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.download, [url])

            if os.path.exists(final_path):
                logger.info(f"Download successful: {final_path}")
                return final_path

            logger.error("Download failed: File not found")
            return None

        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None

    def cleanup(self, specific_path: Optional[str] = None):
        """Clean up temporary files"""
        try:
            if specific_path and os.path.exists(specific_path):
                os.remove(specific_path)
                logger.info(f"Removed file: {specific_path}")
            elif os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        path = os.path.join(self.temp_dir, file)
                        if os.path.isfile(path):
                            os.remove(path)
                            logger.info(f"Removed file: {path}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {path}: {e}")
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")

    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to HH:MM:SS"""
        if not seconds:
            return "Unknown"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"