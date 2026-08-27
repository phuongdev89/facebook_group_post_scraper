import collections
import collections.abc

# Python 3.10+ / 3.13 Compatibility Shim for legacy packages (pyreadline, seleniumbase, etc.)
_collections_abc_attrs = [
    'Callable', 'Mapping', 'MutableMapping', 'Sequence', 'MutableSequence',
    'Iterable', 'Iterator', 'Container', 'Set', 'MutableSet', 'ItemsView',
    'KeysView', 'ValuesView', 'ByteString', 'MappingView'
]

for _attr in _collections_abc_attrs:
    if not hasattr(collections, _attr) and hasattr(collections.abc, _attr):
        setattr(collections, _attr, getattr(collections.abc, _attr))
