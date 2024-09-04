import os
from typing import Optional, Dict

from mcat_providers import client, sync_client, default_ua, log
from mcat_providers.providers import BaseProvider
from mcat_providers.utils.types import MediaType, MediaEnum
from mcat_providers.utils.decorators import async_lru_cache
from mcat_providers.utils.exceptions import DisabledSourceError

class BaseSource:
    # Variables
    name: str
    base: str

    # Defaults
    logger = log
    client = client
    sync_client = sync_client
    tmdb_api_key = os.getenv("TMDB_API_KEY")
    default_headers = {"User-Agent": default_ua}

    @classmethod
    @async_lru_cache(maxsize=128)
    async def resolve_tmdb(cls, media: MediaType):
        """
        Needs a TMDB_API_KEY in .mcat env in current state
        """
        assert cls.tmdb_api_key, "No tmdb key set!"

        base_url = "https://api.themoviedb.org/3"
        headers = {
            "authorization": f"Bearer {cls.tmdb_api_key}",
        }
        headers.update(cls.default_headers)

        if media.media_type == "Movie":
            endpoint = f"/movie/{media.tmdb}"
        elif media.media_type == "Series":
            endpoint = f"/tv/{media.tmdb}"
        else:
            raise ValueError(f"Unsupported media type: {media.media_type}")

        url = f"{base_url}{endpoint}"

        try:
            response = await cls.client.get(url, headers=headers)
            response.raise_for_status()  
            data = response.json()
            return {
                "title": data.get("title") or data.get("name"),
                "media_type": media.media_type,
                "duration": data.get("runtime", 0),
                "release": data.get("release_date") or data.get("first_air_date"),
                "genres": [item.get("name") for item in data.get("genres", [])],
                "episode_count": data.get("number_of_episodes", 0),
                "season_count": data.get("number_of_seasons", 0),
                "last_air_date": data.get("last_air_date") or data.get("first_air_date") or data.get("release_date"),
                "last_season_episode_count": data.get("seasons", [{}])[-1].get("episode_count", 0),
                "languages": [item.get("iso_639_1") for item in data.get("spoken_languages", [])]
            }
        except Exception as e:
            cls.logger.error(f"Failed to resolve TMDB data for {media.gmid}: {e}")
            raise