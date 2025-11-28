from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class PrivateAttrMapping(Protocol):
    """Mapping which must contain `__private_attrs__`, but allows any other keys."""
    __private_attrs__: list[str]

    # 允许其它任意键
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
        attrs: PrivateAttrMapping,   # ✨ Protocol，而不是 TypedDict
    ):
        return super().__new__(cls, name, bases, dict(attrs))


class PrivateAttrBase(metaclass=PrivateAttrType):
    __private_attrs__: list[str] = []