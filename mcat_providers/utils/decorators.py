import asyncio
import functools

def async_lru_cache_parameterless(async_function):
    @functools.lru_cache
    def cached_async_function(*args, **kwargs):
        coroutine = async_function(*args, **kwargs)
        return asyncio.ensure_future(coroutine)
    return cached_async_function

def async_lru_cache(*lru_cache_args, **lru_cache_kwargs):
    def async_lru_cache_decorator(async_function):
        @functools.lru_cache(*lru_cache_args, **lru_cache_kwargs)
        def cached_async_function(*args, **kwargs):
            coroutine = async_function(*args, **kwargs)
            return asyncio.ensure_future(coroutine)
        return cached_async_function
    return async_lru_cache_decorator