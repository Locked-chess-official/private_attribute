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

import random
import hashlib
import inspect
from typing import Any, Callable, TypeVar, Type
from types import FrameType, CodeType
import collections
import string
import threading
import warnings


def _generate_private_attr_cache(mod, _cache={}, _lock=threading.Lock()):  #type: ignore
    def decorator_generate(func: Callable[[int, str], str]) -> Callable[[int, str], str]:
        def wrapper(obj_id: int, attr_name: str) -> str:
            with _lock:
                combined = f"{obj_id}_{attr_name}".encode('utf-8')
                attr_byte = attr_name.encode("utf-8")
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


_REGISTER_GET_TYPE = {}
T = TypeVar('T')

@warnings.deprecated("The 'register' function is deprecated and will be removed in future versions.")
def register(type_obj: Type[T], get_func: Callable[[T], list[CodeType]]):
    """
    Register a type and a function to get all possible code objects from an instance of that type.
    """
    _REGISTER_GET_TYPE[id(type_obj)] = get_func


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
    if hasattr(obj, "__func__"):
        if hasattr(obj.__func__, "__code__"):
            yield obj.__func__.__code__
            return
    return []


class PrivateAttrType(type):
    _type_attr_dict = {}
    _type_allowed_code = {}
    _type_allowed_frame_head = {}

    def __new__(cls, name: str, bases: tuple[type], attrs: dict[str, Any]):
        type_slots = attrs.get("__slots__", ())
        if "__private_attrs__" not in attrs:
            raise TypeError("'__private_attrs__' is required in PrivateAttrType")
        private_attr_list = list(attrs.get('__private_attrs__', None))
        if not isinstance(private_attr_list, 
                          collections.abc.Sequence) or isinstance(private_attr_list, (str, bytes)):
            raise TypeError("'__private_attrs__' must be a sequence of the string")
        change = False
        for i in bases:
            if isinstance(i, cls):
                private_attr_list = list(private_attr_list) + list(i.__private_attrs__)
                change = True
        if change:
            attrs["__private_attrs__"] = tuple(set(private_attr_list))
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
        original_getattr = attrs.get("__getattr__", None)
        original_setattr = attrs.get("__setattr__", None)
        original_delattr = attrs.get("__delattr__", None)
        original_del = attrs.get("__del__", None)
        obj_attr_dict = {}
        type_attr_dict = cls._type_attr_dict
        type_allowed_code = cls._type_allowed_code

        def get_all_code_objects():
            for i in all_allowed_attrs:
                if hasattr(i, "__code__"):
                    yield i.__code__
                if hasattr(i, "__get__"):
                    yield from _get_all_possible_code(i)

        def is_class_frame(frame: FrameType):
            frame = frame.f_back
            if frame is None:
                return False
            if frame.f_code.co_name == "<module>":
                return False
            code_list = list(type_allowed_code[id(type_instance)])
            if frame.f_code in code_list:
                return True
            full_name = frame.f_code.co_qualname
            if full_name.startswith(head_frame) and \
                    isinstance(frame.f_locals.get("self", None), type_instance):
                frame_module = inspect.getmodule(frame)
                type_module = inspect.getmodule(type_instance)
                if frame_module is not type_module:
                    return False
                type_allowed_code[id(type_instance)] += (frame.f_code,)
                return True
            return False

        def __getattribute__(self, attr):
            if attr in private_attr_list:
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
            if attr in private_attr_list:
                if id(self) not in obj_attr_dict:
                    obj_attr_dict[id(self)] = {}
                frame = inspect.currentframe()
                if not is_class_frame(frame):
                    raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                         name=attr,
                                         obj=self)
                frame = frame.f_back
                caller_locals = frame.f_locals
                del frame
                caller_self = caller_locals.get('self', None)
                del caller_locals
                if caller_self is not None and isinstance(caller_self, type_instance):
                    try:
                        private_attr_name = _generate_private_attr_name(id(self), attr)
                        return obj_attr_dict[id(self)][private_attr_name]
                    except KeyError:
                        private_attr_name = _generate_private_attr_name(id(type_instance), attr)
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
                                    if hasattr(result, "__code__"):
                                        if result.__code__ not in type_allowed_code[id(type_instance)]:
                                            type_allowed_code[id(type_instance)] += (result.__code__,)
                                    return result
                                else:
                                    return attribute
                    finally:
                        del caller_self
                else:
                    del caller_self
                    raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                         name=attr,
                                         obj=self)
            if original_getattr:
                result = original_getattr(self, attr)
                if hasattr(result, "__code__"):
                    if result.__code__ not in type_allowed_code[id(type_instance)]:
                        type_allowed_code[id(type_instance)] += (result.__code__,)
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

        def __setattr__(self, attr, value):
            if attr in private_attr_list:
                if id(self) not in obj_attr_dict:
                    obj_attr_dict[id(self)] = {}
                frame = inspect.currentframe()
                if not is_class_frame(frame):
                    raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                         name=attr,
                                         obj=self)
                frame = frame.f_back
                caller_locals = frame.f_locals
                del frame
                caller_self = caller_locals.get('self', None)
                del caller_locals
                if caller_self is not None and isinstance(caller_self, type_instance):
                    private_attr_name = _generate_private_attr_name(id(self), attr)
                    obj_attr_dict[id(self)][private_attr_name] = value
                    del caller_self
                else:
                    del caller_self
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

        def __delattr__(self, attr):
            if attr in private_attr_list:
                if id(self) not in obj_attr_dict:
                    obj_attr_dict[id(self)] = {}
                frame = inspect.currentframe()
                if not is_class_frame(frame):
                    raise AttributeError(
                        f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                        name=attr,
                        obj=self)
                frame = frame.f_back
                caller_locals = frame.f_locals
                del frame
                caller_self = caller_locals.get('self', None)
                del caller_locals
                if caller_self is not None and isinstance(caller_self, type_instance):
                    private_attr_name = _generate_private_attr_name(id(self), attr)
                    try:
                        del obj_attr_dict[id(self)][private_attr_name]
                    except KeyError:
                        raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                             name=attr,
                                             obj=self) from None
                    finally:
                        del caller_self
                else:
                    del caller_self
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

        def __del__(self):
            _clear_obj(id(self))
            if id(self) in obj_attr_dict:
                del obj_attr_dict[id(self)]
            if original_del:
                original_del(self)
            else:
                for all_subtype in type_instance.__mro__[1:]:
                    if hasattr(all_subtype, "__del__"):
                        all_subtype.__del__(self)
                        break

        attrs['__getattribute__'] = __getattribute__
        attrs['__getattr__'] = __getattr__
        attrs['__setattr__'] = __setattr__
        attrs['__delattr__'] = __delattr__
        attrs["__del__"] = __del__

        def __getstate__(self):
            raise TypeError(f"Cannot pickle '{type_instance.__name__}' objects")

        def __setstate__(self, state):
            raise TypeError(f"Cannot unpickle '{type_instance.__name__}' objects")

        if not attrs.get("__getstate__", None):
            attrs["__getstate__"] = __getstate__
        if not attrs.get("__setstate__", None):
            attrs["__setstate__"] = __setstate__
        type_instance = super().__new__(cls, name, bases, attrs)
        type_attr_dict[id(type_instance)] = {_generate_private_attr_name(id(type_instance), "__private_attrs__"): tuple(
            (hashlib.sha256(i.encode("utf-8")).hexdigest(), 
             hashlib.sha256(f"{id(type_instance)}_{i}".encode("utf-8")).hexdigest())
            for i in private_attr_list
        )}
        type_allowed_code[id(type_instance)] = tuple(get_all_code_objects())
        for i in need_update:
            new_attr = _generate_private_attr_name(id(type_instance), i[0])
            type_attr_dict[id(type_instance)][new_attr] = i[1]
        now_frame = inspect.currentframe()
        try:
            last_frame = now_frame.f_back
            if last_frame.f_code.co_name == "<module>":
                head_frame = (f"{name}.",)
            else:
                head_frame = (f"{last_frame.f_code.co_qualname}.{name}.", f"{last_frame.f_code.co_filename}.<local>.{name}")
            cls._type_allowed_frame_head[id(type_instance)] = head_frame
        finally:
            del now_frame
            del last_frame
        return type_instance

    def _is_class_code(cls, frame: FrameType):
        frame = frame.f_back
        if frame is None:
            return False
        if frame.f_code.co_name == "<module>":
            return False
        code_list = PrivateAttrType._type_allowed_code.get(id(cls), ())
        if frame.f_code in code_list:
            return True
        full_name = frame.f_code.co_qualname
        if full_name.startswith(PrivateAttrType._type_allowed_frame_head.get(id(cls), ())) and \
            issubclass(frame.f_locals.get("cls", None), cls):
            frame_module = inspect.getmodule(frame)
            type_module = inspect.getmodule(cls)
            if frame_module is not type_module:
                return False
            return True
        return False

    def __getattribute__(cls, attr):
        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
            hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                PrivateAttrType._type_attr_dict[id(cls)][_generate_private_attr_name(id(cls), "__private_attrs__")]:
            raise AttributeError()
        result = super().__getattribute__(attr)
        if hasattr(result, "__code__"):
            if result.__code__ not in PrivateAttrType._type_allowed_code[id(cls)]:
                PrivateAttrType._type_allowed_code[id(cls)] += (result.__code__,)
        return result

    def __getattr__(cls, attr):
        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
            hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                PrivateAttrType._type_attr_dict[id(cls)][_generate_private_attr_name(id(cls), "__private_attrs__")]:
            frame = inspect.currentframe()
            if not PrivateAttrType._is_class_code(cls, frame):
                raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                     name=attr,
                                     obj=cls)
            frame = frame.f_back
            caller_locals = frame.f_locals
            del frame
            caller_cls: type|None = caller_locals.get("cls", None)
            del caller_locals
            if caller_cls is not None and issubclass(caller_cls, cls):
                private_attr_name = _generate_private_attr_name(id(cls), attr)
                try:
                    result = PrivateAttrType._type_attr_dict[id(cls)][private_attr_name]
                except KeyError:
                    raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                         name=attr,
                                         obj=cls) from None
                else:
                    if hasattr(result, "__get__"):
                        res = result.__get__(None, cls)
                        if hasattr(res, "__code__"):
                            if res.__code__ not in PrivateAttrType._type_allowed_code[id(cls)]:
                                PrivateAttrType._type_allowed_code[id(cls)] += (res.__code__,)
                        return res
                    else:
                        return result
                finally:
                    del caller_cls
            else:
                del caller_cls
                raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                     name=attr,
                                     obj=cls)
        raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                             name=attr,
                             obj=cls)

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
        ]
        if attr in invalid_names:
            raise AttributeError(f"cannot set '{attr}' attribute on class '{cls.__name__}'")
        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
            hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                PrivateAttrType._type_attr_dict[id(cls)][_generate_private_attr_name(id(cls), "__private_attrs__")]:
            frame = inspect.currentframe()
            if not PrivateAttrType._is_class_code(cls, frame):
                raise AttributeError(f"cannot set private attribute '{attr}' to class '{cls.__name__}'",
                                     name=attr,
                                     obj=cls)
            frame = frame.f_back
            caller_locals = frame.f_locals
            del frame
            caller_cls: type|None = caller_locals.get("cls", None)
            del caller_locals
            if caller_cls is not None and issubclass(caller_cls, cls):
                private_attr_name = _generate_private_attr_name(id(cls), attr)
                PrivateAttrType._type_attr_dict[id(cls)][private_attr_name] = value
                del caller_cls
            else:
                del caller_cls
                raise AttributeError(f"cannot set private attribute '{attr}' to class '{cls.__name__}'",
                                     name=attr,
                                     obj=cls)
        else:
            type.__setattr__(cls, attr, value)

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
        ]
        if attr in invalid_names:
            raise AttributeError(f"cannot delete '{attr}' attribute on class '{cls.__name__}'")
        if (hashlib.sha256(attr.encode("utf-8")).hexdigest(),
            hashlib.sha256(f"{id(cls)}_{attr}".encode("utf-8")).hexdigest()) in \
                PrivateAttrType._type_attr_dict[id(cls)][_generate_private_attr_name(id(cls), "__private_attrs__")]:
            frame = inspect.currentframe()
            if not PrivateAttrType._is_class_code(cls, frame):
                raise AttributeError(f"cannot delete private attribute '{attr}' on class '{cls.__name__}'",
                                     name=attr,
                                     obj=cls)
            frame = frame.f_back
            caller_locals = frame.f_locals
            del frame
            caller_cls: type|None = caller_locals.get("cls", None)
            del caller_locals
            if caller_cls is not None and issubclass(caller_cls, cls):
                private_attr_name = _generate_private_attr_name(id(cls), attr)
                try:
                    del PrivateAttrType._type_attr_dict[id(cls)][private_attr_name]
                except KeyError:
                    raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                         name=attr,
                                         obj=cls) from None
                finally:
                    del caller_cls
            else:
                del caller_cls
                raise AttributeError(f"cannot delete private attribute '{attr}' on class '{cls.__name__}'",
                                     name=attr,
                                     obj=cls)
        else:
            type.__delattr__(cls, attr)

    def __del__(cls):
        _clear_obj(id(cls))
        if id(cls) in PrivateAttrType._type_attr_dict:
            del PrivateAttrType._type_attr_dict[id(cls)]

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
