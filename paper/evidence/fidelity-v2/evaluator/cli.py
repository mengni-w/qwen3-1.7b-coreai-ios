"""Command-line orchestration for fidelity-v2."""

from __future__ import annotations

import argparse
import json
import os
import resource
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Sequence

from .contract import (
    CONTRACT,
    ContractError,
    make_source_model_lock,
    run_checked,
    sha256_bytes,
    sha256_file,
    write_json,
)
from .runtime import (
    NUMERIC_THREAD_ENVIRONMENT,
    _peak_rss_record,
    prepare_preflight,
    repository_root,
    run_worker,
)


WORKER_SENTINEL = "QWEN3_FIDELITY_V2_ORCHESTRATED_WORKER"


class _TerminationRequested(Exception):
    def __init__(self, signum: int):
        super().__init__(f"termination signal {signum}")
        self.signum = signum


def _configure_process_environment() -> None:
    for name, value in NUMERIC_THREAD_ENVIRONMENT.items():
        os.environ[name] = value
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _validate_run_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("run ID must be a canonical UUID") from error
    canonical = str(parsed)
    if value != canonical:
        raise argparse.ArgumentTypeError(f"run ID must use canonical form: {canonical}")
    return canonical


def _empty_destination(path: Path, description: str) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ContractError(
                f"{description} must not exist or must be empty: {path}"
            )
    else:
        path.mkdir(parents=True)


def _validate_empty_destination(path: Path, description: str) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ContractError(f"{description} must not exist or must be empty: {path}")


def _claim_run_id(
    *,
    run_id: str,
    output_dir: Path,
    repo_root: Path | None = None,
) -> Path:
    root = (repo_root or repository_root()).resolve()
    common_git_dir_text = run_checked(
        ["git", "rev-parse", "--git-common-dir"], cwd=root
    )
    common_git_dir = Path(common_git_dir_text)
    if not common_git_dir.is_absolute():
        common_git_dir = root / common_git_dir
    registry = common_git_dir.resolve() / "qwen3-fidelity-v2-run-ids"
    registry.mkdir(parents=True, exist_ok=True)
    claim_path = registry / f"{run_id}.json"
    payload = {
        "schema": "qwen3-coreai-ios-fidelity-run-id-claim-v1",
        "runID": run_id,
        "claimedAtUnixSeconds": time.time(),
        "repositoryCommit": run_checked(["git", "rev-parse", "HEAD"], cwd=root),
        "outputDirectoryUTF8SHA256": sha256_bytes(
            str(output_dir.resolve()).encode("utf-8")
        ),
        "scope": "repository-git-common-directory",
    }
    serialized = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    try:
        with claim_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ContractError(
            f"run ID {run_id} was already claimed in this repository; "
            "a different output directory does not permit a rerun"
        ) from error
    return claim_path


def prepare_source(model_dir: Path, lock_file: Path) -> int:
    from huggingface_hub import snapshot_download

    if lock_file.exists():
        raise ContractError(f"source lock already exists: {lock_file}")
    if model_dir == lock_file.parent or model_dir in lock_file.parents:
        raise ContractError(
            "source lock must be outside the downloaded model directory"
        )
    _empty_destination(model_dir, "model directory")
    snapshot_download(
        repo_id=CONTRACT.source_model_id,
        revision=CONTRACT.source_model_revision,
        local_dir=model_dir,
    )
    lock = make_source_model_lock(model_dir)
    write_json(lock_file, lock)
    print(f"source_lock={lock_file}")
    print(f"canonical_sha256={lock['canonicalSHA256']}")
    return 0


