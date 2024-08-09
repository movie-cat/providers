import re
import httpx
import asyncio

from typing import Optional, Union, List, Tuple

from mcat_providers.sources import BaseSource
from mcat_providers.providers.rabbitstream import Rabbitstream
from mcat_providers.utils.types import ProviderResponse, MediaType

class FlixHq(BaseSource):
    name = "FlixHq"
    base = "https://flixhq.to"
    default_headers = {
        "Referer": "https://flixhq.to/",
        **BaseSource.default_headers
    }

    def __init__(self, **kwargs) -> None:
        # self.client.cookies.update({"show_share": "true"})
        self.client_headers = kwargs.get("headers") or {}
        self.client_headers.update(self.default_headers)
        self.providers = {
            "upcloud": Rabbitstream(**kwargs),
            "vidcloud": None,
            "voe": None,
            "upstream": None,
            "mixdrop": None,
        }

    async def get_sources(self, flixhq_id: str) -> Optional[List]:
        headers={"X-Requested-With": "XMLHttpRequest", **self.default_headers}
        req = await self.client.get(f"{self.base}/ajax/episode/list/{flixhq_id}", headers=headers)
        if not req.is_success:
            print("Could not retieve available sources!")
            return None

        # Makes the assumption that titles and linkids are in order
        # And that the patterns will only match things we want
        # Could break in future.
        titles = [title.lower() for title in re.findall(r"title=\"(\w+)\"", req.text)]
        link_ids = re.findall(r"data-linkid=\"(\d+)\"", req.text)
        return list(zip(titles, link_ids))

    async def get_file(self, name: str, provider_id: int) -> Tuple[str, Optional[str]]:
        headers={"X-Requested-With": "XMLHttpRequest", **self.default_headers}
        req = await self.client.get(f"{self.base}/ajax/episode/sources/{provider_id}", headers=headers)
        if not req.is_success:
            print(f"Could not retieve source: '{name}'")
            return name, None
        data = req.json()
        if not data:
            print(f"Could not get data!")
            return name, None
        return name, data.get("link")

    async def scrape_all(self, tmdb: str, media_type: str, season: str = "0", episode: str = "0") -> Optional[List[ProviderResponse]]:
        data = await self.resolve_tmdb(
            MediaType(
                tmdb=tmdb, 
                media_type=media_type,
                episode=episode,
                season=season
            )
        )

        flixhq = data.get("ids", {}).get("flixhq")
        if not flixhq:
            print("No valid flixhq id!")
            return None

        sources = await self.get_sources(flixhq)
        if not sources:
            print("Could not retrieve sources!")
            return None

        def remove_provider(name):
            for idx, data in enumerate(sources.copy()):
                value, _ = data
                if value == name: 
                    del sources[idx]

        for name, ctx in self.providers.items():
            if not ctx:
                remove_provider(name)
        
        tasks = [self.get_file(name, provider_id) for name, provider_id in sources]
        sub_tasks: List = []

        for task in asyncio.as_completed(tasks):
            name, file = await task
            if not file:
                continue
            resolver = self.providers[name]
            if not resolver:
                continue
            sub_tasks.append(resolver.resolve(file))
    
        if not sub_tasks:
            print("No resolver tasks!")
            return None

        return await asyncio.gather(*sub_tasks)