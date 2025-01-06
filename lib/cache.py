import time
from functools import wraps
from operator import attrgetter


class _CacheValue(object):
    __slots__ = ["_value", "_modified"]

    def __init__(self, value):
        self._value = value
        self._modified = time.time()

    @property
    def modified(self):
        return self._modified

    @property
    def value(self):
        return self._value

    def expired(self, ttl):
        return time.time() - self._modified > ttl

    def update(self):
        self._modified = time.time()


class _HashedTuple(tuple):
    __hash_value = None

    def __hash__(self):
        hash_value = self.__hash_value
        if hash_value is None:
            self.__hash_value = hash_value = super(_HashedTuple, self).__hash__()
        return hash_value

    def __getstate__(self):
        return {}


def _make_key(args, kwargs, typed, kwd_mark=(object(),), fast_types=(int, str)):
    """
    Make a cache key from optionally typed positional and keyword arguments

    The key is constructed in a way that is flat as possible rather than
    as a nested structure that would take more memory.

    If there is only a single argument and its data type is known to cache
    its hash value, then that argument is returned without a wrapper.  This
    saves space and improves lookup speed.
    """
    key = args
    sorted_kwargs = tuple(sorted(kwargs.items()))
    if sorted_kwargs:
        key += kwd_mark + sorted_kwargs
    if typed:
        key += tuple(type(v) for v in args)
        if sorted_kwargs:
            key += tuple(type(v) for _, v in sorted_kwargs)
    elif len(key) == 1 and type(key[0]) in fast_types:
        return key[0]
    return _HashedTuple(key)


def cached(seconds=60 * 60, max_size=128, typed=False, lru=False):
    def wrapper(func):
        cache = {}

        if max_size == 0:
            # no caching
            new_func = func
        else:
            get_modified = attrgetter("modified")

            @wraps(func)
            def new_func(*args, **kwargs):
                key = _make_key(args, kwargs, typed)
                cache_entry = cache.get(key)  # type: _CacheValue
                if cache_entry is None or cache_entry.expired(seconds):
                    # Check cache size first and clean if necessary
                    if len(cache) >= max_size:
                        min_key = min(cache, key=get_modified)
                        del cache[min_key]

                    result = func(*args, **kwargs)
                    cache[key] = _CacheValue(result)
                else:
                    if lru:
                        cache_entry.update()
                    result = cache_entry.value

                return result

        def cache_clear():
            cache.clear()

        new_func.cache_clear = cache_clear
        return new_func

    return wrapper
