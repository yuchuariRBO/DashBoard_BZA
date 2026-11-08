"""ExecStartPre only: clear previous worker metric files before Gunicorn starts."""

from pathlib import Path

root = Path("/run/bonanza-metrics")
if root.is_symlink():
    raise RuntimeError("El directorio de métricas no debe ser un enlace.")
root.mkdir(mode=0o700, exist_ok=True)
for path in root.glob("*.db"):
    path.unlink()
