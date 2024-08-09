import re
import hashlib
from pathlib import Path
from typing import Optional, Union, List, Dict
from mcat_providers.providers.types import ProviderHeaders, Stream

class Provider:
    URL_PATTERN = re.compile(r"^(https:\/\/.+)$")
    TARGET_PATTERNS = {
        "bandwith": re.compile(r"BANDWIDTH=(\d+)"),
        "quality": re.compile(r"RESOLUTION=(\d+x\d+)"),
        "codecs": re.compile(r"CODECS=(?:\"|\')([^\"\']+)"),
        "uri": re.compile(r"URI=(?:\"|\')([^\'\"]+)")
    }

    @staticmethod
    def validate_working_dir(working_dir: Union[Path, str]) -> Path:
        working_dir = working_dir if isinstance(working_dir, Path) else Path(working_dir)
        return working_dir if working_dir.is_dir() else working_dir.parent

    @staticmethod
    def calculate_md5(input_bytes: bytes, _mode: str = "digest") -> Union[bytes, str]:
        md5 = hashlib.md5(input_bytes)
        if _mode == "digest":
            return md5.digest()
        elif _mode == "hexdigest":
            return md5.hexdigest()
        else:
            raise ValueError("Unknown md5 formatting mode '{}'".format(_mode))

    @classmethod
    def meta_item(cls, key: str) -> Optional[str]:
        return cls.__meta__.get(key)

    @classmethod
    def parse_m3u8(cls, headers: ProviderHeaders, m3u8_url: str, m3u8_data: str) -> List:
        '''This is probably badly written.'''
        m3u8_data = m3u8_data.strip().split("\n")
        m3u8_data_parsed = []
        if not m3u8_data:
            print("No m3u8 data!")
            raise ValueError("No m3u8 data!")
        expect_url = False
        parsed_data = {
            "provider": cls.__name__,
            "headers": headers,
            "ext": ".m3u8"
        }
        for item in m3u8_data:
            if expect_url:
                url_match = Provider.URL_PATTERN.search(item)
                if not url_match:
                    continue
                parsed_data.update({"url": url_match.group(1)})
                m3u8_data_parsed.append(Stream(**parsed_data))
                parsed_data = {
                    "provider": cls.__name__,
                    "headers": headers,
                    "ext": ".m3u8"
                }
                expect_url = False
                continue
            data = {}
            for target, pattern in Provider.TARGET_PATTERNS.items():
                regex_match = pattern.search(item)
                if regex_match:
                    data.update({target: regex_match.group(1)})
            if data.get("uri"):
                uri = data.pop("uri")
                if not uri.startswith("/"): uri = f"/{uri}"
                url = f"{m3u8_url}{uri}"
                data.update({"url": url})
                parsed_data.update(data)
                m3u8_data_parsed.append(Stream(**parsed_data))
                parsed_data = {
                    "provider": cls.__name__,
                    "headers": headers,
                    "ext": ".m3u8"
                }
                continue
            if data:
                expect_url = True
                parsed_data.update(data)
        return m3u8_data_parsed