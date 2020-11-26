import time
from functools import wraps


class _HashedSeq(list):
    __slots__ = 'hash_value'

    # noinspection PyMissingConstructor
    def __init__(self, tup):
        self[:] = tup
        self.hash_value = hash(tup)

    def __hash__(self):
        return self.hash_value


def _make_key(args, kwds, typed, kwd_mark=(object(),), fast_types=(int, str)):
    """
    Make a cache key from optionally typed positional and keyword arguments

    The key is constructed in a way that is flat as possible rather than
    as a nested structure that would take more memory.

    If there is only a single argument and its data type is known to cache
    its hash value, then that argument is returned without a wrapper.  This
    saves space and improves lookup speed.
    """
    key = args
    if kwds:
        key += kwd_mark
        for item in kwds.items():
            key += item
    if typed:
        key += tuple(type(v) for v in args)
        if kwds:
            key += tuple(type(v) for v in kwds.values())
    elif len(key) == 1 and type(key[0]) in fast_types:
        return key[0]
    return _HashedSeq(key)


def cached(seconds=60 * 60, max_size=128, typed=False, lru=False):
    def wrapper(func):
        cache = {}

        if max_size == 0:
            # no caching
            new_func = func
        else:
            @wraps(func)
            def new_func(*args, **kwargs):
                key = _make_key(args, kwargs, typed)
                cache_entry = cache.get(key)
                if cache_entry is None or time.time() - cache_entry[0] > seconds:
                    # Check cache size first and clean if necessary
                    if len(cache) >= max_size:
                        min_key = min(cache, key=lambda k: cache[k][0])
                        del cache[min_key]

                    result = func(*args, **kwargs)
                    cache[key] = [time.time(), result]
                else:
                    if lru:
                        cache_entry[0] = time.time()
                    result = cache_entry[1]

                return result

        def cache_clear():
            cache.clear()

        new_func.cache_clear = cache_clear
        return new_func

    return wrapper
