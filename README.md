# m-cat providers

*Contains the logic for scraping the different sources used by movie-cat.*

---

### Status

- **Sources**

    | Source        | Status        |
    | ------------- |:-------------:|
    | Flixhq        | ✅            |
  
- **Providers**

    | Provider     | Status        |
    | ------------- |:-------------:|
    | Rabbitstream  | ✅            |

---

### Usage
I do not recommend using this in its current state.

$ pip install .

$ mcat-providers --src "flixhq" --tmdb 278

$ mcat-providers --src "flixhq" --tmdb 278 > streams.json

OR

```py
import os
import asyncio
from rich.console import Console
from mcat_providers.sources import flixhq

def scrape_flix(loop):
    console = Console()
    source = flixhq.FlixHq()
    sources_list = loop.run_until_complete(
        source.scrape_all(
            tmdb="278",
            media_type="movie",
        )
    )
    console.log(sources_list.as_dict)

    first_source = sources_list[0]
    source = first_source.streams[0]
    english_subs = [sub for sub in first_source.subtitles if "english" in sub.language.lower()]
    os.system(f"mpv \"{source.url}\" --referrer=\"{source.headers.referrer}\" --user-agent=\"{source.headers.user_agent}\" --sub-file=\"{english_subs[0].url}\"")

if __name__ == "__main__":
    from mcat_providers import rich_handle
    rich_handle.setLevel("NOTSET")
    loop = asyncio.get_event_loop()
    scrape_flix(loop)
```