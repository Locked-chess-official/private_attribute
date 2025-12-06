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
from types import FrameType, CodeType
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
                _original_cache = _cache.copy()
                _cache.clear()
                keys = sorted(_original_cache.keys(), key=lambda x: x[1:])
                for i in keys:
                    _cache[i] = _original_cache[i]
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


def _register_local_code():
    _all_id_code_in_code: dict[int, list[CodeType]] = {}

    class DelControl:
        def __init__(self, obj_id: int):
            self.obj_id = obj_id

        def __del__(self):
            try:
                del _all_id_code_in_code[self.obj_id]
            except KeyError:
                pass

    def _register(typ: PrivateAttrType, decorator=lambda _: _, final_attr_name="_private_register"):
        if not isinstance(typ, PrivateAttrType):
            raise TypeError("typ must be a subclass of PrivateAttrType")
        frame = inspect.currentframe().f_back
        if not frame:
            raise RuntimeError("Cannot find frame")
        if frame.f_code.co_name == "<module>":
            raise RuntimeError("Cannot register code: the last code is illegal")
        code = frame.f_code
        del frame

        def wrapper(func):
            if hasattr(func, final_attr_name):
                raise RuntimeError("Cannot register code: func has this attr, please change")
            if id(code) in _all_id_code_in_code:
                setattr(func, final_attr_name, DelControl(id(func.__code__)))
                _all_id_code_in_code[id(func.__code__)] = _all_id_code_in_code[id(code)]
                return decorator(func)
            all_code = []
            for i in typ.__mro__:
                if id(i) in PrivateAttrType._type_allowed_code:
                    all_code.extend(PrivateAttrType._type_allowed_code[id(i)])
            if code not in all_code:
                raise RuntimeError("Cannot register code: the last code is illegal")
            setattr(func, final_attr_name, DelControl(id(func.__code__)))
            if id(func.__code__) not in _all_id_code_in_code:
                _all_id_code_in_code[id(func.__code__)] = []
            if code not in _all_id_code_in_code[id(func.__code__)]:
                _all_id_code_in_code[id(func.__code__)].append(code)
            return decorator(func)

        return wrapper

    def _check(code):
        return tuple(_all_id_code_in_code.get(id(code), []))

    def _unregister(typ):
        if not isinstance(typ, PrivateAttrType):
            raise TypeError("typ must be a subclass of PrivateAttrType")
        all_code = []
        for i in typ.__mro__:
            if id(i) in PrivateAttrType._type_allowed_code:
                all_code.extend(PrivateAttrType._type_allowed_code[id(i)])
        def wrapper(func):
            code = func.__code__
            for i in _all_id_code_in_code:
                if code in _all_id_code_in_code[i]:
                    _all_id_code_in_code[i].remove(code)
            return func
        return wrapper

    return _register, _check, _unregister

register_to_type, _check, unregister_to_type = _register_local_code()

def _get_all_possible_code(obj):
    if not hasattr(obj, "__get__") and not hasattr(obj, "__call__"):
        return []
    if isinstance(obj, property):
        if obj.fget is not None and hasattr(obj.fget, "__code__"):
            yield from _get_code_from_code(obj.fget.__code__)
        if obj.fset is not None and hasattr(obj.fset, "__code__"):
            yield from _get_code_from_code(obj.fset.__code__)
        if obj.fdel is not None and hasattr(obj.fdel, "__code__"):
            yield from _get_code_from_code(obj.fdel.__code__)
        return
    if _CONTROL_FOR_CHECK and isinstance(obj, _PrivateWrap):
        for i in obj._func_list:
            if hasattr(i, "__code__"):
                yield from _get_code_from_code(i.__code__)
    if hasattr(obj, "__func__"):
        if hasattr(obj.__func__, "__code__"):
            yield from _get_code_from_code(obj.__func__.__code__)
            return
    if isinstance(obj, (functools.partial, functools.partialmethod)):
        if hasattr(obj.func, "__code__"):
            yield from _get_code_from_code(obj.func.__code__)
    return []

