import inspect
import re

"""
enm-client-scripting private module: executionhandler

This is a private module and should not be used outside of the client-scripting module.
"""


def overrides(method):
    """
    Overrides decorator.

    Can be used to indicate that a function in a class overrides the superclass's function.

    @overrides
    def open_session(self):
    pass

    The assert runs when the class gets imported, so it does not have effect on the performance.
    Checks only of the existence of a super function, does not check its signature.
    """
    stack = inspect.stack()
    base_classes = re.search(r'class.+\((.+)\)\s*\:', stack[2][4][0]).group(1)

    # handle multiple inheritance
    base_classes = [s.strip() for s in base_classes.split(',')]
    # if not base_classes:
    #    raise ValueError('Overrides decorator: unable to determine base class')

    # stack[0]=overrides, stack[1]=inside class def'n, stack[2]=outside class def'n
    derived_class_locals = stack[2][0].f_locals

    # replace each class name in base_classes with the actual class type
    for i, base_class in enumerate(base_classes):
        if '.' not in base_class:
            base_classes[i] = derived_class_locals[base_class]
        # else:
        #    components = base_class.split('.')
        #    # obj is either a module or a class
        #    obj = derived_class_locals[components[0]]
        #    for c in components[1:]:
        #        assert(inspect.ismodule(obj) or inspect.isclass(obj))
        #        obj = getattr(obj, c)
        #    base_classes[i] = obj

    # for cls in base_classes:
        # print(str(cls))
        # print(str(dir(cls)))
        # print(inspect.getargspec(getattr(cls, method.__name__)))
        # print(inspect.getargspec(method))
    assert(any(hasattr(cls, method.__name__) for cls in base_classes))
    return method
