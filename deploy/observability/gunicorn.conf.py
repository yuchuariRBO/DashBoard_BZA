"""Use only in the new, isolated deployment after explicit rollout approval.
Set PROMETHEUS_MULTIPROC_DIR in the launch environment, and empty it BEFORE start.
Never delete it while workers are running. Do not use --preload.
"""

from prometheus_client import multiprocess


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
