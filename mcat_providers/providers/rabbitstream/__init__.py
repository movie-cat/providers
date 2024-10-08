import re
import json
import httpx
import base64
import pythonmonkey

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad

from pathlib import Path
from typing import Optional, Dict, List
from tenacity import retry, retry_if_exception_type, stop_after_attempt, RetryError

from mcat_providers.providers import BaseProvider
from mcat_providers.utils.exceptions import IntegrityError
from mcat_providers.utils.types import ProviderHeaders, ProviderResponse, Subtitle
from mcat_providers.utils.decorators import async_lru_cache, async_lru_cache_parameterless

class Rabbitstream(BaseProvider):
    base = "https://rabbitstream.net"
    default_headers = {
        "Referer": "https://flixhq.to/",
        **BaseProvider.default_headers
    }
    embedded_file = {
        "name": "payload.js",
        "hash": "d587be31e78f245f63afd5331430d0d1",
        "url": "https://raw.githubusercontent.com/movie-cat/embed-scripts/main/rabbitstream/payload.js"
    }

    filename = embedded_file["name"]
    working_dir = BaseProvider.validate_working_dir(Path(__file__))
    file_dir = working_dir.joinpath(filename)

    # We dont want to randomly execute files from the internet
    # So we calculate checksums before allowing the user to use anything
    # If this breaks then that likely means the target file has updated.
    # I will update the hash manually if I modify the file, so updating should fix the issue.
    # If updating doesnt fix the issue then you can fix this manually by updating the file_hash in __meta__ to the new MD5 hash
    # Only update the file hash if you are happy with the content of the file and have deemed it as safe
    if not file_dir.exists():
        payload_url = embedded_file["url"]
        expected_hash = embedded_file["hash"]
        BaseProvider.logger.info(f"Attempting to download most recent version of '{filename}'")
        try:
            req = httpx.get(payload_url)
        except Exception as e:
            BaseProvider.logger.error(e)
            raise IntegrityError(f"Failed to retrieve '{filename}'")
        md5 = BaseProvider.calculate_md5(req.text.encode(), "hexdigest")
        BaseProvider.logger.info(f"Checksum = {md5}, Expected = {expected_hash}")
        if md5 != expected_hash:
            raise IntegrityError(f"Could not validate the checksum of '{filename}'...")
        with open(file_dir, "w", encoding="utf-8") as f:
            f.write(req.text)

    with open(file_dir, "r", encoding="utf-8") as f:
        payload = f.read()

    if not payload:
        raise IntegrityError(f"Could not find any content inside '{filename}' for the WASM bundle!")

    instantiate_and_decrypt = pythonmonkey.eval(payload)

    def __init__(self, **kwargs) -> None:
        self.client_headers = kwargs.get("headers") or {}
        self.client_headers.update(self.default_headers)
    
    @staticmethod
    def base64_to_bytearray(encoded_str) -> bytearray:
        return bytearray(base64.b64decode(encoded_str))

    def format_wasm_key(self, keys: List, kversion: str) -> str:
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
                self.logger.error(e)
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
            self.logger.error("No meta could be retrived!")
            return None
        return meta_match.group(1)

    async def get_sources(self, xrax: str, keys: List, kversion: str, kid: str, browserid: str) -> Optional[Dict]:
        req = await self.client.get(
                f"https://rabbitstream.net/ajax/v2/embed-4/getSources",
                params={"id": xrax, "v": kversion, "h": kid, "b": browserid},
                headers=self.client_headers
            )
        if not req.is_success:
            self.logger.error(
                "Failed to fetch 'getSources' endpoint!\n\t" \
                f"Keys: {keys}\n\tKversion: {kversion}\n\tKid: {kid}\n\tBrowserid: {browserid}" \
                f"Url: {req.url}\n\tStatus: {req.status_code}\n\tBody:\n{req.text}"
            )
            return None
        data = req.json()
        if not data:
            self.logger.error("No JSON data from getSources request!")
            return None
        return data

    @async_lru_cache_parameterless
    async def get_wasm(self) -> bytes:
        wasm_req = await self.client.get(f'https://rabbitstream.net/images/loading.png?v=0.6', headers=self.client_headers)
        return wasm_req.content

    @async_lru_cache(maxsize=128)
    @retry(retry=retry_if_exception_type(ValueError), stop=stop_after_attempt(3))
    async def get_data(self, xrax: str) -> Dict:
        wasm = await self.get_wasm()
        meta = await self.get_meta(xrax)
        if not wasm or not meta:
            raise ValueError("Failed to retrieve wasm or meta!\n\tWasm Exists: {}\nMeta - {}".format(not not wasm, meta))

        keys, kversion, kid, browserid = await self.instantiate_and_decrypt(xrax, meta, wasm)
        sources_data = await self.get_sources(xrax=xrax, keys=keys.tolist(), kversion=kversion, kid=kid, browserid=browserid)
        if not sources_data:
            self.logger.error("Could not retrieve encrypted sources!")
            raise ValueError("Could not retrieve encrypted sources!")

        ciphertext = sources_data.pop("sources")
        if not ciphertext:
            self.logger.error("Could not retrieve ciphertext from encrypted sources!")
            raise ValueError("Could not retrieve ciphertext from encrypted sources!")

        formatted_key = self.format_wasm_key(
            keys=keys.tolist(),
            kversion=kversion
        )
        if not formatted_key:
            self.logger.error("No formatted key!")
            raise ValueError("No formatted key!")

        decryption_key = self.generate_encryption_key(
            salt=self.base64_to_bytearray(ciphertext)[8:16], 
            secret=formatted_key.encode("utf-8")
        )
        if not decryption_key:
            self.logger.error("No decryption key!")
            raise ValueError("No decryption key!")

        decrypted = self.decrypt_aes_data(
            ciphertext=ciphertext, 
            decryption_key=decryption_key
        )
        if not decrypted or "https://" not in decrypted:
            self.logger.error("Failed to decrypt AES data!")
            raise ValueError("Failed to decrypt AES data!")
        subtitles = [Subtitle(**{"language": subtitle.get("label"), "url": subtitle.get("file"), "ext": "." + subtitle.get("file").rpartition(".")[2]}) for subtitle in sources_data.pop("tracks")]
        sources_data.update({"subtitles": subtitles})
        sources_data.update({"sources": json.loads(decrypted)})
        return sources_data

    @async_lru_cache(maxsize=128)
    async def get_qualities(self, playlist: str, provider_headers=ProviderHeaders) -> List:
        req = await self.client.get(playlist, headers=provider_headers.headers)
        if not req.is_success:
            self.logger.error("Failed to request playlist!")
            raise ValueError("Failed to request playlist!")

        base = playlist.rpartition("/")[0]
        m3u8_data = self.parse_m3u8(headers=provider_headers, m3u8_url=base, m3u8_data=req.text)
        if not m3u8_data:
            self.logger.error("No result from parse_m3u8!")
            raise ValueError("No result from parse_m3u8!")
        return m3u8_data

    async def resolve(self, url: str) -> Optional[ProviderResponse]:
        # if self.disabled:
        #     return None

        xrax = url.rpartition("?")[0].rpartition("/")[2]

        try:
            data = await self.get_data(xrax)
        except RetryError:
            self.logger.error("Ran out of retry attempts!")
            return None
        except Exception as e:
            self.logger.error(e)
            return None

        headers = ProviderHeaders(
            origin=self.base,
            referrer=self.base
        )

        playlist = data.get("sources")[0]
        if not playlist or not playlist.get("file"):
            self.logger.error(f"Bad playlist data: {playlist}")
            return None

        qualities = await self.get_qualities(playlist=playlist.get("file"), provider_headers=headers)
        return ProviderResponse(provider=self.__class__.__name__, streams=qualities, subtitles=data.get("subtitles"))