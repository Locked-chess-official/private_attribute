# Private Attribute

## Introduction

This package provide a way to create the private attribute like "C++" does.

## Usage

This is a simple usage about the module:

```python
from private_attribute import PrivateAttrBase

class MyClass(PrivateAttrBase):
    __private_attrs__ = ['a', 'b', 'c']
    def __init__(self):
        self.a = 1
        self.b = 2
        self.c = 3

    def public_way(self):
        print(self.a, self.b, self.c)

obj = MyClass()
obj.public_way()  # (1, 2, 3)

print(hasattr(obj, 'a'))  # False
print(hasattr(obj, 'b'))  # False
print(hasattr(obj, 'c'))  # False
```

All of the attributes in `__private_attrs__` will be hidden from the outside world, and stored by another name.

You can use your function to generate the name. It needs the id of the obj and the name of the attribute:

```python
def my_generate_func(obj_id, attr_name):
    return some_string

class MyClass(PrivateAttrBase, private_func=my_generate_func):
    __private_attrs__ = ['a', 'b', 'c']
    def __init__(self):
        self.a = 1
        self.b = 2
        self.c = 3

    def public_way(self):
        print(self.a, self.b, self.c)

obj = MyClass()
obj.public_way()  # (1, 2, 3)

```

If the method will be decorated, the `property`, `classmethod` and `staticmethod` will be supported.
For the other, you can use the `PrivateWrapProxy` to wrap the function:

```python
from private_attribute import PrivateAttrBase, PrivateWrapProxy

class MyClass(PrivateAttrBase):
    __private_attrs__ = ['a', 'b', 'c']
    @PrivateWrapProxy(decorator1())
    @PrivateWrapProxy(decorator2())
    def method1(self):
        ...

    @method1.attr_name
    def method1(self):
        ...

    @PrivateWrapProxy(decorator3())
    def method2(self):
        ...

    @method2.attr_name
    def method2(self):
        ...


```

## Notes

- All of the private attributes class must contain the `__private_attrs__` attribute.
- The `__private_attrs__` attribute must be a sequence of strings.
- You cannot define the name which in `__slots__` to `__private_attrs__`.
- When you define `__slots__` and `__private_attrs__` in one class, the attributes in `__private_attrs__` can also be defined in the methods, even though they are not in `__slots__`.
- All of the object that is the instance of the class "PrivateAttrBase" or its subclass are default to be unable to be pickled.
- Finally the attributes' names in `__private_attrs__` will be change to a tuple with two hash.

## License

MIT