def _get_code_from_code(code: CodeType, _seen=None):
    if not isinstance(code, CodeType):
        return []
    if _seen is None:
        _seen = set()
    if id(code) in _seen:
        return []
    _seen.add(id(code))
    yield code
    for const in code.co_consts:
        if isinstance(const, CodeType):
            yield from _get_code_from_code(const, _seen)


def _resortkey(x: dict):
    original_x = x.copy()
    x.clear()
    keys = sorted(original_x.keys())
    for i in keys:
        x[i] = original_x[i]

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
        def change_name(i: str):
            if i.startswith("__") and not i.endswith("__"):
                return f"_{name}{i}"
            return i

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

        history_private_attrs = tuple(set(history_private_attrs))
        hash_private_list = []
        for i in private_attr_list:
            hash_private_list.append(cls._hash_private_attribute(change_name(i)))

        hash_private_list = tuple(sorted(hash_private_list))
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
            if i in attrs or change_name(i) in attrs:
                if i in attrs:
                    original_value = attrs[i]
                    del attrs[i]
                else:
                    original_value = attrs[change_name(i)]
                    del attrs[change_name(i)]
                need_update.append((change_name(i), original_value))
        random.shuffle(all_allowed_attrs)
        original_getattribute = attrs.get("__getattribute__", None)
        if _CONTROL_FOR_CHECK and isinstance(original_getattribute, _PrivateWrap):
            original_getattribute = original_getattribute.result
        original_getattr = attrs.get("__getattr__", None)
        if _CONTROL_FOR_CHECK and isinstance(original_getattr, _PrivateWrap):
            original_getattr = original_getattr.result
        original_setattr = attrs.get("__setattr__", None)
        if _CONTROL_FOR_CHECK and isinstance(original_setattr, _PrivateWrap):
            original_setattr = original_setattr.result
        original_delattr = attrs.get("__delattr__", None)
        if _CONTROL_FOR_CHECK and isinstance(original_delattr, _PrivateWrap):
            original_delattr = original_delattr.result
        original_del = attrs.get("__del__", None)
        if _CONTROL_FOR_CHECK and isinstance(original_del, _PrivateWrap):
            original_del = original_del.result
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
                    if isinstance(i.__code__, CodeType):
                        yield from _get_code_from_code(i.__code__)
                if hasattr(i, "__get__"):
                    yield from _get_all_possible_code(i)

        def is_class_frame(frame: FrameType):
            if frame is None:
                return False
            if frame.f_code.co_name == "<module>":
                return False
            elif frame.f_code.co_name in ('<genexpr>', '<listcomp>', '<setcomp>', '<dictcomp>'):
                return is_class_frame(frame.f_back)
            code_list = list(type_allowed_code[id(type_instance)])
            for i in type_instance.__mro__[1:]:
                if isinstance(i, cls):
                    code_list += list(type_allowed_code[id(i)])
            code_list += [
                __getattribute__.__code__,
                __getattr__.__code__,
                __setattr__.__code__,
                __delattr__.__code__,
                __del__.__code__,
            ]
            if frame.f_code in code_list:
                return True
            register_code = _check(frame.f_code)
            if register_code:
                for i in register_code:
                    if i in code_list:
                        return True
            module = inspect.getmodule(frame)
            clsmodule = inspect.getmodule(cls)
            if module is clsmodule:
                if frame.f_code.co_qualname in (
                    __getattribute__.__code__.co_qualname,
                    __getattr__.__code__.co_qualname,
                    __setattr__.__code__.co_qualname,
                    __delattr__.__code__.co_qualname,
                    __del__.__code__.co_qualname,
                ):
                    return True
            all_possible_local = []
            for i in code_list:
                if not hasattr(i, "co_qualname"):
                    continue
                if frame.f_code.co_qualname.startswith(i.co_qualname):
                    all_possible_local.append(i)
            if not all_possible_local:
                return False
            while frame:
                frame = frame.f_back
                if frame is None:
                    return False
                if frame.f_code in all_possible_local:
                    return True
                for i in all_possible_local:
                    if frame.f_code.co_qualname.startswith(i.co_qualname):
                        break
                else:
                    return False
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
                if cls._hash_private_attribute(attr) in hash_private_list:
                    if id(self) not in obj_attr_dict:
                        obj_attr_dict[id(self)] = {}
                    if not is_class_frame(frame):
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                            name=attr,
                                            obj=self)
                    try:
                        private_attr_name = need_call(id(self), attr)
                        return obj_attr_dict[id(self)][private_attr_name]
                    except KeyError:
                        private_attr_name = need_call(id(type_instance), attr)
                        try:
                            return obj_attr_dict[id(self)][private_attr_name]
                        except KeyError:
                            try:
                                if id(type_instance) in cls._type_attr_dict:
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
                elif cls._hash_private_attribute(attr) in history_private_attrs:
                    if not is_class_frame(frame):
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                            name=attr,
                                            obj=self)
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
                        return result
                raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                    name=attr,
                                    obj=self)
            finally:
                del frame

        def __setattr__(self, attr, value):
            frame = inspect.currentframe()
            frame = frame.f_back
            try:
                if cls._hash_private_attribute(attr) in hash_private_list:
                    if id(self) not in obj_attr_dict:
                        obj_attr_dict[id(self)] = {}
                    if not is_class_frame(frame):
                        raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                            name=attr,
                                            obj=self)
                    if id(type_instance) in cls._type_attr_dict:
                        private_attr_name = need_call(id(type_instance), attr)
                        attribute = cls._type_attr_dict[id(type_instance)].get(private_attr_name, None)
                        if hasattr(attribute, "__set__"):
                            attribute.__set__(self, value)
                            return
                    private_attr_name = need_call(id(self), attr)
                    obj_attr_dict[id(self)][private_attr_name] = value
                    _resortkey(obj_attr_dict[id(self)])
                elif cls._hash_private_attribute(attr) in history_private_attrs:
                    if not is_class_frame(frame):
                        raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                            name=attr,
                                            obj=self)
                    for all_subtype in type_instance.__mro__[1:]:
                        if hasattr(all_subtype, "__setattr__") and isinstance(all_subtype, PrivateAttrType):
                            all_subtype.__setattr__(self, attr, value)
                            break
                elif original_setattr:
                    original_setattr(self, attr, value)
                else:
                    for all_subtype in type_instance.__mro__[1:]:
                        if hasattr(all_subtype, "__setattr__"):
                            all_subtype.__setattr__(self, attr, value)
                            break
            finally:
                del frame

        def __delattr__(self, attr):
            frame = inspect.currentframe()
            frame = frame.f_back
            try:
                if cls._hash_private_attribute(attr) in hash_private_list:
                    if id(self) not in obj_attr_dict:
                        obj_attr_dict[id(self)] = {}
                    if not is_class_frame(frame):
                        raise AttributeError(
                            f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                            name=attr,
                            obj=self)
                    if id(type_instance) in cls._type_attr_dict:
                        private_attr_name = need_call(id(type_instance), attr)
                        attribute = cls._type_attr_dict[id(type_instance)].get(private_attr_name, None)
                        if hasattr(attribute, "__delete__"):
                            attribute.__delete__(self)
                            return
                    private_attr_name = need_call(id(self), attr)
                    try:
                        del obj_attr_dict[id(self)][private_attr_name]
                    except KeyError:
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                            name=attr,
                                            obj=self) from None
                elif cls._hash_private_attribute(attr) in history_private_attrs:
                    if not is_class_frame(frame):
                        raise AttributeError(
                            f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                            name=attr,
                            obj=self)
                    for all_subtype in type_instance.__mro__[1:]:
                        if hasattr(all_subtype, "__delattr__") and isinstance(all_subtype, PrivateAttrType):
                            try:
                                all_subtype.__delattr__(self, attr)
                                break
                            except AttributeError:
                                pass
                elif original_delattr:
                    original_delattr(self, attr)
                else:
                    for all_subtype in type_instance.__mro__[1:]:
                        if hasattr(all_subtype, "__delattr__"):
                            all_subtype.__delattr__(self, attr)
                            break
            finally:
                del frame

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
            if _CONTROL_FOR_CHECK and isinstance(v, _PrivateWrap):
                attrs[k] = v.result
        type_instance = super().__new__(cls, name, bases, attrs)
        type_attr_dict[id(type_instance)] = {need_call(id(type_instance), "__private_attrs__"): tuple(
            (hashlib.sha256(change_name(i).encode("utf-8")).hexdigest(), 
             hashlib.sha256(f"{id(type_instance)}_{change_name(i)}".encode("utf-8")).hexdigest())
            for i in private_attr_list
        )}
        type_allowed_code[id(type_instance)] = tuple(all_code)
        cls._type_need_call[id(type_instance)] = need_call
        for i in need_update:
            new_attr = need_call(id(type_instance), i[0])
            value_i = i[1]
            if _CONTROL_FOR_CHECK and isinstance(value_i, _PrivateWrap):
                value_i = value_i.result
            type_attr_dict[id(type_instance)][new_attr] = value_i
            if hasattr(value_i, "__set_name__"):
                value_i.__set_name__(type_instance, new_attr)
        _resortkey(type_attr_dict[id(type_instance)])
        return type_instance


    def _is_class_code(cls, frame: FrameType):
        if frame is None:
            return False
        if frame.f_code.co_name == "<module>":
            return False
        elif frame.f_code.co_name in ('<genexpr>', '<listcomp>', '<setcomp>', '<dictcomp>'):
            return PrivateAttrType._is_class_code(cls, frame.f_back)
        all_possible_local = []
        code_list = PrivateAttrType._type_allowed_code.get(id(cls), ())
        for i in code_list:
            if not hasattr(i, "co_qualname"):
                continue
            if frame.f_code.co_qualname.startswith(i.co_qualname):
                all_possible_local.append(i)
        code_list += tuple(
            getattr(PrivateAttrType, i).__code__ for i in 
            ("__getattribute__", "__getattr__", "__setattr__", "__delattr__", "__del__")
        )
        if frame.f_code in code_list:
            return True
        for icls in cls.__mro__[1:]:
            code_list = PrivateAttrType._type_allowed_code.get(id(icls), ())
            for i in code_list:
                if not hasattr(i, "co_qualname"):
                    continue
                if frame.f_code.co_qualname.startswith(i.co_qualname):
                    all_possible_local.append(i)
            if frame.f_code in code_list:
                return True
        if not all_possible_local:
            return False
        while frame:
            frame = frame.f_back
            if frame is None:
                return False
            if frame.f_code in all_possible_local:
                return True
            for i in all_possible_local:
                if frame.f_code.co_qualname.startswith(i.co_qualname):
                    break
            else:
                return False
        return False


    def __getattribute__(cls, attr):
        try:
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
        except KeyError:
            pass
        result = super().__getattribute__(attr)
        return result

    def __getattr__(cls, attr):
        frame = inspect.currentframe()
        frame = frame.f_back
        try:
            if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                    PrivateAttrType._type_attr_dict[id(cls)][
                        PrivateAttrType._type_need_call[id(cls)](id(cls), "__private_attrs__")]:
                if not PrivateAttrType._is_class_code(cls, frame):
                    raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                            name=attr,
                                            obj=cls)
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
            if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                    PrivateAttrType._type_attr_dict[id(cls)][
                        PrivateAttrType._type_need_call[id(cls)](id(cls), "__private_attrs__")]:
                if not PrivateAttrType._is_class_code(cls, frame):
                    raise AttributeError(f"cannot set private attribute '{attr}' to class '{cls.__name__}'",
                                        name=attr,
                                        obj=cls)
                private_attr_name = PrivateAttrType._type_need_call[id(cls)](id(cls), attr)
                PrivateAttrType._type_attr_dict[id(cls)][private_attr_name] = value
                _resortkey(PrivateAttrType._type_attr_dict[id(cls)])
            else:
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
            if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
                hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                    PrivateAttrType._type_attr_dict[id(cls)][PrivateAttrType._type_need_call[
                        id(cls)](id(cls), "__private_attrs__")]:
                if not PrivateAttrType._is_class_code(cls, frame):
                    raise AttributeError(f"cannot delete private attribute '{attr}' on class '{cls.__name__}'",
                                        name=attr,
                                        obj=cls)
                private_attr_name = PrivateAttrType._type_need_call[id(cls)](id(cls), attr)
                try:
                    del PrivateAttrType._type_attr_dict[id(cls)][private_attr_name]
                except KeyError:
                    raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                        name=attr,
                                        obj=cls) from None
            else:
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
        finally:
            del frame

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


