#!/usr/bin/env python3
"""Build and optionally compile-check the minimal arXiv source bundle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile


MANUSCRIPT = Path(__file__).resolve().parent
OUTPUT = MANUSCRIPT / "output" / "arxiv"
STAGING = OUTPUT / "source"
ARCHIVE = OUTPUT / "qwen3-coreai-report-arxiv.tar.gz"
MAIN_FILE = "qwen3-coreai-report.tex"
SOURCE_FILES = {
    MAIN_FILE: MANUSCRIPT / MAIN_FILE,
    "references.bib": MANUSCRIPT / "references.bib",
    **{
        f"generated/tables/{path.name}": path
        for path in sorted((MANUSCRIPT / "generated" / "tables").glob("t*.tex"))
    },
    **{
        f"generated/figures/{path.name}": path
        for path in sorted((MANUSCRIPT / "generated" / "figures").glob("f*.pdf"))
    },
}
EXPECTED_INPUTS = {
    MAIN_FILE,
    "references.bib",
    *(f"generated/tables/t{i}-{name}.tex" for i, name in (
        (1, "public-status"),
        (2, "profile-definitions"),
        (3, "w8-fidelity"),
        (4, "w8-device-evidence"),
        (5, "paired-quality"),
        (6, "size-rss"),
        (7, "workload-performance"),
        (8, "w8-compatibility"),
    )),
    *(f"generated/figures/f{i}-{name}.pdf" for i, name in (
        (1, "static-pipeline"),
        (2, "profile-comparison"),
        (3, "paired-quality"),
        (4, "workload-latency"),
        (5, "size-rss"),
    )),
}
README = """arXiv source bundle for Deploying Qwen3-1.7B on iPhone with Apple Core AI

Main TeX file: qwen3-coreai-report.tex
Bibliography: references.bib
Local verification engine: Tectonic 0.17.0

Upload the extracted contents of this directory, not the surrounding Git
repository. The generated/ paths are intentional and match the relative paths
used by the manuscript. No shell escape or external data download is required.
"""


class PackageError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_staging() -> None:
    if set(SOURCE_FILES) != EXPECTED_INPUTS:
        raise PackageError(
            "arXiv input inventory drift: "
            f"unexpected={sorted(set(SOURCE_FILES) - EXPECTED_INPUTS)}, "
            f"missing={sorted(EXPECTED_INPUTS - set(SOURCE_FILES))}"
        )
    missing = [relative for relative, source in SOURCE_FILES.items() if not source.is_file()]
    if missing:
        raise PackageError(f"missing arXiv inputs: {', '.join(sorted(missing))}")

    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    for relative, source in sorted(SOURCE_FILES.items()):
        destination = STAGING / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (STAGING / "00README.txt").write_text(README, encoding="utf-8")

    manifest_paths = [
        path for path in sorted(STAGING.rglob("*")) if path.is_file()
    ]
    (STAGING / "MANIFEST.sha256").write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(STAGING).as_posix()}\n"
            for path in manifest_paths
        ),
        encoding="utf-8",
    )

    actual = {
        path.relative_to(STAGING).as_posix()
        for path in STAGING.rglob("*")
        if path.is_file()
    }
    expected = EXPECTED_INPUTS | {"00README.txt", "MANIFEST.sha256"}
    if actual != expected:
        raise PackageError(
            "staged arXiv inventory drift: "
            f"unexpected={sorted(actual - expected)}, missing={sorted(expected - actual)}"
        )


def write_archive() -> None:
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with ARCHIVE.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for path in sorted(STAGING.rglob("*")):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(STAGING).as_posix()
                    info = archive.gettarinfo(str(path), arcname=relative)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mode = 0o644
                    info.mtime = 0
                    with path.open("rb") as handle:
                        archive.addfile(info, handle)


def verify_with_tectonic(tectonic: Path) -> None:
    observed = subprocess.run(
        [str(tectonic), "--version"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    if observed != "Tectonic 0.17.0":
        raise PackageError(
            f"expected Tectonic 0.17.0, observed {observed}"
        )
    verify_dir = OUTPUT / "verify"
    if verify_dir.exists():
        shutil.rmtree(verify_dir)
    verify_dir.mkdir(parents=True)
    subprocess.run(
        [
            str(tectonic),
            "--keep-logs",
            "--keep-intermediates",
            "--outdir",
            str(verify_dir),
            MAIN_FILE,
        ],
        cwd=STAGING,
        check=True,
    )
    pdf = verify_dir / "qwen3-coreai-report.pdf"
    log = verify_dir / "qwen3-coreai-report.log"
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise PackageError("isolated arXiv source compile did not produce a PDF")
    forbidden = (
        "Overfull \\hbox",
        "Undefined control sequence",
        "There were undefined references",
    )
    log_text = log.read_text(encoding="utf-8", errors="replace")
    if any(fragment in log_text for fragment in forbidden):
        raise PackageError("isolated arXiv source compile contains a fatal warning")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tectonic",
        type=Path,
        help="Compile-check the staged bundle with this Tectonic 0.17.0 binary.",
    )
    arguments = parser.parse_args()
    prepare_staging()
    write_archive()
    if arguments.tectonic is not None:
        verify_with_tectonic(arguments.tectonic.resolve())
    print("ARXIV_PACKAGE_OK")
    print(f"archive={ARCHIVE}")
    print(f"archive_sha256={sha256(ARCHIVE)}")
    print(f"source_files={len(EXPECTED_INPUTS)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, PackageError) as error:
        print(f"ARXIV_PACKAGE_FAILED: {error}")
        raise SystemExit(1)