def check_environment(coreai_repo: Path, model_dir: Path, source_lock: Path) -> int:
    environment, tokenizer, serialized, _ = prepare_preflight(
        coreai_repo=coreai_repo,
        model_dir=model_dir,
        source_lock=source_lock,
    )
    result = {
        "status": "ready",
        "environment": environment,
        "tokenizerClass": f"{type(tokenizer).__module__}.{type(tokenizer).__name__}",
        "caseCount": len(serialized),
        "inputTokenCounts": {
            case["id"]: case["inputTokenCount"] for case in serialized
        },
    }
    print(
        json.dumps(
            result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
    )
    return 0


def _write_evidence_manifest(output_dir: Path) -> str:
    manifest_path = output_dir / "MANIFEST.sha256"
    entries = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path != manifest_path:
            entries.append((sha256_file(path), path.relative_to(output_dir).as_posix()))
    payload = "".join(f"{digest}  {relative}\n" for digest, relative in entries)
    with manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return sha256_file(manifest_path)


def _sample_process_tree(process: object) -> tuple[int, int] | None:
    import psutil

    try:
        processes = [process, *process.children(recursive=True)]
        unique = {item.pid: item for item in processes}
        resident_bytes = 0
        observed = 0
        for item in unique.values():
            try:
                resident_bytes += int(item.memory_info().rss)
                observed += 1
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
        return resident_bytes, observed
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None


def launch_run(
    *,
    run_id: str,
    coreai_repo: Path,
    model_dir: Path,
    source_lock: Path,
    output_dir: Path,
) -> int:
    # A rejected preflight is not the frozen official attempt. The output
    # directory is created only after all non-model checks and the synthetic
    # Apple-authoring smoke test pass.
    prepare_preflight(
        coreai_repo=coreai_repo,
        model_dir=model_dir,
        source_lock=source_lock,
    )
    _validate_empty_destination(output_dir, "run output directory")
    claim_path = _claim_run_id(run_id=run_id, output_dir=output_dir)
    _empty_destination(output_dir, "run output directory")
    claim_copy = output_dir / "run-id-claim.json"
    claim_copy.write_bytes(claim_path.read_bytes())
    script = repository_root() / "paper/evidence/fidelity-v2/run_fidelity_v2.py"
    command = [
        sys.executable,
        str(script),
        "_worker",
        "--run-id",
        run_id,
        "--coreai-repo",
        str(coreai_repo),
        "--model-dir",
        str(model_dir),
        "--source-lock",
        str(source_lock),
        "--output-dir",
        str(output_dir),
    ]
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = str(CONTRACT.seed)
    environment.update(NUMERIC_THREAD_ENVIRONMENT)
    environment["TOKENIZERS_PARALLELISM"] = "false"
    environment[WORKER_SENTINEL] = run_id
    started_wall = time.time()
    started_monotonic = time.monotonic()
    stdout_path = output_dir / "stdout.log"
    stderr_path = output_dir / "stderr.log"
    interrupted = False
    termination_actions: list[str] = []
    sample_count = 0
    sampling_error_count = 0
    peak_tree_resident_bytes = 0
    maximum_observed_process_count = 0
    import psutil

    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
        )
        root_process = psutil.Process(child.pid)
        previous_sigterm_handler = signal.getsignal(signal.SIGTERM)

        def request_termination(signum, _frame):  # type: ignore[no-untyped-def]
            raise _TerminationRequested(signum)

        signal.signal(signal.SIGTERM, request_termination)
        try:
            while child.poll() is None:
                sample = _sample_process_tree(root_process)
                if sample is None:
                    sampling_error_count += 1
                else:
                    resident_bytes, process_count = sample
                    sample_count += 1
                    peak_tree_resident_bytes = max(
                        peak_tree_resident_bytes, resident_bytes
                    )
                    maximum_observed_process_count = max(
                        maximum_observed_process_count, process_count
                    )
                try:
                    child.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
        except (KeyboardInterrupt, _TerminationRequested) as interruption:
            interrupted = True
            if child.poll() is None:
                forwarded_signal = (
                    signal.SIGINT
                    if isinstance(interruption, KeyboardInterrupt)
                    else interruption.signum
                )
                child.send_signal(forwarded_signal)
                termination_actions.append(signal.Signals(forwarded_signal).name)
                try:
                    child.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    termination_actions.append("SIGTERM")
                    try:
                        child.wait(timeout=10.0)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        termination_actions.append("SIGKILL")
                        child.wait()
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm_handler)
        final_sample = _sample_process_tree(root_process)
        if final_sample is not None:
            resident_bytes, process_count = final_sample
            sample_count += 1
            peak_tree_resident_bytes = max(peak_tree_resident_bytes, resident_bytes)
            maximum_observed_process_count = max(
                maximum_observed_process_count, process_count
            )
        exit_code = child.wait()
        stdout.flush()
        stderr.flush()
        os.fsync(stdout.fileno())
        os.fsync(stderr.fileno())
    finished_wall = time.time()
    child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    child_raw_rss = int(child_usage.ru_maxrss)
    child_rss_bytes = (
        child_raw_rss if sys.platform == "darwin" else child_raw_rss * 1024
    )
    write_json(
        output_dir / "process-result.json",
        {
            "schema": "qwen3-coreai-ios-fidelity-process-result-v1",
            "runID": run_id,
            "command": [
                Path(command[0]).name,
                "paper/evidence/fidelity-v2/run_fidelity_v2.py",
                "_worker",
                "--run-id",
                run_id,
                "--coreai-repo",
                "<COREAI_MODELS_CHECKOUT>",
                "--model-dir",
                "<PINNED_SOURCE_MODEL_DIRECTORY>",
                "--source-lock",
                "<SOURCE_MODEL_LOCK_JSON>",
                "--output-dir",
                "<RUN_OUTPUT_DIRECTORY>",
            ],
            "exitCode": exit_code,
            "orchestratorInterrupted": interrupted,
            "terminationActions": termination_actions,
            "startedAtUnixSeconds": started_wall,
            "finishedAtUnixSeconds": finished_wall,
            "elapsedSeconds": time.monotonic() - started_monotonic,
            "childPeakMemory": {
                "ruMaxRSSRaw": child_raw_rss,
                "ruMaxRSSReportedUnit": "bytes" if sys.platform == "darwin" else "KiB",
                "peakResidentBytes": child_rss_bytes,
            },
            "orchestratorPeakMemory": _peak_rss_record(),
            "sampledProcessTreePeakMemory": {
                "samplingIntervalSeconds": 0.1,
                "sampleCount": sample_count,
                "samplingErrorCount": sampling_error_count,
                "peakAggregateResidentBytes": peak_tree_resident_bytes,
                "maximumObservedProcessCount": maximum_observed_process_count,
                "semantics": (
                    "maximum sampled sum of RSS for the worker and all observed "
                    "descendants; distinct from ru_maxrss"
                ),
            },
        },
    )
    manifest_hash = _write_evidence_manifest(output_dir)
    print(f"run_id={run_id}")
    print(f"exit_code={exit_code}")
    print(f"output_dir={output_dir}")
    print(f"evidence_manifest_sha256={manifest_hash}")
    if interrupted:
        return 130
    return exit_code if exit_code >= 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Frozen Qwen3-1.7B Core AI W8 fidelity-v2 evaluator"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare-source",
        help="download the exact source checkpoint revision and write its file lock",
    )
    prepare.add_argument("--model-dir", type=_path, required=True)
    prepare.add_argument("--source-lock", type=_path, required=True)

    for name, help_text in (
        ("check", "validate all frozen inputs without running either model"),
        ("run", "execute the single official reference/candidate run"),
        ("_worker", "internal orchestrated worker; do not invoke directly"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--coreai-repo", type=_path, required=True)
        command.add_argument("--model-dir", type=_path, required=True)
        command.add_argument("--source-lock", type=_path, required=True)
        if name in {"run", "_worker"}:
            command.add_argument("--run-id", type=_validate_run_id, required=True)
            command.add_argument("--output-dir", type=_path, required=True)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    # These variables are set before NumPy, Torch, Transformers, or coreai-opt
    # are imported. The run subcommand repeats them in the fresh worker's
    # launch environment so they take effect at interpreter startup.
    _configure_process_environment()
    parser = build_parser()
    args = parser.parse_args(arguments)
    try:
        if args.command == "prepare-source":
            return prepare_source(args.model_dir, args.source_lock)
        if args.command == "check":
            return check_environment(args.coreai_repo, args.model_dir, args.source_lock)
        if args.command == "run":
            return launch_run(
                run_id=args.run_id,
                coreai_repo=args.coreai_repo,
                model_dir=args.model_dir,
                source_lock=args.source_lock,
                output_dir=args.output_dir,
            )
        if args.command == "_worker":
            if os.environ.get(WORKER_SENTINEL) != args.run_id:
                raise ContractError(
                    "the internal worker must be launched by the run subcommand"
                )
            if os.environ.get("PYTHONHASHSEED") != str(CONTRACT.seed):
                raise ContractError(
                    "the worker interpreter was not started with PYTHONHASHSEED=0"
                )
            return run_worker(
                run_id=args.run_id,
                coreai_repo=args.coreai_repo,
                model_dir=args.model_dir,
                source_lock=args.source_lock,
                output_dir=args.output_dir,
            )
    except ContractError as error:
        print(f"CONTRACT_ERROR: {error}", file=sys.stderr)
        return 2
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    raise AssertionError(f"unhandled command: {args.command}")
