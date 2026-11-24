import threading

from app.imports.worker import ImportWorker


class Svc:
    def __init__(self, n):
        self.n = n
        self.done = threading.Event()
        self.boom = True

    def process_next(self):
        if self.boom:
            self.boom = False
            raise RuntimeError("inesperado")
        if self.n > 0:
            self.n -= 1
            return True
        self.done.set()
        return False


def test_worker_processes_until_empty_and_stops():
    svc, wake = Svc(3), threading.Event()
    w = ImportWorker(svc, wake, idle_s=0.01)
    w.start()
    assert svc.done.wait(5)
    w.stop()
    assert svc.n == 0
    assert not w._thread.is_alive()
