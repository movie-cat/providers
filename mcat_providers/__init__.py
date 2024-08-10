import httpx
import asyncio
import logging
from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)
log = logging.getLogger("rich")

loop = asyncio.get_event_loop()
default_timeout = httpx.Timeout(999)
default_ua = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"

client = httpx.AsyncClient(timeout=default_timeout)
sync_client = httpx.Client(timeout=default_timeout)

def main():
    from mcat_providers.sources import flixhq

    source = flixhq.FlixHq()
    sources_list = loop.run_until_complete(
        source.scrape_all(
            tmdb="4935",
            media_type="movie",
        )
    )

    log.info(sources_list)

    # first_source = sources_list[0]
    # log.info(first_source)

    # source = first_source.streams[0]
    # english_subs = [sub for sub in first_source.subtitles if "english" in sub.language.lower()]
    # command = f"mpv \"{source.url}\" --referrer=\"{source.headers.referrer}\" --user-agent=\"{source.headers.user_agent}\" --sub-file=\"{english_subs[0].url}\""
    # log.info(command)