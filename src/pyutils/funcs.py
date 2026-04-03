import ast
import inspect
import re
from types import CodeType
from typing import *

from auto_all import public


@public
def get_anno_class(anno: inspect.Parameter):
    """ Gets the annotation class associated with a type annotation (if any). """
    return next(map(get_anno_class, getattr(anno, "__args__", [])), anno)


@public
def create_dummy_function(sig: Union[Callable, inspect.Signature], source_fname: Optional[str]=None, code_return: bool=False) -> Union[Callable[..., Any], CodeType]:
    """
    Creates a dummy function with the same signature as provided that just returns the arguments.
    """
    if isinstance(sig, Callable):
        source_fname = sig.__name__
        sig = inspect.signature(sig)
    else:
        assert source_fname is not None, "source_fname must be provided if sig is a Signature"

    # Construct the function definition string
    # This involves iterating through parameters to get names, defaults, and annotations
    param_names = []
    param_strings = []
    for param in sig.parameters.values():
        param_names.append(param.name)
        param_str = param.name
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            param_str += "/"
        elif param.kind == inspect.Parameter.VAR_POSITIONAL:
            param_str = f"*{param.name}"
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            param_str = f"**{param.name}"
        
        if param.annotation != inspect.Parameter.empty:
            param_str += f": {getattr(param.annotation, '__name__', str(param.annotation))}"
        if param.default != inspect.Parameter.empty:
            param_str += f" = {re.match(r'<?([^>]*)>?', repr(param.default)).group(1)}" # Use repr for accurate representation of default values
        
        param_strings.append(param_str)

    func_code = ast.parse(f"def {source_fname}_dummy_func({', '.join(param_strings)}):\n    return vars()\n")
 
    # Compile the AST into a code object
    code = compile(func_code, filename="<ast>", mode="exec")
    if code_return:
        return code

    while True:
        try:
            exec(code, globals())
            break
        except NameError as e:
            missing_name = re.search(r"name '(\S+)' is not defined", str(e)).group(1)
            raise e
            
    return globals()[f"{source_fname}_dummy_func"]


@public
def scripting_unit_conv(func: Callable[..., Any], *args, **kwargs) -> Any:
    """ Decorator to convert units for use in scripting environments """
    return create_dummy_function(func)(*args, **kwargs)
