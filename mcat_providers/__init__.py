import json
import httpx
import asyncio
import logging
from rich.logging import RichHandler

fh = logging.FileHandler('debug.log')
logging.basicConfig(
    level="NOTSET",
    format='%(asctime)s %(levelname)s | %(name)s | %(message)s',
    datefmt='[%H:%M:%S]',
    handlers=[fh]
)
log = logging.getLogger()
loop = asyncio.get_event_loop()
default_timeout = httpx.Timeout(999)
default_ua = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"

client = httpx.AsyncClient(timeout=default_timeout)
sync_client = httpx.Client(timeout=default_timeout)

def main():
    from mcat_providers.sources import flixhq
    
    rich_handler = RichHandler(rich_tracebacks=True)
    rich_handler.setLevel(logging.ERROR)
    log.addHandler(rich_handler)

    source = flixhq.FlixHq()
    sources_list = loop.run_until_complete(
        source.scrape_all(
            tmdb="278",
            media_type="movie",
        )
    )

    return json.dumps(sources_list.as_dict)