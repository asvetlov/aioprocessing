import asyncio

from .executor import _AioExecutorMixin, CoroBuilder
from  multiprocessing import (Event, Lock, RLock, BoundedSemaphore,
                                          Condition, Semaphore, Barrier)
from multiprocessing.util import register_after_fork

__all__ = ["AioLock", "AioRLock", "AioBarrier", "AioCondition", "AioEvent",
           "AioSemaphore", "AioBoundedSemaphore"]


class _ContextManager:
    """ Context manager.

    This enables the following idiom for acquiring and releasing a
    lock around a block:

        with (yield from lock):
            <block>

    """

    def __init__(self, lock):
        self._lock = lock

    def __enter__(self):
        # We have no use for the "as ..."  clause in the with
        # statement for locks.
        return None

    def __exit__(self, *args):
        try:
            self._lock.release()
        finally:
            self._lock = None  # Crudely prevent reuse.


class AioBaseLock(metaclass=CoroBuilder):
    pool_workers = 1
    coroutines = ['acquire', 'release']
    def __init__(self, *args, **kwargs):
        self._threaded_acquire = False
        def _after_fork(obj):
            obj._threaded_acquire = False
        register_after_fork(self, _after_fork)

    def coro_acquire(self, *args, **kwargs):
        def lock_acquired(fut):
            if fut.result():
                self._threaded_acquire = True

        out = self.run_in_executor(self._obj.acquire, *args, **kwargs)
        out.add_done_callback(lock_acquired)
        return out

    def __getstate__(self):
        state = super().__getstate__()
        state['_threaded_acquire'] = False
        return state

    def __setstate__(self, state):
        super().__setstate__(state)

    def release(self):
        """ Release the lock.
        
        If the lock was acquired in the same process via
        coro_acquire, we need to release the lock in the
        ThreadPoolExecutor's thread.
        
        """
        if self._threaded_acquire:
            out = self.run_in_thread(self._obj.release)
        else:
            out = self._obj.release()
        self._threaded_acquire = False
        return out

    def __enter__(self):
        self._obj.__enter__()

    def __exit__(self, *args, **kwargs):
        self._obj.__exit__(*args, **kwargs)

    def __iter__(self):
        yield from self.coro_acquire()
        return _ContextManager(self)


class AioBaseWaiter(metaclass=CoroBuilder):
    pool_workers = 1
    coroutines = ['wait']


class AioBarrier(AioBaseWaiter):
    delegate = Barrier
    pass


class AioCondition(AioBaseLock, AioBaseWaiter):
    delegate = Condition
    pool_workers = 1
    coroutines = ['wait_for', 'notify', 'notify_all']


class AioEvent(AioBaseWaiter):
    delegate = Event


class AioLock(AioBaseLock):
    delegate = Lock


class AioRLock(AioBaseLock):
    delegate = RLock


class AioSemaphore(AioBaseLock):
    delegate = Semaphore


class AioBoundedSemaphore(AioBaseLock):
    delegate = BoundedSemaphore


