import re
import json
import httpx
import base64
import asyncio
import pythonmonkey

from pathlib import Path
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad
from typing import Optional, Dict, List
from tenacity import retry, retry_if_exception_type, stop_after_attempt, RetryError

from mcat_providers.providers import Provider
from mcat_providers.providers.types import ProviderHeaders, ProviderResponse, Subtitle

from mcat_providers.utils.exceptions import IntegrityError
from mcat_providers.utils.decorators import async_lru_cache, async_lru_cache_parameterless

class Rabbitstream(Provider):
    __meta__ = {
        "name": "Rabbitstream",
        "filename": "payload.js",
        "file_hash": "d587be31e78f245f63afd5331430d0d1",
        "file_url": "https://raw.githubusercontent.com/movie-cat/embed-scripts/main/rabbitstream/payload.js",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "referrer": "https://rabbitstream.net",
        "origin": "https://rabbitstream.net",
    }

    def __init__(self, **kwargs) -> None:
        filename = self.meta_item("filename")
        timeout = httpx.Timeout(kwargs.get("timeout", 999))
        working_dir = self.validate_working_dir(kwargs.get("working_dir", Path(__file__)))
        file_dir = working_dir.joinpath(filename)

        # We dont want to randomly execute files from the internet
        # So we calculate checksums before allowing the user to use anything
        # If this breaks then that likely means the target file has updated.
        # I will update the hash manually if I modify the file, so updating should fix the issue.
        # If updating doesnt fix the issue then you can fix this manually by updating the file_hash in __meta__ to the new MD5 hash
        # Only update the file hash if you are happy with the content of the file and have deemed it as safe
        if not file_dir.exists():
            payload_url = self.meta_item("file_url")
            expected_hash = self.meta_item("file_hash")
            print(f"Attempting to download most recent version of '{filename}'")
            try:
                req = httpx.get(payload_url)
            except httpx.ConnectError:
                raise IntegrityError("Failed to retrieve '{}'".format(filename))
            md5 = self.calculate_md5(req.text.encode(), "hexdigest")
            print(f"Checksum = {md5}, Expected = {expected_hash}")
            if md5 != expected_hash:
                raise IntegrityError("Could not validate the checksum of '{}'...".format(filename))
            with open(file_dir, "w", encoding="utf-8") as f:
                f.write(req.text)

        with open(file_dir, "r", encoding="utf-8") as f:
            PAYLOAD = f.read()

        if not PAYLOAD:
            raise IntegrityError("Could not find '{}' for the WASM bundle!".format(filename))

        self.instantiate_and_decrypt = pythonmonkey.eval(PAYLOAD)
        self.client = httpx.AsyncClient(timeout=timeout)
        self.client_headers = {"User-Agent": self.meta_item("user-agent"), "Referrer": "https://flixhq.to/"}

    @staticmethod
    def base64_to_bytearray(encoded_str) -> bytearray:
        return bytearray(base64.b64decode(encoded_str))

    @staticmethod
    def format_wasm_key(keys: List, kversion: str) -> str:
        def convert_to_bytes(kversion: int) -> List[int]:
            return [
                (4278190080 & kversion) >> 24,
                (16711680 & kversion) >> 16,
                (65280 & kversion) >> 8,
                255 & kversion
            ]
        
        def xor_with_version(keys: List, kversion_bytes: List[int]) -> Optional[List]:
            try:
                for i in range(len(keys)):
                    keys[i] ^= kversion_bytes[i % len(kversion_bytes)]
                return keys
            except Exception as e:
                print(e)
                return None

        converted = convert_to_bytes(int(kversion))
        processed_keys = xor_with_version(keys, converted) or keys
        return base64.b64encode(bytearray(processed_keys)).decode('utf-8')

    def generate_encryption_key(self, salt, secret) -> bytes:
        key = self.calculate_md5(secret + salt)
        current_key = key
        while len(current_key) < 48:
            key = self.calculate_md5(key + secret + salt)
            current_key += key
        return current_key

    def decrypt_aes_data(self, ciphertext, decryption_key) -> str:
        cipher_data = self.base64_to_bytearray(ciphertext)
        encrypted = cipher_data[16:]
        AES_CBC = AES.new(
            decryption_key[:32], AES.MODE_CBC, iv=decryption_key[32:]
        )
        decrypted_data = unpad(
            AES_CBC.decrypt(encrypted), AES.block_size
        )
        return decrypted_data.decode("utf-8")

    async def get_meta(self, xrax: str) -> Optional[str]:
        embed_req = await self.client.get(f"https://rabbitstream.net/v2/embed-4/{xrax}?z=", headers=self.client_headers)
        meta_match = re.search(r"name=\"fyq\"\s?content=\"(\w+)\"", embed_req.text)
        if not meta_match:
            print("No meta could be retrived!")
            return None
        return meta_match.group(1)

    async def get_sources(self, xrax: str, kversion: str, kid: str, browserid: str) -> Optional[Dict]:
        req = await self.client.get(
                f"https://rabbitstream.net/ajax/v2/embed-4/getSources",
                params={"id": xrax, "v": kversion, "h": kid, "b": browserid},
                headers=self.client_headers
            )
        if not req.is_success:
            print(
                "Failed to fetch 'getSources' endpoint!\n\t" /
                f"Keys: {keys}\n\tKversion: {kversion}\n\tKid: {kid}\n\tBrowserid: {browserid}" / 
                f"Url: {req.url}\n\tStatus: {req.status_code}\n\tBody:\n{req.text}"
            )
            return None
        data = req.json()
        if not data:
            print("No JSON data from getSources request!")
            return None
        return data

    @async_lru_cache_parameterless
    async def get_wasm(self) -> bytes:
        wasm_req = await self.client.get(f'https://rabbitstream.net/images/loading.png?v=0.6', headers=self.client_headers)
        return wasm_req.content

    @async_lru_cache(maxsize=512)
    @retry(retry=retry_if_exception_type(ValueError), stop=stop_after_attempt(3))
    async def get_data(self, xrax: str) -> List:
        wasm = await self.get_wasm()
        meta = await self.get_meta(xrax)
        if not wasm or not meta:
            raise ValueError("Failed to retrieve wasm or meta!\n\tWasm Exists: {}\nMeta - {}".format(not not wasm, meta))

        keys, kversion, kid, browserid = await self.instantiate_and_decrypt(xrax, meta, wasm)
        sources_data = await self.get_sources(xrax=xrax, kversion=kversion, kid=kid, browserid=browserid)
        ciphertext = sources_data.pop("sources")
        if not ciphertext:
            print("Could not retrieve encrypted sources!")
            raise ValueError("Could not retrieve encrypted sources!")

        formatted_key = self.format_wasm_key(
            keys=keys.tolist(),
            kversion=kversion
        )
        if not formatted_key:
            print("No formatted key!")
            raise ValueError("No formatted key!")

        decryption_key = self.generate_encryption_key(
            salt=self.base64_to_bytearray(ciphertext)[8:16], 
            secret=formatted_key.encode("utf-8")
        )
        if not decryption_key:
            print("No decryption key!")
            raise ValueError("No decryption key!")

        decrypted = self.decrypt_aes_data(
            ciphertext=ciphertext, 
            decryption_key=decryption_key
        )
        if not decrypted or "https://" not in decrypted:
            print("Failed to decrypt AES data!")
            raise ValueError("Failed to decrypt AES data!")
        subtitles = [Subtitle(**{"language": subtitle.get("label"), "url": subtitle.get("file"), "ext": "." + subtitle.get("label").rpartition(".")[2]}) for subtitle in sources_data.pop("tracks")]
        sources_data.update({"subtitles": subtitles})
        sources_data.update({"sources": json.loads(decrypted)})
        return sources_data

    @async_lru_cache(maxsize=512)
    async def get_qualities(self, playlist: str, provider_headers=ProviderHeaders) -> List:
        req = await self.client.get(playlist, headers=provider_headers.headers)
        if not req.is_success:
            print("Failed to request playlist!")
            raise ValueError("Failed to request playlist!")

        base = playlist.rpartition("/")[0]
        m3u8_data = self.parse_m3u8(headers=provider_headers, m3u8_url=base, m3u8_data=req.text)
        if not m3u8_data:
            print("No result from parse_m3u8!")
            raise ValueError("No result from parse_m3u8!")
        return m3u8_data

    async def resolve(self, xrax: str) -> Optional[ProviderResponse]:
        try:
            data = await self.get_data(xrax)
        except RetryError:
            print("Ran out of retry attempts!")
            return None
        except Exception as e:
            print(e)
            return none

        headers = ProviderHeaders(
            origin=self.meta_item("origin"),
            referrer=self.meta_item("referrer"),
            user_agent=self.meta_item("user-agent")
        )

        playlist = data.get("sources")[0]
        if not playlist or not playlist.get("file"):
            print(f"Bad playlist data: {playlist}")
            return None

        qualities = await self.get_qualities(playlist=playlist.get("file"), provider_headers=headers)
        return ProviderResponse(provider=self.__class__.__name__, streams=qualities, subtitles=data.get("subtitles"))