_CONTROL_FOR_CHECK = False


class PrivateAttrBase(metaclass=PrivateAttrType):
    """
    The base class for creating classes with private attributes.
    Private attributes are defined in the `__private_attrs__` sequence and are only accessible in class.
    """
    __private_attrs__: list[str] | tuple[str] = ()
    __slots__ = ()

class PrivateWrapProxy(PrivateAttrBase):
    """
    The proxy class for the private attribute decorator.
    It can ensure that the original function will be saved.
    """
    __private_attrs__ = ["_decorator", "_func_list"]
    __slots__ = ()
    def __init__(self, decorator, _original_decorator=None):
        self._decorator = decorator
        if isinstance(_original_decorator, _PrivateWrap):
            self._func_list = _original_decorator._func_list
        elif isinstance(_original_decorator, _PrivateWrapParent):
            self._func_list = _original_decorator._private_parent._func_list
        else:
            self._func_list = []

    def __call__(self, func):
        if isinstance(func, _PrivateWrap):
            return _PrivateWrap(self._decorator, func.result, func._func_list + self._func_list)
        return _PrivateWrap(self._decorator, func, [func] + self._func_list)


class _PrivateWrapParent(PrivateAttrBase):
    __private_attrs__ = ["_private_obj", "_private_parent"]
    __slots__ = ()
    def __init__(self, obj, parent: _PrivateWrap):
        self._private_obj = obj
        self._private_parent = parent

    def __getattr__(self, name):
        self._private_obj = getattr(self._private_obj, name)
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0:
            var = args[0]
            if isinstance(var, _PrivateWrap):
                self._private_obj = self._private_parent._result = self._private_obj(var.result)
                self._private_parent._func_list.extend(var._func_list)
                return self._private_parent
            self._private_obj = self._private_parent._result = self._private_obj(*args, **kwargs)
            return self
        else:
            self._private_obj = self._private_parent._result = self._private_obj(*args, **kwargs)
            return self

    def __getitem__(self, name):
        self._private_obj = self._private_obj.__getitem__(name)
        return self

    @property
    def result(self):
        return self._private_obj

    @result.setter
    def _result(self, value):
        self._private_obj = value

    @property
    def _parent(self):
        return self._private_parent


