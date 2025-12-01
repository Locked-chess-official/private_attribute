"""
A module that provides a metaclass for creating classes with private attributes.
Private attributes are defined in the `__private_attrs__` sequence and are only
You can use the `PrivateAttrBase` metaclass to create classes with private attributes.
The attributes which are private are not on the instance's `__dict__` and cannot be accessed outside
but in the classmethods it is reachable.
Usage example:
```python
class MyClass(PrivateAttrBase):
    __private_attrs__ = ('private_attr1',)
    def __init__(self):
        self.private_attr1 = 1

    @property
    def public_attr1(self):
        return self.private_attr1
```
"""

from __future__ import annotations
import random
import hashlib
import inspect
from typing import Any, Callable
from types import FrameType
import collections
import string
import threading
import time
import functools

_running_time = time.time()


def _generate_private_attr_cache(mod, _cache={}, _lock=threading.Lock()):  #type: ignore
    def decorator_generate(func: Callable[[int, str], str]) -> Callable[[int, str], str]:
        def wrapper(obj_id: int, attr_name: str) -> str:
            with _lock:
                combined = f"{obj_id}_{attr_name}".encode('utf-8')
                attr_byte = f"{_running_time}_{attr_name}".encode("utf-8")
                hash_obj = hashlib.sha256(combined)
                attr_hash_obj = hashlib.sha256(attr_byte)
                key = (obj_id, hash_obj.hexdigest(), attr_hash_obj.hexdigest())
                if key not in _cache:
                    original_result = result = func(obj_id, attr_name)
                    i = 0
                    while result in _cache.values():
                        i += 1
                        result = original_result + f"_{i}"
                    _cache[key] = result
                return _cache[key]

        return wrapper

    def clear_function(obj_id):
        with _lock:
            original_key = list(_cache.keys())
            for i in original_key:
                if i[0] == obj_id:
                    del _cache[i]

    if mod == "generate":
        return decorator_generate
    else:
        return clear_function


@_generate_private_attr_cache("generate")
def _generate_private_attr_name(obj_id: int, attr_name: str) -> str:
    combined = f"{obj_id}_{attr_name}".encode('utf-8')
    hash_obj = hashlib.sha256(combined)

    seed = int(hash_obj.hexdigest(), 16)
    random_proxy = random.Random(seed)

    def generate_random_ascii(length):
        chars = string.printable
        return ''.join(random_proxy.choice(chars) for _ in range(length))

    part1 = generate_random_ascii(6)
    part2 = generate_random_ascii(8)
    part3 = generate_random_ascii(4)

    return f"_{part1}_{part2}_{part3}"


_clear_obj = _generate_private_attr_cache("clean")


class PrivateWrapProxy:
    """
    The proxy class for the private attribute decorator.
    It can ensure that the original function will be saved.
    """
    def __init__(self, decorator):
        self.decorator = decorator

    def __call__(self, func):
        if isinstance(func, _PrivateWrap):
            return _PrivateWrap(self.decorator, func._private_result, func.__func_list__)
        return _PrivateWrap(self.decorator, func, [func])


class _PrivateWrapParent:
    def __init__(self, obj, parent: _PrivateWrap):
        self._private_obj = obj
        self.parent = parent

    def __getattr__(self, name):
        return _PrivateWrapParent(getattr(self._private_obj, name), self.parent)

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0:
            var = args[0]
            if isinstance(var, _PrivateWrap):
                self._private_obj = self.parent._private_result = self._private_obj(var._private_result)
                self.parent.__func_list__.extend(var.__func_list__)
                functools.update_wrapper(self.parent, self.parent.__func_list__[-1])
                return self.parent
            self._private_obj = self.parent._private_result = self._private_obj(*args, **kwargs)
            return self
        else:
            self._private_obj = self.parent._private_result = self._private_obj(*args, **kwargs)
            return self

    def __getitem__(self, name):
        return _PrivateWrapParent(self._private_obj.__getitem__(name), self.parent)


