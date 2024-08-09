import httpx


default_timeout = httpx.Timeout(999)
default_ua = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"

client = httpx.AsyncClient(timeout=default_timeout)
sync_client = httpx.Client(timeout=default_timeout)