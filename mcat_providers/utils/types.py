from __future__ import annotations

import re
from enum import Enum
from mcat_providers import default_ua
from typing import Optional, Union, List, Dict

# Enums
class QualityEnum(Enum):
    P_144 = "144p"
    P_240 = "240p"
    P_360 = "360p"
    P_480 = "480p"
    P_720 = "720p"
    P_1080 = "1080p"
    P_1440 = "1440p"
    P_2160 = "2160p"
    P_4320 = "4320p"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def process_quality_str(quality_str: str) -> str:
        quality_str = quality_str.lower()
        quality_str = quality_str.strip()
        quality_str = re.sub(r"[^a-zA-Z0-9]", "", quality_str)
        return quality_str

    @classmethod
    def map_enum(cls, quality: str) -> QualityEnum:
        quality = cls.process_quality_str(quality)
        if quality in ["7680x4320", "4320p", "8k"]:
            return cls.P_4320
        elif quality in ["4096x2160", "2160p", "ultrahd", "uhd", "4k"]:
            return cls.P_2160
        elif quality in ["2560x1440", "1440p", "quadhd", "wqhd", "qhd"]:
            return cls.P_1440
        elif quality in ["1920x1080", "1080p", "fullhd", "fhd"]:
            return cls.P_1080
        elif quality in ["1280x720", "720p", "hd"]:
            return cls.P_720
        elif quality in ["854x480", "480p"]:
            return cls.P_480
        elif quality in ["640x360", "360p"]:
            return cls.P_360
        elif quality in ["426x240", "240p"]:
            return cls.P_240
        elif quality in ["144p"]:
            return cls.P_144
        else:
            print(f"Unknown quality: {quality}")
            return cls.UNKNOWN

class MediaEnum(Enum):
    MOVIE = "Movie"
    SERIES = "Series"
    ANIME = "Anime"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def process_media_type(media_type: str) -> str:
        media_type = media_type.lower()
        return media_type.strip()

    @classmethod
    def map_enum(cls, meda_type: str) -> MediaEnum:
        meda_type = cls.process_media_type(meda_type)
        if any(keyword in meda_type for keyword in ["movie"]):
            return cls.MOVIE
        if any(keyword in meda_type for keyword in ["tv", "series"]):
            return cls.SERIES
        if any(keyword in meda_type for keyword in ["anime"]):
            return cls.ANIME
        return cls.UNKNOWN

    @property
    def gmid_key(self) -> Optional[str]:
        if self == MediaEnum.MOVIE:
            return "M"
        elif self == MediaEnum.SERIES:
            return "S"
        return None

# Types
class MediaType:
    def __init__(
        self,
        tmdb: Union[str, int],
        media_type: Union[str, MediaEnum],
        season: Union[str, int] = "0",
        episode: Union[str, int] = "0",
    ) -> None:
        self.tmdb = str(tmdb)
        self.media_type = media_type if isinstance(media_type, MediaEnum) else MediaEnum.map_enum(media_type)
        self.season = str(season)
        self.episode = str(episode)

    @property
    def gmid(self) -> str:
        gmid = f"{self.media_type.gmid_key}.{self.tmdb}"
        if self.media_type == MediaEnum.SERIES:
            gmid += f".{self.season}.{self.episode}"
        return gmid

