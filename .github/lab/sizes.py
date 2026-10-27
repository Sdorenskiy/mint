"""Размер установленных пакетов в venv: по каждому дистрибутиву (файлы из RECORD) и всего site-packages."""
import importlib.metadata as md
import os
import sys
from pathlib import Path

venv = Path(sys.argv[1])
site = next(venv.glob("lib/python*/site-packages"))
rows = []
for dist in md.distributions(path=[str(site)]):
    total = 0
    for f in dist.files or []:
        p = Path(dist.locate_file(f))
        try:
            total += p.stat().st_size
        except OSError:
            pass
    rows.append((total, dist.metadata["Name"], dist.version))
rows.sort(reverse=True)
all_bytes = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(site) for f in fs
                if os.path.exists(os.path.join(r, f)))
print(f"site_packages_bytes {all_bytes}")
print(f"packages {len(rows)}")
for size, name, ver in rows:
    print(f"{size / 1e6:8.1f} MB  {name}=={ver}")
