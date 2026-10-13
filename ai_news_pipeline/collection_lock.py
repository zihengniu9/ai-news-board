"""Cross-process lock shared by scheduled and browser-triggered collectors (Windows and Linux)."""
import os
from contextlib import contextmanager
from .runtime import data_root


@contextmanager
def collection_lock():
    root=data_root();root.mkdir(parents=True,exist_ok=True)
    with (root/'collection.lock').open('a+b') as f:
        f.seek(0,2)
        if f.tell()==0:f.write(b'0');f.flush()
        f.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('已有采集任务运行，本次未重复启动') from None
            try:yield
            finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError('已有采集任务运行，本次未重复启动') from None
            try:yield
            finally:fcntl.flock(f.fileno(),fcntl.LOCK_UN)
