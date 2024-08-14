import sys
import asyncio
from mcat_providers.sources import flixhq

if __name__ == "__main__":
  src = flixhq.FlixHq()
  data = asyncio.run(src.scrape_all(
    tmdb=sys.argv[1],
    media_type="movie"
  ))
  print(data.as_dict)