class _PrivateWrap:
    def __init__(self, decorator, func, original_func: list[Callable]):
        self.__func_list__ = original_func
        self._private_result = decorator(func)
        functools.update_wrapper(self, original_func)

    def __call__(self, *args, **kwargs):
        return self._private_result(*args, **kwargs)

    def __get__(self, instance, owner):
        if hasattr(self._private_result, "__get__"):
            return self._private_result.__get__(instance, owner)
        return self._private_result

    def __set__(self, instance, value):
        if hasattr(self._private_result, "__set__"):
            return self._private_result.__set__(instance, value)

    def __delete__(self, instance):
        if hasattr(self._private_result, "__delete__"):
            return self._private_result.__delete__(instance)

    def __getattr__(self, name):
        return _PrivateWrapParent(getattr(self._private_result, name), self)

    def __set_name__(self, owner, name):
        if hasattr(self._private_result, "__set_name__"):
            self._private_result.__set_name__(owner, name)

    def __wrapped__(self):
        return self._private_result

    def __getitem__(self, name):
        return _PrivateWrapParent(self._private_result.__getitem__(name), self)


_FORWARD_DUNDERS = [
    "__iter__", "__next__", "__len__", "__contains__", "__str__", "__repr__", 
    "__bool__", "__bytes__", "__format__", "__hash__", "__eq__", "__ne__", "__lt__",
    "__le__", "__gt__", "__ge__", "__add__", "__radd__", "__sub__", "__rsub__",
    "__mul__", "__rmul__", "__matmul__", "__rmatmul__", "__truediv__", "__rtruediv__",
    "__floordiv__", "__rfloordiv__", "__mod__", "__rmod__", "__pow__", "__rpow__",
    "__lshift__", "__rlshift__", "__rshift__", "__rrshift__", "__and__", "__rand__",
    "__xor__", "__rxor__", "__or__", "__ror__", "__neg__", "__pos__", "__abs__",
    "__invert__", "__round__", "__index__", "__enter__", "__exit__", "__aiter__",
    "__anext__", "__await__"]

def _set_getting_attribute(i, cls):
    def _privatewrap_function(self: _PrivateWrap, *args, **kwargs):
        return _PrivateWrapParent(getattr(self._private_result, i)(*args, **kwargs), self)
    def _privatewrapparent_function(self: _PrivateWrapParent, *args, **kwargs):
        return _PrivateWrapParent(getattr(self._private_obj, i)(*args, **kwargs), self.parent)
    if cls is _PrivateWrap:
        return _privatewrap_function
    return _privatewrapparent_function

for i in _FORWARD_DUNDERS:
    setattr(_PrivateWrap, i, _set_getting_attribute(i, _PrivateWrap))
    setattr(_PrivateWrapParent, i, _set_getting_attribute(i, _PrivateWrapParent))


def _get_all_possible_code(obj, _seen=None):
    if _seen is None:
        _seen = set()
    if id(obj) in _seen:
        return []
    _seen.add(id(obj))
    if not hasattr(obj, "__get__") and not hasattr(obj, "__call__"):
        return []
    if isinstance(obj, property):
        if obj.fget is not None and hasattr(obj.fget, "__code__"):
            yield obj.fget.__code__
        if obj.fset is not None and hasattr(obj.fset, "__code__"):
            yield obj.fset.__code__
        if obj.fdel is not None and hasattr(obj.fdel, "__code__"):
            yield obj.fdel.__code__
        return
    if isinstance(obj, _PrivateWrap):
        for i in obj.__func_list__:
            if hasattr(i, "__code__"):
                yield i.__code__
    if hasattr(obj, "__func__"):
        if hasattr(obj.__func__, "__code__"):
            yield obj.__func__.__code__
            return
    return []


