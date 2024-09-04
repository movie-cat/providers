import re
import httpx
import asyncio

from datetime import datetime
from typing import Optional, Union, List, Dict, Tuple

from mcat_providers.sources import BaseSource
from mcat_providers.utils.decorators import async_lru_cache
from mcat_providers.providers.rabbitstream import Rabbitstream
from mcat_providers.utils.types import ProviderResponse, SourceResponse, MediaType, MediaEnum

class FlixHq(BaseSource):
    name = "FlixHq"
    base = "https://flixhq.to"
    default_headers = {
        "Referer": "https://flixhq.to/",
        **BaseSource.default_headers
    }
    entries_pattern = re.compile(r"<div class=\"film-detail\">.+?(?=\"clearfix\")")

    def __init__(self, **kwargs) -> None:
        # self.client.cookies.update({"show_share": "true"})
        self.client_headers = kwargs.get("headers") or {}
        self.client_headers.update(self.default_headers)
        self.providers = {
            "upcloud": Rabbitstream(**kwargs),
            "doodstream": None,
            "vidcloud": None,
            "voe": None,
            "upstream": None,
            "mixdrop": None,
        }

    @async_lru_cache(maxsize=128)
    async def query_flix(self, title: str):
        title = title.lower().strip()
        title = "-".join(title.split(" "))
        tasks = [self.client.get(f"{self.base}/search/{title}", params={"page": i}) for i in range(1, 4)]
        responses = await asyncio.gather(*tasks)
        entries = []
        for response in responses:
            data = self.entries_pattern.findall(response.text.replace("\n", "\\n"))
            entries.extend(data)
        results = []
        for entry in entries:
            title = re.search(r"title=\"([^\"]+)\"", entry)
            href = re.search(r"href=\"([^\"]+)\"", entry)
            fdi_type = re.search(r"fdi-type\">([^<]+)", entry)
            if not all([title, href, fdi_type]):
                self.logger.warning(f"failed to gather all items in entry: {entry}")
                continue
            data_1, data_2 = re.findall(r"class=\"fdi-item(?:\sfdi-duration)?\">([^<]+)", entry)
            media_type = fdi_type.group(1).lower()
            if media_type not in ("movie", "tv"):
                raise ValueError(f"Bad fdi_type {media_type}")
            if data_2.strip() == "N/A":
                data_2 = "-1"
            results.append({
                "title": title.group(1),
                "url": f"{self.base}{href.group(1)}",
                "type": MediaEnum.map_enum(media_type),
                "year": int(data_1) if media_type == "movie" else None,
                "duration": int(data_2.removesuffix("m")) if media_type == "movie" else 0,
                "season_count": int(data_1.split(" ")[-1] or -1) if media_type == "tv" else 0,
                "last_season_episode_count": int(data_2.split(" ")[-1] or -1) if media_type == "tv" else 0
            })
        return results

    async def get_seasons(self, flixhq_id: str) -> Optional[Dict]:
        headers={"X-Requested-With": "XMLHttpRequest", **self.default_headers}
        req = await self.client.get(f"{self.base}/ajax/season/list/{flixhq_id}", headers=headers)
        if not req.is_success:
            self.logger.error("Could not retieve available seasons!")
            return None
        season_ids = re.findall(r"<a\sdata-id=\"(\w+)\".+?(?=Season)Season\s(\d+)", req.text.replace("\n", ""))
        return {i[1]: i[0] for i in season_ids}

    async def get_episodes(self, season_id: str) -> Optional[Dict]:
        headers={"X-Requested-With": "XMLHttpRequest", **self.default_headers}
        req = await self.client.get(f"{self.base}/ajax/season/episodes/{season_id}", headers=headers)
        if not req.is_success:
            self.logger.error("Could not retieve available episodes!")
            return None
        episode_ids = re.findall(r"data-id=\"(\w+)\"", req.text)
        return {str(i): ep for i, ep in enumerate(episode_ids, start=1)}

    async def get_sources(self, source_id: str, media_type: MediaType) -> Optional[List]:
        headers={"X-Requested-With": "XMLHttpRequest", **self.default_headers}
        req = await self.client.get(f"{self.base}/ajax/episode/{'list' if media_type == 'Movie' else 'servers'}/{source_id}", headers=headers)
        if not req.is_success:
            self.logger.error("Could not retieve available sources!")
            return None
        # Makes the assumption that titles and linkids are in order
        # And that the patterns will only match things we want
        # Could break in future.
        titles = [title.lower() for title in re.findall(r"title=\"(?:Server\s)?(\w+)\"", req.text)]
        link_ids = re.findall(r"data-(?:link)?id=\"(\d+)\"", req.text)
        return list(zip(titles, link_ids))

    async def get_file(self, name: str, provider_id: int) -> Tuple[str, Optional[str]]:
        headers={"X-Requested-With": "XMLHttpRequest", **self.default_headers}
        req = await self.client.get(f"{self.base}/ajax/episode/sources/{provider_id}", headers=headers)
        if not req.is_success:
            self.logger.error(f"Could not retieve source: '{name}'")
            return name, None
        data = req.json()
        if not data:
            self.logger.error(f"Could not get data!")
            return name, None
        return name, data.get("link")

    async def resolve_source_id(
        self, 
        title: str, 
        media_type: MediaType,
        duration: int,
        release: str, 
        genres: List, 
        episode_count: int, 
        season_count: int,
        last_air_date: str,
        last_season_episode_count: int,
        languages: List
    ) -> Optional[str]:
        results = await self.query_flix(title)
        title_year = int(release.split("-")[0])
        last_aired_year = int(last_air_date.split("-")[0])
        current_year = datetime.now().year
        filtered_results = []

        for item in results:
            if item["type"] != media_type: 
                continue
            if item["duration"] not in (duration, -1):
                continue
            if item["title"] != title:
                continue
            if media_type == "Movie":
                if item["year"] != title_year:
                    continue
            elif media_type == "Series" and (current_year - last_aired_year) >= 1:
                if item["last_season_episode_count"] not in (last_season_episode_count, -1):
                    continue
                if item["season_count"] not in (season_count, -1):
                    continue
            filtered_results.append(item)
        
        if len(filtered_results) > 1:
            for item in filtered_results.copy():
                if not filtered_results:
                    break
                index = filtered_results.index(item)
                req = await self.client.get(item["url"])
                full_date = re.search(r"Released:<\/span>\s+?(\d+-\d+-\d+)", req.text)
                if not full_date:
                    filtered_results.pop(index)
                    continue
                if full_date.group(1) != release:
                    filtered_results.pop(index)
                    continue
                start = req.text.find('<span class="type">Genre:</span>')
                end = req.text.find('<div class="row-line">', start)
                segment = req.text[start:end]
                page_genres = re.findall(r"href=\"\/genre\/[^\"]+\"\s+?title=\"([^\"]+)\"", segment)
                if not page_genres and genres:
                    filtered_results.pop(index)
                for genre in page_genres:
                    if genre in genres:
                        continue
                    filtered_results.pop(index)
                    break

        if not filtered_results:
            return None

        result = filtered_results[0]
        source_id = result["url"].split("-")[-1]
        return source_id

    async def scrape_all(
        self, 
        media_type: str, 
        season: str = "0", 
        episode: str = "0",
        source_id: Optional[str] = None, 
        tmdb: Optional[str] = None,
    ) -> Optional[SourceResponse]:
        assert source_id or tmdb, "source_id or tmdb must be passed with call!"
        media = MediaType(
            tmdb=tmdb,
            source_id=source_id,
            media_type=media_type,
            episode=episode,
            season=season
        )

        flixhq_id = source_id
        if not source_id:
            data = await self.resolve_tmdb(media)
            flixhq_id = await self.resolve_source_id(**data)

        if not flixhq_id:
            self.logger.error("No valid flixhq_id!")
            return None

        source_id = flixhq_id
        if media.media_type == "Series":
            seasons = await self.get_seasons(flixhq_id)
            season_id = seasons.get(season)
            if not season_id:
                self.logger.error(f"Season '{season}' does not exist in available seasons '{list(seasons.keys())}'")
                return None
            episodes = await self.get_episodes(season_id)
            episode_id = episodes.get(episode)
            if not episode_id:
                self.logger.error(f"Episode '{episode}' does not exist in available episodes '{list(episodes.keys())}'")
                return None
            source_id = episode_id
            
        sources = await self.get_sources(source_id, media.media_type)
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
            resolver = self.providers.get(name, "unknown")
            if not resolver:
                continue
            if resolver == "unknown":
                self.logger.warning(f"Unknown source '{name}'")
                continue
            sub_tasks.append(resolver.resolve(file))
    
        if not sub_tasks:
            self.logger.error("No resolver tasks!")
            return None

        responses = await asyncio.gather(*sub_tasks)
        return SourceResponse(source=self.__class__.__name__, providers=responses)