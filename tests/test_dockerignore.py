"""The Docker build context is an ALLOWLIST, and a real record can never enter it.

`docker build` ships the whole folder to the daemon, and this folder is where a real
install keeps health.db, the imaging and document stores, the audit log and backups.
.dockerignore therefore excludes everything and re-includes only code. This test reads
the file and evaluates it with Docker's rule (patterns in order, last match wins, a
leading `!` re-includes), so a future edit that widens it to a folder holding data, or
that turns it into a denylist, fails here rather than as a medical record in an image
layer.
"""
import fnmatch
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# One path of every shape a real record takes, plus near-misses a widened pattern catches.
DATA = [
    "health.db", "health.db-wal", "health.db-shm", "health.db.bak-20260715-122548",
    "imaging_store/cd1/IM000001", "imaging_store/.scan-cache.json",
    "imaging_archive/cd1/other_content/1/report.txt",
    "documents_store/manifest.json", "documents_store/doc.pdf",
    "gateway_audit.log", "gateway_audit.log.pre-trim",
    ".sweep/metrics.json", ".env.local", "frontend/.env.local",
    "demo_store/demo.db", "frontend/health.db", "static-demo/api/metrics.json",
]

# What the images genuinely need, so an over-tight edit fails too.
CODE = [
    "api.py", "db.py", "schema.sql", "requirements.txt",
    "frontend/package.json", "frontend/package-lock.json", "frontend/index.html",
    "frontend/vite.config.js", "frontend/src/main.jsx", "frontend/public/favicon.svg",
    "docker/nginx.conf",
]


def _patterns():
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _matches(pattern, path):
    pattern = pattern.rstrip("/")
    if pattern.startswith("**/"):
        tail = pattern[3:]
        parts = path.split("/")
        return any(_matches(tail, "/".join(parts[i:])) for i in range(len(parts)))
    parts = path.split("/")
    # A pattern names a path or any folder above it (excluding a folder excludes its contents).
    return any(fnmatch.fnmatchcase("/".join(parts[:i]), pattern) for i in range(1, len(parts) + 1))


def _included(path):
    included = True
    for p in _patterns():
        negate = p.startswith("!")
        if _matches(p[1:] if negate else p, path):
            included = negate
    return included


def test_it_starts_by_excluding_everything():
    assert _patterns()[0] == "*", "the .dockerignore must be an allowlist: '*' first"


def test_no_real_data_path_enters_the_build_context():
    leaked = [p for p in DATA if _included(p)]
    assert not leaked, f"data paths would be sent to the Docker daemon: {leaked}"


def test_the_code_the_images_need_is_included():
    missing = [p for p in CODE if not _included(p)]
    assert not missing, f"needed by the Dockerfile but excluded: {missing}"