class _PrivateWrap(PrivateAttrBase):
    __private_attrs__ = ["_private_result", "__func_list__"]
    __slots__ = ()
    def __init__(self, decorator, func, original_func: list[Callable]):
        self.__func_list__ = original_func
        self._private_result = decorator(func)

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

    @property
    def result(self):
        return self._private_result

    @result.setter
    def _result(self, value):
        self._private_result = value

    @property
    def _func_list(self):
        return self.__func_list__


_FORWARD_DUNDERS = [
    "__iter__", "__next__", "__len__", "__contains__",
    "__add__", "__radd__", "__sub__", "__rsub__",
    "__mul__", "__rmul__", "__matmul__", "__rmatmul__",
    "__truediv__", "__rtruediv__", "__floordiv__", "__rfloordiv__",
    "__mod__", "__rmod__", "__pow__", "__rpow__",
    "__lshift__", "__rlshift__", "__rshift__", "__rrshift__",
    "__and__", "__rand__", "__xor__", "__rxor__", "__or__", "__ror__",
    "__neg__", "__pos__", "__abs__", "__invert__", "__round__", "__index__",
    "__enter__", "__exit__", "__aiter__", "__anext__", "__await__"
]

def _set_getting_attribute(i):
    def _privatewrap_function(self: _PrivateWrap, *args, **kwargs):
        return _PrivateWrapParent(getattr(self.result, i)(*args, **kwargs), self)
    def _privatewrapparent_function(self: _PrivateWrapParent, *args, **kwargs):
        self._result = getattr(self.result, i)(*args, **kwargs)
        return self

    setattr(_PrivateWrap, i, _privatewrap_function)
    setattr(_PrivateWrapParent, i, _privatewrapparent_function)

for i in _FORWARD_DUNDERS:
    _set_getting_attribute(i)


_CONTROL_FOR_CHECK = True


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