class PrivateAttrType(type):
    _type_attr_dict = {}
    _type_allowed_code = {}
    _type_need_call = {}

    @classmethod
    def _hash_private_attribute(cls, name: str) -> tuple[str]:
        return (hashlib.sha256(f"_{_running_time}_{name}".encode("utf-8")).hexdigest(),
                hashlib.sha256(f"{id(cls)}_{name}".encode("utf-8")).hexdigest())

    def __new__(cls, name: str, bases: tuple[type], attrs: dict[str, Any],
                private_func: Callable[[int, str], str] | None=None):
        type_slots = attrs.get("__slots__", ())
        if "__private_attrs__" not in attrs:
            raise TypeError("'__private_attrs__' is required in PrivateAttrType")
        private_attr_list = list(attrs.get('__private_attrs__', None))
        if not isinstance(private_attr_list, 
                          collections.abc.Sequence) or isinstance(private_attr_list, (str, bytes)):
            raise TypeError("'__private_attrs__' must be a sequence of the string")
        history_private_attrs = []
        for i in bases:
            if isinstance(i, cls):
                history_private_attrs += list(i.__private_attrs__)

        hash_private_list = []
        for i in private_attr_list:
            hash_private_list.append(cls._hash_private_attribute(i))

        invalid_names = [
            "__private_attrs__",
            "__name__",
            "__module__",
            "__class__",
            "__dict__",
            "__slots__",
            "__weakref__",
            "__getattribute__",
            "__getattr__",
            "__setattr__",
            "__delattr__",
            "__del__",
            "__mro__"
        ]
        for i in invalid_names:
            if i in private_attr_list:
                raise TypeError(f"'__private_attrs__' cannot contain the invalid attribute name '{i}'")
        need_update = []
        all_allowed_attrs = list(attrs.values())
        for i in private_attr_list:
            if not isinstance(i, str):
                raise TypeError(f"'__private_attrs__' should only contain string elements, not '{type(i).__name__}'")
            if i in type_slots:
                raise TypeError("'__private_attrs__' cannot contain the attribute name in '__slots__'")
            if i in attrs:
                original_value = attrs[i]
                del attrs[i]
                need_update.append((i, original_value))
        original_getattribute = attrs.get("__getattribute__", None)
        if isinstance(original_getattribute, _PrivateWrap):
            original_getattribute = original_getattribute._private_result
        original_getattr = attrs.get("__getattr__", None)
        if isinstance(original_getattr, _PrivateWrap):
            original_getattr = original_getattr._private_result
        original_setattr = attrs.get("__setattr__", None)
        if isinstance(original_setattr, _PrivateWrap):
            original_setattr = original_setattr._private_result
        original_delattr = attrs.get("__delattr__", None)
        if isinstance(original_delattr, _PrivateWrap):
            original_delattr = original_delattr._private_result
        original_del = attrs.get("__del__", None)
        if isinstance(original_del, _PrivateWrap):
            original_del = original_del._private_result
        obj_attr_dict = {}
        type_attr_dict = cls._type_attr_dict
        type_allowed_code = cls._type_allowed_code
        if callable(private_func):
            need_call: Callable[[int, str], str] = _generate_private_attr_cache("generate")(private_func)
        else:
            need_call = _generate_private_attr_name

        def get_all_code_objects():
            for i in all_allowed_attrs:
                if hasattr(i, "__code__"):
                    yield i.__code__
                if hasattr(i, "__get__"):
                    yield from _get_all_possible_code(i)

        def is_class_frame(frame: FrameType):
            if frame is None:
                return False
            if frame.f_code.co_name == "<module>":
                return False
            code_list = list(type_allowed_code[id(type_instance)])
            for i in type_instance.__mro__[1:]:
                if isinstance(i, cls):
                    code_list += list(type_allowed_code[id(i)])
            if frame.f_code in code_list:
                return True
            if frame.f_code in (
                __getattribute__.__code__,
                __getattr__.__code__,
                __setattr__.__code__,
                __delattr__.__code__,
                __del__.__code__,
            ):
                return True
            return False

        def __getattribute__(self, attr):
            if cls._hash_private_attribute(attr) in hash_private_list or \
                cls._hash_private_attribute(attr) in history_private_attrs:
                raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                     name=attr,
                                     obj=self)
            if original_getattribute:
                result = original_getattribute(self, attr)
                if hasattr(result, "__code__"):
                    if result.__code__ not in type_allowed_code[id(type_instance)]:
                        type_allowed_code[id(type_instance)] += (result.__code__,)
                return result
            for all_subtype in type_instance.__mro__[1:]:
                if hasattr(all_subtype, "__getattribute__"):
                    result = all_subtype.__getattribute__(self, attr)
                    if hasattr(result, "__code__"):
                        if result.__code__ not in type_allowed_code[id(type_instance)]:
                            type_allowed_code[id(type_instance)] += (result.__code__,)
                    return result
            raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                 name=attr,
                                 obj=self)

        def __getattr__(self, attr):
            frame = inspect.currentframe()
            frame = frame.f_back
            try:
                caller_locals = frame.f_locals
                caller_self = caller_locals.get('self', None)
                del caller_locals
                if cls._hash_private_attribute(attr) in hash_private_list:
                    if id(self) not in obj_attr_dict:
                        obj_attr_dict[id(self)] = {}
                    if not is_class_frame(frame):
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                            name=attr,
                                            obj=self)

                    if caller_self is not None and isinstance(caller_self, type_instance):
                        try:
                            private_attr_name = need_call(id(self), attr)
                            return obj_attr_dict[id(self)][private_attr_name]
                        except KeyError:
                            private_attr_name = need_call(id(type_instance), attr)
                            try:
                                return obj_attr_dict[id(self)][private_attr_name]
                            except KeyError:
                                try:
                                    if cls._type_attr_dict.get(id(type_instance), None) is not None:
                                        attribute = cls._type_attr_dict[id(type_instance)][private_attr_name]
                                    else:
                                        raise KeyError(id(type_instance))
                                except KeyError:
                                    raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                                        name=attr,
                                                        obj=self) from None
                                else:
                                    if hasattr(attribute, "__get__"):
                                        result = attribute.__get__(self, type_instance)
                                        return result
                                    else:
                                        return attribute
                    else:
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                            name=attr,
                                            obj=self)
                elif cls._hash_private_attribute(attr) in history_private_attrs:
                    if not is_class_frame(frame):
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                            name=attr,
                                            obj=self)
                    if caller_self is not None and isinstance(caller_self, type_instance):
                        for all_subtype in type_instance.__mro__[1:]:
                            if hasattr(all_subtype, "__getattr__") and isinstance(all_subtype, PrivateAttrType):
                                try:
                                    result = all_subtype.__getattr__(self, attr)
                                    return result
                                except AttributeError:
                                    continue
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                            name=attr,
                                            obj=self)
                if original_getattr:
                    result = original_getattr(self, attr)
                    return result
                for all_subtype in type_instance.__mro__[1:]:
                    if hasattr(all_subtype, "__getattr__"):
                        result = all_subtype.__getattr__(self, attr)
                        if hasattr(result, "__code__"):
                            if result.__code__ not in type_allowed_code[id(type_instance)]:
                                type_allowed_code[id(type_instance)] += (result.__code__,)
                        return result
                raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                    name=attr,
                                    obj=self)
            finally:
                del frame
                del caller_self

        def __setattr__(self, attr, value):
            frame = inspect.currentframe()
            frame = frame.f_back
            try:
                caller_locals = frame.f_locals
                caller_self = caller_locals.get('self', None)
                del caller_locals
                if cls._hash_private_attribute(attr) in hash_private_list:
                    if id(self) not in obj_attr_dict:
                        obj_attr_dict[id(self)] = {}
                    if not is_class_frame(frame):
                        raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                            name=attr,
                                            obj=self)
                    if caller_self is not None and isinstance(caller_self, type_instance):
                        private_attr_name = need_call(id(self), attr)
                        obj_attr_dict[id(self)][private_attr_name] = value
                    else:
                        raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                            name=attr,
                                            obj=self)
                elif cls._hash_private_attribute(attr) in history_private_attrs:
                    if not is_class_frame(frame):
                        raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                            name=attr,
                                            obj=self)
                    if caller_self is not None and isinstance(caller_self, type_instance):
                        for all_subtype in type_instance.__mro__[1:]:
                            if hasattr(all_subtype, "__setattr__") and isinstance(all_subtype, PrivateAttrType):
                                all_subtype.__setattr__(self, attr, value)
                                break
                    else:
                        raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                            name=attr,
                                            obj=self)
                elif original_setattr:
                    original_setattr(self, attr, value)
                else:
                    for all_subtype in type_instance.__mro__[1:]:
                        if hasattr(all_subtype, "__setattr__"):
                            all_subtype.__setattr__(self, attr, value)
                            break
            finally:
                del frame
                del caller_self

        def __delattr__(self, attr):
            frame = inspect.currentframe()
            frame = frame.f_back
            try:
                caller_locals = frame.f_locals
                caller_self = caller_locals.get('self', None)
                del caller_locals
                if cls._hash_private_attribute(attr) in hash_private_list:
                    if id(self) not in obj_attr_dict:
                        obj_attr_dict[id(self)] = {}
                    if not is_class_frame(frame):
                        raise AttributeError(
                            f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                            name=attr,
                            obj=self)
                    if caller_self is not None and isinstance(caller_self, type_instance):
                        private_attr_name = need_call(id(self), attr)
                        try:
                            del obj_attr_dict[id(self)][private_attr_name]
                        except KeyError:
                            raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                                name=attr,
                                                obj=self) from None
                    else:
                        raise AttributeError(
                            f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                            name=attr,
                            obj=self)
                elif cls._hash_private_attribute(attr) in history_private_attrs:
                    if not is_class_frame(frame):
                        raise AttributeError(
                            f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                            name=attr,
                            obj=self)
                    if caller_self is not None and isinstance(caller_self, type_instance):
                        for all_subtype in type_instance.__mro__[1:]:
                            try:
                                if hasattr(all_subtype, "__delattr__") and isinstance(all_subtype, PrivateAttrType):
                                    all_subtype.__delattr__(self, attr)
                                    break
                            except AttributeError:
                                continue
                    else:
                        raise AttributeError(
                            f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                            name=attr,
                            obj=self)
                elif original_delattr:
                    original_delattr(self, attr)
                else:
                    for all_subtype in type_instance.__mro__[1:]:
                        if hasattr(all_subtype, "__delattr__"):
                            all_subtype.__delattr__(self, attr)
                            break
            finally:
                del frame
                del caller_self

        def __del__(self):
            if _clear_obj:
                _clear_obj(id(self))
            if id(self) in obj_attr_dict:
                del obj_attr_dict[id(self)]
            if original_del:
                original_del(self)
            else:
                for all_subtype in type.__getattribute__(type_instance, "__mro__")[1:]:
                    if hasattr(all_subtype, "__del__"):
                        all_subtype.__del__(self)
                        break

        def __getstate__(self):
            raise TypeError(f"Cannot pickle '{type_instance.__name__}' objects")

        def __setstate__(self, state):
            raise TypeError(f"Cannot unpickle '{type_instance.__name__}' objects")
        all_code = tuple(get_all_code_objects())

        if "__getstate__" not in attrs:
            attrs["__getstate__"] = __getstate__
        if "__setstate__" not in attrs:
            attrs["__setstate__"] = __setstate__
        attrs['__getattribute__'] = __getattribute__
        attrs['__getattr__'] = __getattr__
        attrs['__setattr__'] = __setattr__
        attrs['__delattr__'] = __delattr__
        attrs["__del__"] = __del__
        attrs["__private_attrs__"] = tuple(hash_private_list)
        all_items = attrs.items()
        for k, v in all_items:
            if isinstance(v, _PrivateWrap):
                attrs[k] = v._private_result
        type_instance = super().__new__(cls, name, bases, attrs)
        type_attr_dict[id(type_instance)] = {need_call(id(type_instance), "__private_attrs__"): tuple(
            (hashlib.sha256(i.encode("utf-8")).hexdigest(), 
             hashlib.sha256(f"{id(type_instance)}_{i}".encode("utf-8")).hexdigest())
            for i in private_attr_list
        )}
        type_allowed_code[id(type_instance)] = tuple(all_code)
        cls._type_need_call[id(type_instance)] = need_call
        for i in need_update:
            new_attr = need_call(id(type_instance), i[0])
            type_attr_dict[id(type_instance)][new_attr] = i[1]
        return type_instance

    def _is_class_code(cls, frame: FrameType):
        if frame is None:
            return False
        if frame.f_code.co_name == "<module>":
            return False
        code_list = PrivateAttrType._type_allowed_code.get(id(cls), ())
        if frame.f_code in code_list:
            return True
        for icls in cls.__mro__[1:]:
            code_list = PrivateAttrType._type_allowed_code.get(id(icls), ())
            if frame.f_code in code_list:
                return True
        return False

    def __getattribute__(cls, attr):
        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
            hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                PrivateAttrType._type_attr_dict[id(cls)][
                    PrivateAttrType._type_need_call[id(cls)](id(cls), "__private_attrs__")]:
            raise AttributeError()
        for icls in type.__getattribute__(cls, "__mro__")[1:]:
            if id(icls) in PrivateAttrType._type_attr_dict:
                if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                    hashlib.sha256(f"{id(icls)}_{attr}".encode("utf-8")).hexdigest()) in \
                        PrivateAttrType._type_attr_dict[id(icls)][
                            PrivateAttrType._type_need_call[id(icls)](id(icls), "__private_attrs__")]:
                    raise AttributeError()
        result = super().__getattribute__(attr)
        return result

    def __getattr__(cls, attr):
        frame = inspect.currentframe()
        frame = frame.f_back
        try:
            caller_locals = frame.f_locals
            caller_cls: type|None = caller_locals.get("cls", None)
            del caller_locals
            if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                    PrivateAttrType._type_attr_dict[id(cls)][
                        PrivateAttrType._type_need_call[id(cls)](id(cls), "__private_attrs__")]:
                if not PrivateAttrType._is_class_code(cls, frame):
                    raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                            name=attr,
                                            obj=cls)
                if caller_cls is not None and issubclass(caller_cls, cls):
                    private_attr_name = PrivateAttrType._type_need_call[id(cls)](id(cls), attr)
                    try:
                        result = PrivateAttrType._type_attr_dict[id(cls)][private_attr_name]
                    except KeyError:
                        raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                            name=attr,
                                            obj=cls) from None
                    else:
                        if hasattr(result, "__get__"):
                            res = result.__get__(None, cls)
                            return res
                        else:
                            return result
                else:
                    raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                        name=attr,
                                        obj=cls)
            elif caller_cls is not None and issubclass(caller_cls, cls) and PrivateAttrType._is_class_code(cls, frame):
                for icls in cls.__mro__[1:]:
                    if id(icls) in PrivateAttrType._type_attr_dict:
                        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                            hashlib.sha256(f"{id(icls)}_{attr}".encode("utf-8")).hexdigest()) in \
                                PrivateAttrType._type_attr_dict[id(icls)][
                                    PrivateAttrType._type_need_call[id(icls)](id(icls), "__private_attrs__")]:
                            try:
                                result = PrivateAttrType.__getattr__(icls, attr)
                                return result
                            except AttributeError:
                                continue
            raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                name=attr,
                                obj=cls)
        finally:
            del frame
            del caller_cls

    def __setattr__(cls, attr, value):
        invalid_names = [
            "__class__",
            "__delattr__",
            "__getattribute__",
            "__getattr__",
            "__setattr__",
            "__getstate__",
            "__setstate__",
            "__del__",
            "__private_attrs__"
        ]
        if attr in invalid_names:
            raise AttributeError(f"cannot set '{attr}' attribute on class '{cls.__name__}'")
        frame = inspect.currentframe()
        frame = frame.f_back
        try:
            caller_locals = frame.f_locals
            caller_cls: type|None = caller_locals.get("cls", None)
            del caller_locals
            if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                    PrivateAttrType._type_attr_dict[id(cls)][
                        PrivateAttrType._type_need_call[id(cls)](id(cls), "__private_attrs__")]:
                if not PrivateAttrType._is_class_code(cls, frame):
                    raise AttributeError(f"cannot set private attribute '{attr}' to class '{cls.__name__}'",
                                        name=attr,
                                        obj=cls)
                if caller_cls is not None and issubclass(caller_cls, cls):
                    private_attr_name = PrivateAttrType._type_need_call[id(cls)](id(cls), attr)
                    PrivateAttrType._type_attr_dict[id(cls)][private_attr_name] = value
                else:
                    raise AttributeError(f"cannot set private attribute '{attr}' to class '{cls.__name__}'",
                                        name=attr,
                                        obj=cls)
            elif PrivateAttrType._is_class_code(cls, frame) and caller_cls is not None and issubclass(caller_cls, cls):
                for icls in cls.__mro__[1:]:
                    if id(icls) in PrivateAttrType._type_attr_dict:
                        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                            hashlib.sha256(f"{id(icls)}_{attr}".encode("utf-8")).hexdigest()) in \
                                PrivateAttrType._type_attr_dict[id(icls)][PrivateAttrType._type_need_call[
                                    id(icls)](id(icls), "__private_attrs__")]:
                            PrivateAttrType.__setattr__(icls, attr, value)
                            return
                else:
                    type.__setattr__(cls, attr, value)
        finally:
            del frame
            del caller_cls

    def __delattr__(cls, attr):
        invalid_names = [
            "__class__",
            "__delattr__",
            "__getattribute__",
            "__getattr__",
            "__setattr__",
            "__getstate__",
            "__setstate__",
            "__del__",
            "__private_attrs__"
        ]
        if attr in invalid_names:
            raise AttributeError(f"cannot delete '{attr}' attribute on class '{cls.__name__}'")
        frame = inspect.currentframe()
        frame = frame.f_back
        try:
            caller_locals = frame.f_locals
            caller_cls: type|None = caller_locals.get("cls", None)
            del caller_locals
            if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                    PrivateAttrType._type_attr_dict[id(cls)][PrivateAttrType._type_need_call[
                        id(cls)](id(cls), "__private_attrs__")]:
                if not PrivateAttrType._is_class_code(cls, frame):
                    raise AttributeError(f"cannot delete private attribute '{attr}' on class '{cls.__name__}'",
                                        name=attr,
                                        obj=cls)
                if caller_cls is not None and issubclass(caller_cls, cls):
                    private_attr_name = PrivateAttrType._type_need_call[id(cls)](id(cls), attr)
                    try:
                        del PrivateAttrType._type_attr_dict[id(cls)][private_attr_name]
                    except KeyError:
                        raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                            name=attr,
                                            obj=cls) from None
                else:
                    raise AttributeError(f"cannot delete private attribute '{attr}' on class '{cls.__name__}'",
                                        name=attr,
                                        obj=cls)
            elif PrivateAttrType._is_class_code(cls, frame) and caller_cls is not None and issubclass(caller_cls, cls):
                for icls in cls.__mro__[1:]:
                    if id(icls) in PrivateAttrType._type_attr_dict:
                        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                            hashlib.sha256(f"{id(icls)}_{attr}".encode("utf-8")).hexdigest()) in \
                                PrivateAttrType._type_attr_dict[id(icls)][
                                    PrivateAttrType._type_need_call[id(icls)](id(icls), "__private_attrs__")]:
                            PrivateAttrType.__delattr__(icls, attr)
                            return
                else:
                    type.__delattr__(cls, attr)
            else:
                type.__delattr__(cls, attr)
        finally:
            del frame
            del caller_cls

    def __del__(cls):
        if callable(_clear_obj):
            _clear_obj(id(cls))
        if id(cls) in PrivateAttrType._type_attr_dict:
            del PrivateAttrType._type_attr_dict[id(cls)]
        if id(cls) in PrivateAttrType._type_allowed_code:
            del PrivateAttrType._type_allowed_code[id(cls)]
        if id(cls) in PrivateAttrType._type_need_call:
            del PrivateAttrType._type_need_call[id(cls)]

    def __getstate__(cls):
        raise TypeError("Cannot pickle PrivateAttrType classes")

    def __setstate__(cls, state):
        raise TypeError("Cannot unpickle PrivateAttrType classes")


class PrivateAttrBase(metaclass=PrivateAttrType):
    """
    The base class for creating classes with private attributes.
    Private attributes are defined in the `__private_attrs__` sequence and are only accessible in class.
    """
    __private_attrs__: list[str] | tuple[str] = ()
    __slots__ = ()


if __name__ == "__main__":
    class MyClass(PrivateAttrBase):
        __private_attrs__ = ('private_attr1',)
        private_attr1 = 1

        def __init__(self, val1, val2):
            self.private_attr1 = val1
            self.public_attr2 = val2

        @property
        def public_attr1(self):
            return self.private_attr1

        @public_attr1.setter
        def public_attr1(self, value):
            self.private_attr1 = value

        @public_attr1.deleter
        def public_attr1(self):
            del self.private_attr1

        @classmethod
        def public_class_attr1(cls):
            return cls.private_attr1


    # Example usage
    obj = MyClass(10, 20)
    try:
        print(obj.private_attr1)  # Should raise AttributeError
    except AttributeError as e:
        print(e)

    print(obj.public_attr1)  # Should print 10
    print(obj.public_attr2)  # Should print 20
    print(obj.public_class_attr1())  # Should print 1
    import gc
    del obj
    print(gc.collect())
