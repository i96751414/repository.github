import sys

PY3 = sys.version_info.major >= 3

if PY3:
    string_types = str

    def str_to_unicode(s):
        return s
else:
    # noinspection PyUnresolvedReferences
    string_types = basestring  # noqa

    def str_to_unicode(s):
        return s.decode("utf-8")
