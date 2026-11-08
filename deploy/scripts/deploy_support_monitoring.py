#!/usr/bin/env python3
"""Authorized production rollout for this VM; creates private backups first.

Run as root after the hermetic test suite. No credential is printed. Native
binaries must already exist in --binary-cache (verified releases documented).
"""

import argparse
import grp
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/bonanza")
PYTHON = ROOT / "venv/bin/python"
DEPLOY = ROOT / "deploy/observability"
PRODUCTION = DEPLOY / "production"
CONFIG = Path("/etc/bonanza-observability")
DATA = Path("/var/lib/bonanza-observability")


def run(*args, cwd=ROOT):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def django(*args):
    run(PYTHON, ROOT / "inventario_bonanza/manage.py", *args)


def copy(source, target, mode=0o644):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(mode)


def environment_update(path, values):
    lines = path.read_text().splitlines()
    result = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in values:
            continue
        result.append(line)
    result.extend(f"{key}={value}" for key, value in values.items())
    path.write_text("\n".join(result) + "\n")
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary-cache",
        type=Path,
        default=Path("/home/robiotec/.cache/bonanza-observability"),
    )
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error(
            "Se requiere root para servicios, configuración y respaldo privado."
        )
    os.umask(0o077)
    os.chdir(ROOT)
    cache = args.binary_cache
    sources = {
        "prometheus": cache / "prometheus-3.16.0.linux-amd64",
        "grafana": cache / "grafana-13.3.0",
        "alertmanager": cache / "alertmanager-0.34.2.linux-amd64",
    }
    for name, path in sources.items():
        executable = path / ("bin/grafana" if name == "grafana" else name)
        if not executable.is_file():
            raise RuntimeError(f"Falta el binario previamente validado: {name}")
    # Read the configured database name without exposing environment credentials.
    import sys

    sys.path.insert(0, str(ROOT / "inventario_bonanza"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "inventario_bonanza.settings")
    import django as django_module

    django_module.setup()
    from django.conf import settings

    db = settings.DATABASES["default"]
    if db["ENGINE"] != "django.db.backends.sqlite3":
        raise RuntimeError("Este despliegue requiere el motor SQLite revisado.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path("/var/backups/bonanza") / f"support-monitoring-{timestamp}"
    backup.mkdir(parents=True, mode=0o700)
    with (
        sqlite3.connect(f"file:{db['NAME']}?mode=ro", uri=True) as source,
        sqlite3.connect(backup / "database.sqlite3") as destination,
    ):
        source.backup(destination, pages=512, sleep=0.05)
        if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("El respaldo SQLite no superó quick_check.")
    for source, label in [
        (ROOT / ".env", "environment"),
        (Path("/etc/nginx/sites-available/bonanza"), "nginx-site"),
    ]:
        copy(source, backup / label, 0o600)
    dropins = Path("/etc/systemd/system/bonanza-gunicorn.service.d")
    shutil.copytree(dropins, backup / "gunicorn-dropins")
    with (backup / "source-diff.patch").open("w") as output:
        subprocess.run(
            ["git", "-c", f"safe.directory={ROOT}", "diff", "--binary"],
            cwd=ROOT,
            stdout=output,
            check=True,
        )
    print(f"Respaldo SQLite/configuración verificado: {backup}", flush=True)
    if subprocess.run(
        ["id", "bonanza-monitor"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode:
        run(
            "useradd",
            "--system",
            "--home-dir",
            str(DATA),
            "--shell",
            "/usr/sbin/nologin",
            "bonanza-monitor",
        )
    account = __import__("pwd").getpwnam("bonanza-monitor")
    gid = grp.getgrnam("bonanza-monitor").gr_gid
    CONFIG.mkdir(mode=0o750, exist_ok=True)
    CONFIG.chmod(0o750)
    os.chown(CONFIG, 0, gid)
    binary_root = Path("/opt/bonanza-observability")
    binary_root.mkdir(parents=True, exist_ok=True)
    binary_root.chmod(0o755)
    for name in ("prometheus", "grafana", "alertmanager"):
        target = Path("/opt/bonanza-observability") / name
        shutil.copytree(sources[name], target, dirs_exist_ok=True)
        for path in [target, *target.rglob("*")]:
            if path.is_symlink():
                continue
            os.chown(path, 0, 0)
            path.chmod(0o755 if path.is_dir() or os.access(path, os.X_OK) else 0o644)
        folder = DATA / name
        folder.mkdir(parents=True, exist_ok=True)
        for path in [DATA, folder]:
            os.chown(path, account.pw_uid, gid)
            path.chmod(0o750)
    logs = Path("/var/log/bonanza-observability/grafana")
    logs.mkdir(parents=True, exist_ok=True)
    os.chown(logs.parent, account.pw_uid, gid)
    logs.parent.chmod(0o750)
    os.chown(logs, account.pw_uid, gid)
    logs.chmod(0o750)
    private = Path("/var/lib/bonanza-support")
    private.mkdir(mode=0o700, exist_ok=True)
    private.chmod(0o700)
    token = settings.MONITOR_METRICS_TOKEN or secrets.token_urlsafe(48)
    tokenfile = CONFIG / "metrics-token"
    tokenfile.write_text(token)
    tokenfile.chmod(0o640)
    os.chown(tokenfile, 0, gid)
    secret = CONFIG / "grafana-admin-password"
    if not secret.exists():
        secret.write_text(secrets.token_urlsafe(48))
    secret.chmod(0o640)
    os.chown(secret, 0, gid)
    values = {
        "SUPPORT_PRIVATE_ROOT": str(private),
        "MONITOR_METRICS_TOKEN": token,
        "PROMETHEUS_URL": "http://127.0.0.1:19090",
        "GRAFANA_URL": "https://bonanza.robio-ai.com/grafana",
        "OBSERVABILITY_ENABLED": "True",
        "MONITOR_SERVICE_PROBES": json.dumps(
            {"minio": "http://127.0.0.1:9000/minio/health/live"}
        ),
    }
    environment_update(ROOT / ".env", values)
    for source, target in [
        (PRODUCTION / "prometheus.yml", "prometheus.yml"),
        (PRODUCTION / "grafana.ini", "grafana.ini"),
        (DEPLOY / "prometheus/alerts.yml", "alerts.yml"),
        (DEPLOY / "alertmanager.yml", "alertmanager.yml"),
    ]:
        copy(source, CONFIG / target)
    shutil.copytree(
        DEPLOY / "grafana/provisioning", CONFIG / "provisioning", dirs_exist_ok=True
    )
    shutil.copytree(DEPLOY / "dashboards", CONFIG / "dashboards", dirs_exist_ok=True)
    provider = CONFIG / "provisioning/dashboards/bonanza.yaml"
    provider.write_text(
        provider.read_text().replace(
            "/var/lib/grafana/dashboards", str(CONFIG / "dashboards")
        )
    )
    for path in (CONFIG / "provisioning").rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    for path in (CONFIG / "dashboards").rglob("*"):
        path.chmod(0o644)
    # Directories created with the private umask must remain readable to the daemon.
    for folder in [CONFIG / "provisioning", CONFIG / "dashboards"]:
        folder.chmod(0o755)
    for path in PRODUCTION.glob("*.service"):
        copy(path, Path("/etc/systemd/system") / path.name)
    for path in PRODUCTION.glob("*.timer"):
        copy(path, Path("/etc/systemd/system") / path.name)
    copy(PRODUCTION / "gunicorn-observability.conf", dropins / "observability.conf")
    copy(
        PRODUCTION / "nginx.conf",
        Path("/etc/nginx/snippets/bonanza-observability.conf"),
    )
    site = Path("/etc/nginx/sites-available/bonanza")
    include = "    include /etc/nginx/snippets/bonanza-observability.conf;\n"
    source = site.read_text()
    if include.strip() not in source:
        marker = "    location /static/ {"
        if marker not in source:
            raise RuntimeError(
                "Revisar ubicación del include Nginx; no coincide con la plantilla de esta VM."
            )
        site.write_text(source.replace(marker, include + "\n" + marker, 1))
        site.chmod(0o644)
    run(
        "/opt/bonanza-observability/prometheus/promtool",
        "check",
        "config",
        CONFIG / "prometheus.yml",
    )
    run(
        "/opt/bonanza-observability/alertmanager/amtool",
        "check-config",
        CONFIG / "alertmanager.yml",
    )
    for filename in (
        "prometheus.yml",
        "grafana.ini",
        "alertmanager.yml",
        "metrics-token",
        "grafana-admin-password",
    ):
        run("runuser", "-u", "bonanza-monitor", "--", "test", "-r", CONFIG / filename)
    run("nginx", "-t")
    run("systemctl", "daemon-reload")
    django("check")
    # Brief application maintenance; unrelated MinIO/queue services remain running.
    run("systemctl", "stop", "bonanza-gunicorn")
    try:
        django("migrate", "--noinput")
        django("collectstatic", "--noinput")
    finally:
        run("systemctl", "start", "bonanza-gunicorn")
    run(
        "systemctl",
        "enable",
        "--now",
        "bonanza-alertmanager",
        "bonanza-prometheus",
        "bonanza-grafana",
        "bonanza-monitoring-sample.timer",
    )
    run("systemctl", "reload", "nginx")
    run("systemctl", "start", "bonanza-monitoring-sample.service")
    run(
        "systemctl",
        "is-active",
        "bonanza-gunicorn",
        "nginx",
        "minio",
        "bonanza-prometheus",
        "bonanza-grafana",
        "bonanza-alertmanager",
    )
    import time
    import urllib.request

    for port, path in [
        (19090, "/-/ready"),
        (13000, "/api/health"),
        (19093, "/-/ready"),
    ]:
        deadline = time.monotonic() + 20
        while True:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}{path}", timeout=2
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"El servicio en {port} no está listo; revisar journalctl."
                )
            time.sleep(0.5)
    print(
        "Despliegue aplicado. Verificar HTTPS, permisos, Grafana y métricas antes de darlo por finalizado.",
        flush=True,
    )


if __name__ == "__main__":
    main()
