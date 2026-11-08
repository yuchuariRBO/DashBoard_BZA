#!/usr/bin/env python3
"""Bounded VM maintenance. Never traverse application or personal data."""

import argparse
import fcntl
import logging
from logging.handlers import WatchedFileHandler
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time


PROJECT = Path('/root/bonanza')
CACHE_ROOTS = (
    Path('/root/.cache/pip'),
    Path('/home/robiotec/.cache/pip'),
    Path('/root/.vscode-server/data/CachedExtensionVSIXs'),
    Path('/home/robiotec/.vscode-server/data/CachedExtensionVSIXs'),
)
CACHE_AGE_DAYS = 30
LOCK = Path('/run/bonanza-maintenance/cleanup.lock')
logger = logging.getLogger('bonanza.maintenance')


def clean_cache(directory, *, dry_run=False, now=None):
    """Delete old regular cache files; never follow directory or file symlinks."""
    directory = Path(directory)
    if not directory.exists() or directory.is_symlink():
        return 0, 0
    # Reject roots with symlink ancestors as well as a symlink root itself.
    if any(parent.is_symlink() for parent in directory.parents):
        raise ValueError(f'Cache path has a symlink ancestor: {directory}')
    cutoff = (time.time() if now is None else now) - CACHE_AGE_DAYS * 86400
    count = allocated = 0
    for base, directories, files in os.walk(directory, followlinks=False):
        directories[:] = [name for name in directories if not (Path(base) / name).is_symlink()]
        for name in files:
            path = Path(base) / name
            try:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_mtime >= cutoff:
                    continue
                if not dry_run:
                    path.unlink()
                count += 1
                allocated += info.st_blocks * 512
            except FileNotFoundError:
                # A cache producer may remove an entry concurrently.
                continue
    return count, allocated


def run_command(command, *, allowed_codes=(0,)):
    logger.info('Ejecutando: %s', ' '.join(command))
    result = subprocess.run(command, check=False, timeout=300)
    if result.returncode not in allowed_codes:
        raise RuntimeError(f'{command[0]} terminó con código {result.returncode}')
    if result.returncode == 3:
        logger.info('Logrotate ya está en ejecución; se conserva la ejecución existente.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Mostrar el alcance sin borrar archivos ni ejecutar limpieza.')
    options = parser.parse_args(argv)
    if os.geteuid() != 0 and not options.dry_run:
        parser.error('La ejecución real requiere root; usar el servicio systemd.')

    handlers = [logging.StreamHandler()]
    if not options.dry_run:
        destination = PROJECT / 'logs/maintenance/weekly-cleanup.log'
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o2750)
        handlers.append(WatchedFileHandler(destination, encoding='utf-8'))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', handlers=handlers)

    if options.dry_run:
        for directory in CACHE_ROOTS:
            count, allocated = clean_cache(directory, dry_run=True)
            logger.info('SIMULACIÓN caché=%s archivos=%s bytes=%s', directory, count, allocated)
        logger.info('SIMULACIÓN: apt-get clean; journal archivado máximo 14 días/300M; logrotate de Bonanza sin forzar.')
        logger.info('No se modificó ningún archivo.')
        return 0

    LOCK.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info('Ya hay una limpieza ejecutándose; se omite esta invocación.')
            return 0
        before = shutil.disk_usage(PROJECT).free
        failures = []
        logger.info('Inicio de limpieza semanal. Bytes libres=%s', before)
        actions = [
            ('paquetes descargados', lambda: run_command(['/usr/bin/apt-get', 'clean'])),
            ('journal archivado', lambda: run_command(['/usr/bin/journalctl', '--vacuum-time=14d', '--vacuum-size=300M'])),
            ('rotación de Bonanza', lambda: run_command(['/usr/sbin/logrotate', '/etc/logrotate.d/bonanza'], allowed_codes=(0, 3))),
        ]
        for directory in CACHE_ROOTS:
            def clean(directory=directory):
                count, allocated = clean_cache(directory)
                logger.info('Caché=%s archivos eliminados=%s bytes=%s', directory, count, allocated)
            actions.append((str(directory), clean))
        for name, action in actions:
            try:
                action()
            except Exception:
                failures.append(name)
                logger.exception('No se pudo completar: %s', name)
        after = shutil.disk_usage(PROJECT).free
        logger.info('Fin de limpieza. Bytes libres=%s diferencia=%s pasos fallidos=%s', after, after - before, len(failures))
        return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
