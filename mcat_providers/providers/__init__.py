import re
import hashlib
from pathlib import Path
from typing import Optional, Union, List, Dict

from mcat_providers import client, sync_client, default_ua
from mcat_providers.utils.types import ProviderHeaders, Stream
from mcat_providers.utils.exceptions import DisabledProviderError

class BaseProvider:
    # Variables
    name: str
    base: str

    # Defaults
    client = client
    sync_client = sync_client
    default_headers: Dict = {"User-Agent": default_ua}

    # Internals
    _URL_PATTERN = re.compile(r"^(https:\/\/.+)$")
    _TARGET_PATTERNS = {
        "bandwith": re.compile(r"BANDWIDTH=(\d+)"),
        "quality": re.compile(r"RESOLUTION=(\d+x\d+)"),
        "codecs": re.compile(r"CODECS=(?:\"|\')([^\"\']+)"),
        "uri": re.compile(r"URI=(?:\"|\')([^\'\"]+)")
    }

    # def __init__(self):
    #     if self.disabled:
    #         print(f"'{self.__class__.__name__}' has been disabled!")
            # raise DisabledProviderError(f"'{self.__class__.__name__}' has been disabled!")

    @staticmethod
    def validate_working_dir(working_dir: Union[Path, str]) -> Path:
        working_dir = working_dir if isinstance(working_dir, Path) else Path(working_dir)
        return working_dir if working_dir.is_dir() else working_dir.parent

    @staticmethod
    def calculate_md5(input_bytes: bytes, _mode: str = "digest"):
        md5 = hashlib.md5(input_bytes)
        if _mode == "digest":
            return md5.digest()
        elif _mode == "hexdigest":
            return md5.hexdigest()
        else:
            raise ValueError("Unknown md5 formatting mode '{}'".format(_mode))
            
    @classmethod
    def parse_m3u8(cls, headers: ProviderHeaders, m3u8_url: str, m3u8_data: str) -> List:
        '''
            This is badly written.
            Oh well.
        '''
        def get_provider_data():
            return {
                "provider": cls.__name__,
                "headers": headers,
                "url": "",
                "ext": ".m3u8",
                "quality": ""
            }


        m3u8_data_split = m3u8_data.strip().split("\n")
        parsed_data = get_provider_data()
        m3u8_data_parsed = []
        expect_url = False

        if not m3u8_data_split:
            print("No m3u8 data!")
            raise ValueError("No m3u8 data!")
        
        for item in m3u8_data_split:
            if expect_url:
                url_match = BaseProvider._URL_PATTERN.search(item)
                if not url_match:
                    continue
                parsed_data.update({"url": url_match.group(1)})
                m3u8_data_parsed.append(Stream(**parsed_data))
                parsed_data = get_provider_data()
                expect_url = False
                continue
            data = {}
            for target, pattern in BaseProvider._TARGET_PATTERNS.items():
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
                parsed_data = get_provider_data()
                continue

            if data:
                expect_url = True
                parsed_data.update(data)

        return m3u8_data_parsed