class ProviderHeaders:
    def __init__(
        self, 
        origin: Optional[str] = None, 
        referrer: Optional[str] = None, 
        user_agent: Optional[str] = None, 
        additional_headers: Optional[Dict] = None,
        **kwargs
    ) -> None:
        self._origin = origin
        self._referrer = referrer
        self._user_agent = user_agent or default_ua
        self._headers = {
            "Origin": self._origin,
            "Referrer": self._referrer,
            "User-Agent": self._user_agent,
        }
        if additional_headers:
            self._headers.update(additional_headers)
        self._headers.update(kwargs)

    @property
    def origin(self) -> str:
        if not self._origin:
            raise ValueError("Origin must be set first!")
        return self._origin

    @origin.setter
    def origin(self, value: str) -> None:
        self._origin = value
        self._headers.update({"Origin": self._origin})

    @property
    def referrer(self) -> str:
        if not self._referrer:
            raise ValueError("Referrer must be set first!")
        return self._referrer

    @referrer.setter
    def referrer(self, value: str) -> None:
        self._referrer = value
        self._headers.update({"Referrer": self._referrer})

    @property
    def user_agent(self) -> str:
        if not self._user_agent:
            raise ValueError("User agent must be set first!")
        return self._user_agent
    
    @user_agent.setter
    def user_agent(self, value: str) -> None:
        self._user_agent = value
        self._headers.update({"User-Agent": self._user_agent})

    @property
    def headers(self) -> Dict:
        if not self._origin:
            raise ValueError("Origin must be set first!")
        if not self._referrer:
            raise ValueError("Referrer must be set first!")
        if not self._user_agent:
            raise ValueError("User agent must be set first!")
        return self._headers.copy()

    def add_header(self, key: str, value: str) -> None:
        self._headers[key] = value

    def remove_header(self, key: str) -> None:
        if key in self._headers:
            del self._headers[key]

    def __repr__(self) -> str:
        return f"ProviderHeaders(origin='{self._origin}', referrer='{self._referrer}', user_agent='{self._user_agent}'"

class Subtitle:
    def __init__(self, language: str, url: str, ext: str):
        self.language = language
        self.url = url
        self.ext = ext

    @property
    def as_dict(self) -> Dict:
        return {
            "language": self.language,
            "url": self.url,
            "ext": self.ext
        }

    def __repr__(self) -> str:
        return f"Subtitle(language='{self.language}', url='{self.url}', ext='{self.ext}')"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Subtitle):
            return False
        return self.language == other.language and self.url == other.url and self.ext == other.ext

    def __hash__(self) -> int:
        return hash((self.language, self.url, self.ext))

class Stream:
    def __init__(
        self, 
        provider: str,
        headers: ProviderHeaders,
        url: str,
        ext: str,
        quality: Union[str, QualityEnum], 
        codec: Optional[str] = None, 
        bandwith: Optional[int] = None,
        audio_channels: Optional[int] = None,
        **kwargs
    ) -> None:
        self.provider = provider
        self.headers = headers
        self.url = url
        self.ext = ext
        self.quality = quality if isinstance(quality, QualityEnum) else QualityEnum.map_enum(quality) 
        self.codec = codec
        self.bandwith = bandwith
        self.audio_channels = audio_channels # TODO

    @property
    def as_dict(self) -> Dict:
        return {
            "provider": self.provider,
            "headers": self.headers.headers,
            "url": self.url,
            "ext": self.ext,
            "quality": self.quality,
            "codec": self.codec,
            "bandwith": self.bandwith,
            "audio_channels": self.audio_channels
        }

    def __repr__(self) -> str:
        return f"Stream(provider='{self.provider}', headers={self.headers}, url='{self.url}', ext='{self.ext}'," \
               f"quality={self.quality}, codec='{self.codec}', bandwith={self.bandwith}, audio_channels={self.audio_channels})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Stream):
            return False
        return self.url == other.url and self.quality == other.quality and \
               self.provider == other.provider and self.headers == other.headers and\
               self.ext == other.ext and self.codec == other.codec and self.bandwith == other.bandwith and\
               self.audio_channels == other.audio_channels

    def __hash__(self) -> int:
        return hash((self.url, self.quality, self.provider, self.headers, self.ext, self.codec, self.bandwith, self.audio_channels))

class ProviderResponse:
    def __init__(
            self,
            provider: str,
            streams: List[Stream], 
            subtitles: List[Subtitle],
        ) -> None:
        self.provider = provider
        self.streams = streams
        self.subtitles = subtitles

    @property
    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "streams": [stream.as_dict for stream in self.streams],
            "subtitles": [subtitle.as_dict for subtitle in self.subtitles]
        }

    def __repr__(self) -> str:
        return f"ProviderResponse(provider='{self.provider}', streams={self.streams}, subtitles={self.subtitles})"