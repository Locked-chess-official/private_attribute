import random
import hashlib
import inspect
from typing import Any, Callable
import collections
import string
import threading


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


class PrivateAttrType(type):
    _type_attr_dict = {}

    def __new__(cls, name: str, bases: tuple[type], attrs: dict[str, Any]):
        type_slots = attrs.get("__slots__", ())
        if "__private_attrs__" not in attrs:
            raise TypeError("'__private_attrs__' is required in PrivateAttrType")
        private_attr_list = attrs.get('__private_attrs__', None)
        if not isinstance(private_attr_list, collections.abc.Sequence) or isinstance(private_attr_list, (str, bytes)):
            raise TypeError("'__private_attrs__' must be a sequence of the string")
        change = False
        for i in bases:
            if isinstance(i, cls):
                private_attr_list = private_attr_list + i.__private_attrs__
                change = True
        if change:
            attrs["__private_attrs__"] = tuple(set(private_attr_list))
        if "__private_attrs__" in private_attr_list:
            raise TypeError("'__private_attrs__' cannot contain '__private_attrs__' itself")
        need_update = []
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

        def __getattribute__(self, attr):
            if attr in private_attr_list:
                raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                     name=attr,
                                     obj=self)
            if original_getattribute:
                return original_getattribute(self, attr)
            for all_subtype in type_instance.__mro__[1:]:
                if hasattr(all_subtype, "__getattribute__"):
                    return all_subtype.__getattribute__(self, attr)
            raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                 name=attr,
                                 obj=self)

        def __getattr__(self, attr):
            if attr in private_attr_list:
                if id(self) not in obj_attr_dict:
                    obj_attr_dict[id(self)] = {}
                frame = inspect.currentframe()
                if not frame or not frame.f_back or frame.f_back.f_code.co_name == "<module>":
                    raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                         name=attr,
                                         obj=self)
                frame = frame.f_back
                caller_locals = frame.f_locals
                caller_self = caller_locals.get('self', None)
                if caller_self is not None and isinstance(caller_self, type_instance):
                    try:
                        private_attr_name = _generate_private_attr_name(id(self), attr)
                        return obj_attr_dict[id(self)][private_attr_name]
                    except KeyError:
                        private_attr_name = _generate_private_attr_name(id(type_instance), attr)
                        try:
                            return obj_attr_dict[id(self)][private_attr_name]
                        except KeyError:
                            raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                                 name=attr,
                                                 obj=self) from None
            if original_getattr:
                return original_getattr(self, attr)
            for all_subtype in type_instance.__mro__[1:]:
                if hasattr(all_subtype, "__getattr__"):
                    return all_subtype.__getattr__(self, attr)
            raise AttributeError(f"'{type_instance.__name__}' object has no attribute '{attr}'",
                                 name=attr,
                                 obj=self)

        def __setattr__(self, attr, value):
            if attr in private_attr_list:
                if id(self) not in obj_attr_dict:
                    obj_attr_dict[id(self)] = {}
                frame = inspect.currentframe()
                if not frame or not frame.f_back or frame.f_back.f_code.co_name == "<module>":
                    raise AttributeError(f"cannot set private attribute '{attr}' to '{type_instance.__name__}' object",
                                         name=attr,
                                         obj=self)
                frame = frame.f_back
                caller_locals = frame.f_locals
                caller_self = caller_locals.get('self', None)
                if caller_self is not None and isinstance(caller_self, type_instance):
                    private_attr_name = _generate_private_attr_name(id(self), attr)
                    obj_attr_dict[id(self)][private_attr_name] = value
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

        def __delattr__(self, attr):
            if attr in private_attr_list:
                if id(self) not in obj_attr_dict:
                    obj_attr_dict[id(self)] = {}
                frame = inspect.currentframe()
                if not frame or not frame.f_back or frame.f_back.f_code.co_name == "<module>":
                    raise AttributeError(
                        f"cannot delete private attribute '{attr}' on '{type_instance.__name__}' object",
                        name=attr,
                        obj=self)
                frame = frame.f_back
                caller_locals = frame.f_locals
                caller_self = caller_locals.get('self', None)
                if caller_self is not None and isinstance(caller_self, type_instance):
                    private_attr_name = _generate_private_attr_name(id(self), attr)
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
        type_instance = super().__new__(cls, name, bases, attrs)
        type_attr_dict[id(type_instance)] = {}
        for i in need_update:
            new_attr = _generate_private_attr_name(id(type_instance), i[0])
            type_attr_dict[id(type_instance)][new_attr] = i[1]
        return type_instance

    def __getattribute__(cls, attr):
        if attr == "__private_attrs__":
            return super().__getattribute__(attr)
        if hasattr(cls, "__private_attrs__") and attr in super().__getattribute__("__private_attrs__"):
            raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                 name=attr,
                                 obj=cls)
        return super().__getattribute__(attr)

    def __getattr__(cls, attr):
        if hasattr(cls, '__private_attrs__') and attr in cls.__private_attrs__:
            frame = inspect.currentframe()
            if not frame or not frame.f_back or frame.f_back.f_code.co_name == "<module>":
                raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                     name=attr,
                                     obj=cls)
            if id(cls) not in PrivateAttrType._type_attr_dict:
                PrivateAttrType._type_attr_dict[id(cls)] = {}
            frame = frame.f_back
            caller_locals = frame.f_locals
            caller_cls: type|None = caller_locals.get("cls", None)
            if caller_cls is not None and issubclass(caller_cls, cls):
                private_attr_name = _generate_private_attr_name(id(cls), attr)
                try:
                    return PrivateAttrType._type_attr_dict[id(cls)][private_attr_name]
                except KeyError:
                    raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                                         name=attr,
                                         obj=cls) from None
        raise AttributeError(f"'{cls.__name__}' class has no attribute '{attr}'",
                             name=attr,
                             obj=cls)

    def __setattr__(cls, attr, value):
        if hasattr(cls, '__private_attrs__') and attr in cls.__private_attrs__:
            frame = inspect.currentframe()
            if not frame or not frame.f_back or frame.f_back.f_code.co_name == "<module>":
                raise AttributeError(f"cannot set private attribute '{attr}' to class '{cls.__name__}'",
                                     name=attr,
                                     obj=cls)
            if id(cls) not in PrivateAttrType._type_attr_dict:
                PrivateAttrType._type_attr_dict[id(cls)] = {}
            frame = frame.f_back
            caller_locals = frame.f_locals
            caller_cls: type|None = caller_locals.get("cls", None)
            if caller_cls is not None and issubclass(caller_cls, cls):
                private_attr_name = _generate_private_attr_name(id(cls), attr)
                PrivateAttrType._type_attr_dict[id(cls)][private_attr_name] = value
            else:
                raise AttributeError(f"cannot set private attribute '{attr}' to class '{cls.__name__}'",
                                     name=attr,
                                     obj=cls)
        else:
            type.__setattr__(cls, attr, value)

    def __delattr__(cls, attr):
        if hasattr(cls, '__private_attrs__') and attr in cls.__private_attrs__:
            frame = inspect.currentframe()
            if not frame or not frame.f_back or frame.f_back.f_code.co_name == "<module>":
                raise AttributeError(f"cannot delete private attribute '{attr}' on class '{cls.__name__}'",
                                     name=attr,
                                     obj=cls)
            if id(cls) not in PrivateAttrType._type_attr_dict:
                PrivateAttrType._type_attr_dict[id(cls)] = {}
            frame = frame.f_back
            caller_locals = frame.f_locals
            caller_cls: type|None = caller_locals.get("cls", None)
            if caller_cls is not None and issubclass(caller_cls, cls):
                private_attr_name = _generate_private_attr_name(id(cls), attr)
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
        else:
            type.__delattr__(cls, attr)

    def __del__(cls):
        _clear_obj(id(cls))
        if id(cls) in PrivateAttrType._type_attr_dict:
            del PrivateAttrType._type_attr_dict[id(cls)]


class PrivateAttrBase(metaclass=PrivateAttrType):
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
