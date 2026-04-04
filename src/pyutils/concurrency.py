import concurrent.futures as cf
import inspect
import multiprocessing.pool as mp
import os
from functools import partial, wraps
from typing import Any, Callable, Dict, Optional, Tuple

from auto_all import public

from pyutils.decorators import redirect_output, wrap_once
from pyutils.funcs import get_anno_class


@public
def get_concurrency_executor(*args, max_threads: int, **kwargs) -> Callable[..., cf.Executor]:
    """ Get a concurrency executor (`concurrent.futures.executor`) for the current function, using the specified number of maximum threads.  
        Uses a `ProcessPoolExecutor` if multiprocessing is allowed by `max_threads`, otherwise, uses `ThreadPoolExecutor`.
    """
    return partial((cf.ThreadPoolExecutor if max_threads == 1 else cf.ProcessPoolExecutor), max_workers=(max_threads if max_threads > 1 else int(os.getenv("MAX_THREADS", 4))))


@public
@wrap_once
def max_threads(func: Callable[..., Any]) -> Callable[..., Any]:
    """ Decorator to set the maximum number of threads for a function.  
        Prevents nested multithreading by setting MAX_THREADS to 1 if the function is called within another function.  
    """
    f_name = func.__qualname__

    @wraps(func)
    @redirect_output
    def thread_wrapper(*args, multithread: bool=True, **kwargs):
        if multithread:
            max_threads = kwargs.get("max_threads", globals().get("MAX_THREADS", int(os.getenv("MAX_THREADS", 4))))
            for _ in filter(lambda f: any(map(lambda v: isinstance(v, (mp.Pool, cf.Executor)), f.frame.f_locals.values())), inspect.stack()):
                print("Found nested multithreading, setting max_threads to 1")
                max_threads = 1
                break

            print(f"Using {max_threads=} for {f_name}")
        else:
            max_threads = 1
        
        return func(*args, max_threads=max_threads, **kwargs)
    return thread_wrapper


@public
@wrap_once
def concurrency(func: Callable[..., Any]) -> Callable[..., Any]:
    """ Decorator to pass a `current.futures.executor` object to the called function based on the specified number of maximum threads.
        Uses a `ProcessPoolExecutor` if multiprocessing is allowed by `max_threads`, otherwise, uses `ThreadPoolExecutor`.
    """
    sig = inspect.signature(func)
    executor_arg = next(map(lambda p: p[0], filter(lambda p: issubclass(get_anno_class(p[1].annotation), cf.Executor), sig.parameters.items())), "executor") 

    @max_threads
    @wraps(func)
    def concurrency_wrapper(*args, max_threads: int, executor: Optional[cf.Executor]=None, **kwargs):
        if executor is None:
            # with get_concurrency_executor(max_threads=max_threads)() as executor:
            with cf.ProcessPoolExecutor(max_workers=max_threads) as executor:
                fkwargs = kwargs.copy()
                fkwargs.update({executor_arg: executor})
                return func(*args, **fkwargs)
        else:
            return func(*args, executor=executor, **kwargs)
    
    return concurrency_wrapper


@public
def apply_with_kwargs(f: Callable[..., Any], args: Tuple[Any], kwargs: Dict[Any, Any]) -> Any:
    """ Calls a function `f` with the given `args` and `kwargs` """
    return f(*args, **kwargs)
