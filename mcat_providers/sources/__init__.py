from typing import Optional, Dict

from mcat_providers import client, sync_client, default_ua, log
from mcat_providers.providers import BaseProvider
from mcat_providers.utils.types import MediaType
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
    default_headers: Dict = {"User-Agent": default_ua}

    # def __init__(self):
    #     if self.disabled:
    #         raise DisabledSourceError(f"'{self.__class__.__name__}' has been disabled!")

    @classmethod
    async def resolve_tmdb(cls, media: MediaType):
        req = await cls.client.get(f"https://api.dmdb.network/v1/gmid/{media.gmid}")
        return req.json()