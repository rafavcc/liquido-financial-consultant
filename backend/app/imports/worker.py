"""Thread em segundo plano que drena a fila de importação."""

from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)


class ImportWorker:
    def __init__(self, service, wake: threading.Event, idle_s: float = 5.0) -> None:
        self._service, self._wake, self._idle = service, wake, idle_s
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._run, name="import-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        self._wake.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                if self._service.process_next():
                    continue
            except Exception:
                log.exception("Falha inesperada no worker de importação")
            self._wake.wait(self._idle)
            self._wake.clear()
