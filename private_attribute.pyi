from typing import Protocol, Any, runtime_checkable, TypeVar, Callable, Type
import collections

T = TypeVar('T')
def register(cls: Type[T], get_code_objects: Callable[[T], list[Any]]) -> None:
    """Register a function to get code objects for a specific class type."""


@runtime_checkable
class PrivateAttrMapping(Protocol):
    """Mapping which must contain `__private_attrs__`, but allows any other keys."""
    __private_attrs__: collections.abc.Sequence[str]

    def __getitem__(self, key: str) -> Any: ...
    def __iter__(self) -> Any: ...
    def __len__(self) -> int: ...
    def get(self, key: str, default: Any = None): ...


class PrivateAttrType(type):
    _type_attr_dict: dict[int, dict[str, Any]] = {}
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: PrivateAttrMapping,
    ):
        return super().__new__(cls, name, bases, dict(attrs))

    def __init__(cls):
        cls.__private_attrs__: collections.abc.Sequence[str]


class PrivateAttrBase(metaclass=PrivateAttrType):
    __private_attrs__: collections.abc.Sequence[str] = []