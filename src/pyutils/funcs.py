import inspect

from auto_all import public


@public
def get_anno_class(anno: inspect.Parameter):
    """ Gets the annotation class associated with a type annotation (if any). """
    return next(map(get_anno_class, getattr(anno, "__args__", [])), anno)
