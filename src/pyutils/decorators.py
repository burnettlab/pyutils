""" Utility Decorators """
import ast
import datetime
import gc
import inspect
import os
import pickle
import re
import sys
from contextlib import redirect_stdout
from copy import deepcopy
from functools import partial, wraps
from itertools import chain
from pathlib import Path
from types import CodeType
from typing import *

from auto_all import public


@public
def update_signature_from_partial(f_partial: partial) -> partial:
    """Updates the __signature__ of a partial object to reflect its actual call signature."""
    # Get the signature of the original function
    original_sig = inspect.signature(f_partial.func)
    
    # Bind the pre-defined args and kwargs to the original signature
    # This identifies which parameters have been satisfied
    bound_args = original_sig.bind_partial(*f_partial.args, **dict(chain.from_iterable(map(lambda it: ([(it[0], {})] + list(it[1].items())) if isinstance(it[1], dict) else (it,), f_partial.keywords.items()))))
    
    # Get the parameters that are left unbound
    remaining_params = []
    for name, param in original_sig.parameters.items():
        if name not in list(bound_args.kwargs.keys()) + list(bound_args.arguments.keys()):
            # Create a new parameter for the remaining ones
            new_param = param.replace(default=param.default) # Retain default values if any
            remaining_params.append(new_param)
            
    # Create a new signature with only the remaining parameters
    new_sig = inspect.Signature(remaining_params, return_annotation=original_sig.return_annotation)
    
    # Assign the new signature to the partial function object
    f_partial.__signature__ = new_sig   # type: ignore
    return f_partial


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


@public
def wrap_once(wrapper_func: Callable[..., Any]) -> Callable[..., Any]:
    """ Decorator to ensure a function is only wrapped once per wrapper. """ 
    @wraps(wrapper_func)
    def wrap_once_wrapper(*args, **kwargs):
        # If called as a decorator-factory (e.g. @decorator(arg=...)), the first call
        # will not receive the function to wrap as the first positional arg.
        if not args or not callable(args[0]):
            return wrapper_func(*args, **kwargs)  # produce the actual decorator
        
        # Called directly as a plain decorator: first arg is the function to wrap
        wrapped_func = args[0]
        if wrapper_func.__name__ in getattr(wrapped_func, "_wrapped_by_", set()):
            return wrapped_func
        setattr(wrapped_func, "_wrapped_by_", getattr(wrapped_func, "_wrapped_by_", set()) | {wrapper_func.__name__})
        return wrapper_func(wrapped_func, *args[1:], **kwargs)

    return wrap_once_wrapper


@public
@wrap_once
def save_state(func: Callable[..., Any]) -> Callable[..., Any]:
    """ Decorator to save and restore the state of the object. """    
    @wraps(func)
    def save_state_wrapper(*args, **kwargs):
        obj = deepcopy(args[0])
        return func(obj, *args[1:], **kwargs)
    return save_state_wrapper


@public
@wrap_once
def DetailedError(func: Callable[..., Any]) -> Callable[..., Any]:
    """ Decorator to catch and print detailed errors in a function. """
    f_name = re.search(r'function (\S+) at', str(func)).group(1)
    @wraps(func)
    def error_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            funcname_iter = map(lambda f: f.function, inspect.stack())
            test_fname = next(funcname_iter)
            if all(f != test_fname for f in funcname_iter):
                traceback_frames = inspect.getinnerframes(exc_traceback)
                for frame in traceback_frames:
                    print(f"File: {frame.filename}, Line: {frame.lineno}, Function: {frame.function}")
                    print(f"  Code: {frame.code_context[0].strip() if frame.code_context else 'No code context'}")
                    print(f"  Local variables: {dict(filter(lambda e: not e[0].startswith('_'), frame.frame.f_locals.items()))}")
                if hasattr(e, 'args'):
                    print(f"Exception args: {e.args}")
            raise e
    return error_wrapper


@public
@wrap_once
def pickle_output(func: Optional[Callable[..., Any]]=None, *, date_format: str="%Y%m%d_%H%M%S") -> Callable[..., Any]:
    """ Decorator to enable pickling of the output of a function.  
        Loads the function's output from a file if it exists, otherwise calls the function and saves the output to a file.
    """
    if func is None:
        return partial(func, date_format=date_format)
    
    fname = getattr(func, "__qualname__", getattr(func, "__name__", type(func)))
    
    @wraps(func)
    @DetailedError
    def pickle_wrapper(*args, force_run: bool=False, check_time: bool=True, **kwargs):
        inspect_f = inspect.unwrap(func)
        func_data_path = Path("data", f"{fname}")
        func_data_path.mkdir(parents=True, exist_ok=True)
        func_pkls = filter(lambda p: p.suffix == ".pkl" and p.stem.endswith("_input"), func_data_path.iterdir())

        running = force_run
        res = None
        while True:
            # Check to see if there are any pickled inputs
            try:
                f_input = next(func_pkls)
            except StopIteration:
                running |= True
                break

            if check_time:
                # Skip if the pickled input is older than the file containing the function
                mod_time = datetime.datetime.fromtimestamp(Path(inspect.getfile(inspect_f)).stat().st_mtime)
                pkl_time = datetime.datetime.strptime('_'.join(f_input.stem.split("_")[:-1]), date_format)
                if pkl_time < mod_time:
                    continue

            # Load the input arguments and check if they match the current function call
            with open(f_input, "rb") as f_in:
                input_args, input_kwargs = pickle.load(f_in)

            if len(input_args) == len(args) and len(input_kwargs) == len(kwargs):               
                if all(compare_args(*args) for args in zip(input_args, args)) and all(k in input_kwargs and compare_args(input_kwargs[k], v) for k, v in kwargs.items()):
                    f_output = Path(f_input.parent, f"{f_input.stem.replace('_input', '_output')}.pkl")
                    assert f_output.exists(), f"Output file {f_output} does not exist for input {f_input}"
                    print(f"Loading previous output for {fname} from {f_output}")
                    with open(f_output, "rb") as f_out:
                        res = pickle.load(f_out)
                    running = False
                    break

        if running:
            res = func(*args, **kwargs)
            assert res is not None, "Function must return a value"
            gc.collect()  # Ensure memory is cleared before saving
            with open(func_data_path / f"{datetime.datetime.now().strftime(date_format)}_input.pkl", "wb") as f_in:
                pickle.dump((args, kwargs), f_in)

            with open(func_data_path / f"{datetime.datetime.now().strftime(date_format)}_output.pkl", "wb") as f_out:
                pickle.dump(res, f_out)

        return res

    return pickle_wrapper


@public
@wrap_once
def redirect_output(func: Optional[Callable[..., Any]]=None, *, blocked: bool=False) -> Callable[..., Any]:
    """ Decorator to redirect the output of a function to /dev/null if it is called within another function of the same name.  
        E.g This function decorates CircuitSizing.circuit_sizing, so any function wrapped by that decorator will have its output suppressed if called by a function also wrapped by that decorator.  
        Can override with blocked=True.
    """
    if func is None:
        return partial(redirect_output, blocked=blocked)

    @wraps(func)
    def redirect_wrapper(*args, verbose: bool=False, **kwargs):
        if not blocked and (verbose or all(f.function != func.__name__ for f in inspect.stack())):
            result = func(*args, verbose=verbose, **kwargs)
        else:
            std_out = os.devnull
            std_err = os.devnull
            with open(str(std_out), 'w') as o, redirect_stdout(o), open(str(std_err), 'w') as e, redirect_stdout(e):
                result = func(*args, **kwargs)
        return result
    return redirect_wrapper
