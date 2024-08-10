import json
import httpx
import click
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
rich_handle = RichHandler(rich_tracebacks=True)
rich_handle.setLevel(logging.CRITICAL)
log.addHandler(rich_handle)

loop = asyncio.get_event_loop()
default_timeout = httpx.Timeout(999)
default_ua = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
client = httpx.AsyncClient(timeout=default_timeout)
sync_client = httpx.Client(timeout=default_timeout)

def handle_flixhq(tmdb: str, media_type: str, se: str, ep: str, **kwargs):
    from mcat_providers.sources import flixhq
    source = flixhq.FlixHq()
    sources_list = loop.run_until_complete(
        source.scrape_all(
            tmdb=tmdb,
            media_type=media_type,
            season=se,
            episode=ep
        )
    )
    return json.dumps(sources_list.as_dict)

@click.command()
@click.option("--src", required=True)
@click.option("--tmdb", required=True)
@click.option("--media-type", default="movie")
@click.option("--se", default="0")
@click.option("--ep", default="0")
@click.option("--log-level", default=50, show_default=True) # logging.CRITICAL default
def main(src: str, **kwargs):
    rich_handle.setLevel(kwargs.pop("log_level"))

    if src.lower() == "flixhq":
        data = handle_flixhq(**kwargs)
        print(data)
        return data

    raise ValueError(f"Unknown source: '{src}'")