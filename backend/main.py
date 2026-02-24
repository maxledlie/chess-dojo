import asyncio
import uuid

import uvicorn
from api.app import create_app
from matchmaking.daemon import main as daemon_main
from multiprocessing import Process
import structlog

logger = structlog.get_logger()

GRACEFUL_SHUTDOWN_TIMEOUT = 10


def api_main():
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


def mm_daemon_main():
    daemon_id = f"mm-{uuid.uuid4().hex[:8]}"
    asyncio.run(daemon_main(daemon_id))


if __name__ == "__main__":
    api_p = Process(target=api_main, name="api")
    mm_p = Process(target=mm_daemon_main, name="matchmaker")

    procs = [api_p, mm_p]
    for proc in procs:
        proc.start()

    try:
        # Keep parent process alive.
        # If any process dies, shut down the rest
        shutdown = False
        while not shutdown:
            for proc in procs:
                if not proc.is_alive():
                    logger.error(f"Process {proc.name} died")
                    shutdown = True

    except KeyboardInterrupt:
        pass

    finally:
        # Request graceful shutdown (SIGINT)
        for proc in procs:
            if proc.is_alive():
                proc.terminate()

        # Wait for graceful shutdown
        for proc in procs:
            proc.join(timeout=GRACEFUL_SHUTDOWN_TIMEOUT)

        # Force terminate processes
        for proc in procs:
            proc.kill()
