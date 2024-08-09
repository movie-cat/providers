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

```py
import asyncio
from pprint import pprint
from mcat_providers.sources import flixhq
from mcat_providers.providers import rabbitstream

def scrape_rabbit(loop):
    xrax = input("Input xrax: ")
    rabbit = rabbitstream.Rabbitstream()
    sources = loop.run_until_complete(rabbit.resolve(xrax))
    pprint(sources.as_dict)

def scrape_flix(loop):
    source = flixhq.FlixHq()
    sources_list = loop.run_until_complete(
        source.scrape_all(
            tmdb="278",
            media_type="movie",
        )
    )

    for sources in sources_list:
        pprint(sources.as_dict)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    scrape_flix(loop)
```