"""Model execution and evidence production for the frozen fidelity study."""

from __future__ import annotations

import gc
import importlib.metadata
import json
import multiprocessing
import os
import platform
import random
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Sequence

from .contract import (
    CONTRACT,
    SYSTEM_MESSAGE,
    ContractError,
    append_jsonl,
    canonical_json_bytes,
    run_checked,
    sha256_bytes,
    sha256_file,
    source_tree_manifest,
    token_ids_sha256,
    validate_coreai_checkout,
    validate_prompt_manifest,
    validate_source_model_lock,
    validate_tokenizer,
    write_json,
)
from .metrics import aggregate_all, compute_case_metrics


EXPECTED_DISTRIBUTIONS = {
    "coreai-core": "1.0.0b2",
    "coreai-models": "0.1.0",
    "coreai-opt": "0.2.1",
    "coreai-torch": "0.4.1",
    "coremltools": "9.0",
    "huggingface-hub": "0.36.2",
    "Jinja2": "3.1.6",
    "numpy": "2.3.5",
    "psutil": "7.2.2",
    "PyYAML": "6.0.3",
    "safetensors": "0.7.0",
    "sentencepiece": "0.2.1",
    "tokenizers": "0.23.0rc0",
    "torch": "2.9.0",
    "transformers": "4.57.6",
}

NUMERIC_THREAD_ENVIRONMENT = {
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}

SPAWN_DETERMINISM_SENTINEL = "QWEN3_FIDELITY_V2_DETERMINISTIC_SPAWN"
SPAWN_PROBE_DIRECTORY = "QWEN3_FIDELITY_V2_SPAWN_PROBE_DIRECTORY"
SPAWN_BOOTSTRAPPED = "QWEN3_FIDELITY_V2_SPAWN_BOOTSTRAPPED"


def _random_state_payload(state: tuple[Any, ...]) -> Any:
    version, values, gaussian = state
    return [version, list(values), gaussian]


def _numpy_state_payload(state: tuple[Any, ...]) -> Any:
    algorithm, values, position, has_gaussian, cached_gaussian = state
    return [
        algorithm,
        values.tolist(),
        int(position),
        int(has_gaussian),
        float(cached_gaussian),
    ]


def _reset_seeds() -> None:
    import numpy as np
    import torch

    random.seed(CONTRACT.seed)
    np.random.seed(CONTRACT.seed)
    torch.manual_seed(CONTRACT.seed)


def _set_determinism() -> None:
    os.environ["PYTHONHASHSEED"] = str(CONTRACT.seed)
    import torch

    _reset_seeds()
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


def _determinism_state() -> dict[str, Any]:
    import numpy as np
    import torch

    return {
        "pythonHashSeed": os.environ.get("PYTHONHASHSEED"),
        "pythonRandomStateSHA256": sha256_bytes(
            canonical_json_bytes(_random_state_payload(random.getstate()))
        ),
        "numpyRandomStateSHA256": sha256_bytes(
            canonical_json_bytes(_numpy_state_payload(np.random.get_state()))
        ),
        "torchInitialSeed": int(torch.initial_seed()),
        "torchDeterministicAlgorithmsEnabled": bool(
            torch.are_deterministic_algorithms_enabled()
        ),
        "torchDeterministicWarnOnly": bool(
            torch.is_deterministic_algorithms_warn_only_enabled()
        ),
        "torchThreads": int(torch.get_num_threads()),
        "torchInteropThreads": int(torch.get_num_interop_threads()),
        "numericThreadEnvironment": {
            name: os.environ.get(name) for name in NUMERIC_THREAD_ENVIRONMENT
        },
    }


def _expected_determinism_state() -> dict[str, Any]:
    import numpy as np

    python_rng = random.Random(CONTRACT.seed)
    numpy_rng = np.random.RandomState(CONTRACT.seed)
    return {
        "pythonHashSeed": str(CONTRACT.seed),
        "pythonRandomStateSHA256": sha256_bytes(
            canonical_json_bytes(_random_state_payload(python_rng.getstate()))
        ),
        "numpyRandomStateSHA256": sha256_bytes(
            canonical_json_bytes(_numpy_state_payload(numpy_rng.get_state()))
        ),
        "torchInitialSeed": CONTRACT.seed,
        "torchDeterministicAlgorithmsEnabled": True,
        "torchDeterministicWarnOnly": False,
        "torchThreads": 1,
        "torchInteropThreads": 1,
        "numericThreadEnvironment": NUMERIC_THREAD_ENVIRONMENT,
    }


def _bootstrap_spawned_palettization_process() -> None:
    """Freeze process-global state in coreai-opt's spawn workers.

    The Apple implementation deliberately uses the spawn start method. Those
    processes import this entrypoint afresh and therefore do not inherit the
    parent worker's Python, NumPy, or Torch state.
    """

    if os.environ.get(SPAWN_DETERMINISM_SENTINEL) != "1":
        return
    spawn_launcher = any("spawn_main" in argument for argument in sys.orig_argv)
    if multiprocessing.current_process().name == "MainProcess" and not spawn_launcher:
        return
    if os.environ.get(SPAWN_BOOTSTRAPPED) == "1":
        return
    _set_determinism()
    state = _determinism_state()
    if state != _expected_determinism_state():
        raise ContractError(f"spawn child determinism contract differs: {state}")
    probe_directory = os.environ.get(SPAWN_PROBE_DIRECTORY)
    if not probe_directory:
        raise ContractError("spawn child probe directory was not provided")
    os.environ[SPAWN_BOOTSTRAPPED] = "1"
    write_json(
        Path(probe_directory) / f"child-{os.getpid()}.json",
        {
            "schema": "qwen3-coreai-ios-fidelity-spawn-child-v1",
            "launcher": "multiprocessing.spawn_main",
            "state": state,
        },
    )


_bootstrap_spawned_palettization_process()


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def fidelity_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sysctl(name: str) -> str | None:
    result = subprocess.run(
        ["sysctl", "-n", name],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip()


def _rss_record(who: int) -> dict[str, Any]:
    raw = int(resource.getrusage(who).ru_maxrss)
    # Darwin reports bytes; Linux and several BSDs report KiB.
    bytes_value = raw if sys.platform == "darwin" else raw * 1024
    return {
        "ruMaxRSSRaw": raw,
        "ruMaxRSSReportedUnit": "bytes" if sys.platform == "darwin" else "KiB",
        "peakResidentBytes": bytes_value,
    }


def _peak_rss_record() -> dict[str, Any]:
    return _rss_record(resource.RUSAGE_SELF)


def _child_peak_rss_record() -> dict[str, Any]:
    return _rss_record(resource.RUSAGE_CHILDREN)


def _distribution_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution, expected in EXPECTED_DISTRIBUTIONS.items():
        try:
            actual = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as error:
            raise ContractError(
                f"required distribution is not installed: {distribution}"
            ) from error
        if actual != expected:
            raise ContractError(
                f"{distribution} version is {actual}; frozen environment requires {expected}"
            )
        versions[distribution] = actual
    return versions


def _installed_distribution_snapshot() -> list[dict[str, str]]:
    records = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        records.append({"name": name, "version": distribution.version})
    return sorted(records, key=lambda item: (item["name"].lower(), item["version"]))


def _relevant_evaluator_files() -> list[Path]:
    root = repository_root()
    paths = [
        root / "paper/EXPERIMENT_PROTOCOL_V1.md",
        root / "paper/evidence/fidelity-v2/prompt-manifest.json",
        root / "paper/evidence/fidelity-v2/environment.lock.json",
        root / "paper/evidence/fidelity-v2/README.md",
        root / "paper/evidence/fidelity-v2/run_fidelity_v2.py",
        root / "patches/qwen3-1.7b-coreai-main.patch",
        root / "recipes/qwen3_1_7b_w8_per_tensor.yaml",
    ]
    paths.extend(sorted((fidelity_root() / "evaluator").glob("*.py")))
    paths.extend(sorted((fidelity_root() / "spawn_bootstrap").glob("*.py")))
    paths.extend(sorted((fidelity_root() / "tests").glob("*.py")))
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ContractError(f"evaluator source files are missing: {missing}")
    return paths


def _validate_evaluator_commit() -> dict[str, Any]:
    root = repository_root()
    paths = _relevant_evaluator_files()
    relative = [path.relative_to(root).as_posix() for path in paths]

    for path in relative:
        run_checked(["git", "ls-files", "--error-unmatch", "--", path], cwd=root)
    unstaged = run_checked(
        ["git", "diff", "--name-only", "HEAD", "--", *relative], cwd=root
    )
    staged = run_checked(
        ["git", "diff", "--cached", "--name-only", "HEAD", "--", *relative], cwd=root
    )
    if unstaged or staged:
        raise ContractError(
            "frozen protocol/evaluator inputs differ from the current Git commit"
        )

    head = run_checked(["git", "rev-parse", "HEAD"], cwd=root)
    protocol_path = "paper/EXPERIMENT_PROTOCOL_V1.md"
    prompt_path = "paper/evidence/fidelity-v2/prompt-manifest.json"
    evaluator_path = "paper/evidence/fidelity-v2/evaluator/runtime.py"
    protocol_commit = run_checked(
        ["git", "log", "-1", "--format=%H", "--", protocol_path], cwd=root
    )
    prompt_commit = run_checked(
        ["git", "log", "-1", "--format=%H", "--", prompt_path], cwd=root
    )
    evaluator_commit = run_checked(
        ["git", "log", "-1", "--format=%H", "--", evaluator_path], cwd=root
    )
    if not protocol_commit or not prompt_commit or not evaluator_commit:
        raise ContractError(
            "protocol, prompt manifest, and evaluator must all be committed"
        )
    if len({protocol_commit, prompt_commit, evaluator_commit}) != 3:
        raise ContractError(
            "protocol, prompt manifest, and evaluator require three ordered commits"
        )
    protocol_commit_paths = run_checked(
        [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            protocol_commit,
        ],
        cwd=root,
    ).splitlines()
    prompt_commit_paths = run_checked(
        [
            "git",
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            prompt_commit,
        ],
        cwd=root,
    ).splitlines()
    if protocol_commit_paths != [protocol_path]:
        raise ContractError(
            f"protocol commit is not standalone: {protocol_commit_paths}"
        )
    if prompt_commit_paths != [prompt_path]:
        raise ContractError(
            f"prompt-manifest commit is not standalone: {prompt_commit_paths}"
        )
    run_checked(
        ["git", "merge-base", "--is-ancestor", protocol_commit, prompt_commit], cwd=root
    )
    run_checked(
        ["git", "merge-base", "--is-ancestor", prompt_commit, evaluator_commit],
        cwd=root,
    )
    run_checked(
        ["git", "merge-base", "--is-ancestor", evaluator_commit, head], cwd=root
    )

    protocol = root / protocol_path
    prompt_manifest = root / prompt_path
    if sha256_file(protocol) != CONTRACT.protocol_sha256:
        raise ContractError(
            "experiment protocol hash differs from the frozen evaluator constant"
        )
    if sha256_file(prompt_manifest) != CONTRACT.prompt_manifest_file_sha256:
        raise ContractError(
            "prompt manifest hash differs from the frozen evaluator constant"
        )

    return {
        "repositoryCommit": head,
        "protocolCommit": protocol_commit,
        "promptManifestCommit": prompt_commit,
        "evaluatorCommit": evaluator_commit,
        "sourceFiles": source_tree_manifest(paths, root),
    }


def validate_environment(
    *,
    coreai_repo: Path,
    model_dir: Path,
    source_lock: Path,
) -> dict[str, Any]:
    if platform.system() != "Darwin":
        raise ContractError("the frozen authoring run requires macOS")
    if platform.machine() != "arm64":
        raise ContractError("the frozen authoring run requires Apple silicon (arm64)")
    if sys.version_info[:2] != (3, 12):
        raise ContractError(
            f"the frozen environment requires Python 3.12; got {platform.python_version()}"
        )
    expected_prefix = (coreai_repo.resolve() / ".venv").resolve()
    actual_prefix = Path(sys.prefix).resolve()
    executable_path = Path(os.path.abspath(sys.executable))
    if actual_prefix != expected_prefix or not executable_path.is_relative_to(
        coreai_repo.resolve() / ".venv"
    ):
        raise ContractError(
            "the evaluator must run from the pinned coreai-models checkout's "
            f".venv; got sys.prefix={actual_prefix} and executable={executable_path}"
        )
    actual_thread_environment = {
        name: os.environ.get(name) for name in NUMERIC_THREAD_ENVIRONMENT
    }
    if actual_thread_environment != NUMERIC_THREAD_ENVIRONMENT:
        raise ContractError(
            "numeric-library thread controls are not frozen to one thread: "
            f"{actual_thread_environment}"
        )

    root = repository_root()
    environment_lock_path = root / "paper/evidence/fidelity-v2/environment.lock.json"
    environment_lock = json.loads(environment_lock_path.read_text(encoding="utf-8"))
    if (
        environment_lock.get("schema")
        != "qwen3-coreai-ios-fidelity-environment-lock-v1"
    ):
        raise ContractError("unexpected evaluator environment-lock schema")
    if environment_lock.get("platform") != {
        "architecture": "arm64",
        "operatingSystem": "macOS",
        "pythonMajorMinor": "3.12",
    }:
        raise ContractError("evaluator environment-lock platform contract differs")
    if environment_lock.get("distributions") != EXPECTED_DISTRIBUTIONS:
        raise ContractError("evaluator environment-lock distribution pins differ")
    if environment_lock.get("numericThreadEnvironment") != NUMERIC_THREAD_ENVIRONMENT:
        raise ContractError("evaluator environment-lock numeric thread controls differ")
    locked_coreai = environment_lock.get("coreAIModels", {})
    if locked_coreai != {
        "baseCommit": CONTRACT.apple_base_commit,
        "paperPatchSHA256": CONTRACT.paper_patch_sha256,
        "upstreamUVLockSHA256": CONTRACT.apple_uv_lock_sha256,
    }:
        raise ContractError("evaluator environment-lock coreai-models identity differs")
    paper_patch = root / "patches/qwen3-1.7b-coreai-main.patch"
    recipe = root / "recipes/qwen3_1_7b_w8_per_tensor.yaml"
    coreai_identity = validate_coreai_checkout(coreai_repo, paper_patch, recipe)
    source_identity = validate_source_model_lock(model_dir, source_lock)
    evaluator_identity = _validate_evaluator_commit()
    distributions = _distribution_versions()

    return {
        "schema": "qwen3-coreai-ios-fidelity-environment-v1",
        "operatingSystem": {
            "platform": platform.platform(),
            "macVersion": platform.mac_ver()[0],
            "kernelRelease": platform.release(),
        },
        "hardware": {
            "architecture": platform.machine(),
            "model": _sysctl("hw.model"),
            "machine": _sysctl("hw.machine"),
            "physicalMemoryBytes": _sysctl("hw.memsize"),
            "processorBrand": _sysctl("machdep.cpu.brand_string"),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executableBasename": Path(sys.executable).name,
            "usesPinnedCoreAIModelsDotVenv": True,
        },
        "distributions": distributions,
        "installedDistributionSnapshot": _installed_distribution_snapshot(),
        "coreAIModels": coreai_identity,
        "sourceModel": source_identity,
        "evaluator": evaluator_identity,
        "controls": {
            "seed": CONTRACT.seed,
            "deterministicAlgorithms": True,
            "torchThreads": 1,
            "torchInteropThreads": 1,
            "numericLibraryThreadEnvironment": NUMERIC_THREAD_ENVIRONMENT,
            "executionDevice": "cpu",
            "decode": "greedy",
            "doSample": False,
            "maxNewTokens": CONTRACT.max_new_tokens,
            "maxTotalContextTokens": CONTRACT.max_total_context,
            "truncation": False,
            "targetDType": CONTRACT.target_dtype,
        },
    }


def _activate_coreai_source(coreai_repo: Path) -> None:
    source = (coreai_repo / "python/src").resolve()
    if not source.is_dir():
        raise ContractError(f"coreai-models Python source is missing: {source}")
    sys.path.insert(0, str(source))
    import coreai_models

    imported = Path(coreai_models.__file__).resolve()
    if source not in imported.parents:
        raise ContractError(
            f"coreai_models imported from unpinned location: {imported}"
        )


def _prepare_with_deterministic_spawn(
    *,
    palettizer: Any,
    example_inputs: tuple[Any, ...],
    num_workers: int,
    expected_spawn_processes: int,
    probe_directory: Path,
) -> tuple[Any, dict[str, Any]]:
    if probe_directory.exists():
        if not probe_directory.is_dir() or any(probe_directory.iterdir()):
            raise ContractError(
                f"spawn probe directory is not empty: {probe_directory}"
            )
    else:
        probe_directory.mkdir(parents=True)

    previous = {
        SPAWN_DETERMINISM_SENTINEL: os.environ.get(SPAWN_DETERMINISM_SENTINEL),
        SPAWN_PROBE_DIRECTORY: os.environ.get(SPAWN_PROBE_DIRECTORY),
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
    }
    os.environ[SPAWN_DETERMINISM_SENTINEL] = "1"
    os.environ[SPAWN_PROBE_DIRECTORY] = str(probe_directory)
    bootstrap = fidelity_root() / "spawn_bootstrap"
    inherited_python_path = previous["PYTHONPATH"]
    python_path_parts = [str(bootstrap), str(fidelity_root())]
    if inherited_python_path:
        python_path_parts.append(inherited_python_path)
    os.environ["PYTHONPATH"] = os.pathsep.join(python_path_parts)
    try:
        prepared = palettizer.prepare(
            example_inputs=example_inputs,
            num_workers=num_workers,
        )
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    probe_paths = sorted(probe_directory.glob("child-*.json"))
    if len(probe_paths) != expected_spawn_processes:
        raise ContractError(
            "coreai-opt spawn process count differs: "
            f"expected {expected_spawn_processes}, observed {len(probe_paths)}"
        )
    expected_state = _expected_determinism_state()
    probes = []
    for path in probe_paths:
        probe = json.loads(path.read_text(encoding="utf-8"))
        if probe.get("schema") != "qwen3-coreai-ios-fidelity-spawn-child-v1":
            raise ContractError(f"unexpected spawn probe schema in {path.name}")
        if probe.get("state") != expected_state:
            raise ContractError(
                f"spawn probe state differs in {path.name}: {probe.get('state')}"
            )
        probes.append(probe)
    return prepared, {
        "requestedWorkerCount": num_workers,
        "observedSpawnProcessCount": len(probes),
        "state": expected_state,
        "probeRecordsCanonicalSHA256": sha256_bytes(canonical_json_bytes(probes)),
    }


def _run_synthetic_authoring_smoke(recipe: Path) -> dict[str, Any]:
    """Exercise the exact parser and KMeans prepare path without model data."""

    import torch
    import torch.nn as nn
    import torch.nn.utils.parametrize as parametrize
    from coreai_opt.palettization.kmeans import KMeansPalettizer
    from coreai_opt.palettization.spec.fake_palettize import _FakePalettizeImplBase
    from coreai_models.llm.export import _load_compression_config_object

    class SyntheticProjectionPair(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.first = nn.Conv2d(16, 32, kernel_size=1, bias=False).to(
                dtype=torch.float16
            )
            self.second = nn.Conv2d(32, 16, kernel_size=1, bias=False).to(
                dtype=torch.float16
            )
            with torch.no_grad():
                for index, module in enumerate((self.first, self.second)):
                    values = torch.linspace(
                        -1.0 + index * 0.125,
                        1.0 + index * 0.125,
                        module.weight.numel(),
                        dtype=torch.float16,
                    ).reshape_as(module.weight)
                    module.weight.copy_(values)

        def forward(self, value: Any) -> Any:
            return self.second(self.first(value))

    try:
        config = _load_compression_config_object(recipe, "iOS")
    except SystemExit as error:
        raise ContractError(
            f"Apple parser rejected the frozen recipe during smoke test: {error}"
        ) from error
    model = SyntheticProjectionPair().eval()
    input_value = torch.ones((1, 16, 1, 1), dtype=torch.float16)
    palettizer = KMeansPalettizer(model, config)
    with tempfile.TemporaryDirectory(prefix="fidelity-v2-smoke-spawn-") as temporary:
        prepared, spawn_contract = _prepare_with_deterministic_spawn(
            palettizer=palettizer,
            example_inputs=(input_value,),
            num_workers=2,
            expected_spawn_processes=2,
            probe_directory=Path(temporary) / "probes",
        )
    targets = []
    for name, module in prepared.named_modules():
        if not parametrize.is_parametrized(module, "weight"):
            continue
        if any(
            isinstance(item, _FakePalettizeImplBase)
            for item in module.parametrizations.weight
        ):
            targets.append(name)
    if targets != ["first", "second"]:
        raise ContractError(
            f"synthetic Apple KMeans targets differ: observed {targets}"
        )
    with torch.inference_mode():
        output = prepared(input_value)
    if output.dtype != torch.float16 or not bool(torch.isfinite(output).all()):
        raise ContractError("synthetic Apple KMeans output is not finite FP16")
    return {
        "schema": "qwen3-coreai-ios-fidelity-synthetic-authoring-smoke-v1",
        "status": "success",
        "recipeSHA256": sha256_file(recipe),
        "targetModules": targets,
        "representation": "KMeansPalettizer.prepare",
        "spawnDeterminism": spawn_contract,
    }


def prepare_preflight(
    *,
    coreai_repo: Path,
    model_dir: Path,
    source_lock: Path,
) -> tuple[dict[str, Any], Any, list[dict[str, Any]], int]:
    environment = validate_environment(
        coreai_repo=coreai_repo,
        model_dir=model_dir,
        source_lock=source_lock,
    )
    _activate_coreai_source(coreai_repo)
    _set_determinism()

    from transformers import AutoTokenizer

    root = repository_root()
    prompt_manifest_path = root / "paper/evidence/fidelity-v2/prompt-manifest.json"
    _, prompt_cases = validate_prompt_manifest(prompt_manifest_path)
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir),
        local_files_only=True,
        trust_remote_code=False,
    )
    serialized_cases = validate_tokenizer(tokenizer, prompt_cases)
    eos_token_id = tokenizer.eos_token_id
    if isinstance(eos_token_id, bool) or not isinstance(eos_token_id, int):
        raise ContractError(f"tokenizer exposes invalid EOS token id: {eos_token_id!r}")
    recipe = root / "recipes/qwen3_1_7b_w8_per_tensor.yaml"
    environment["syntheticAuthoringSmoke"] = _run_synthetic_authoring_smoke(recipe)
    environment["tokenizer"] = {
        "class": f"{type(tokenizer).__module__}.{type(tokenizer).__name__}",
        "eosTokenID": eos_token_id,
        "chatTemplateUTF8SHA256": sha256_bytes(tokenizer.chat_template.encode("utf-8")),
    }
    return environment, tokenizer, serialized_cases, eos_token_id


def _construct_causal_mask(
    max_length: int, query_length: int, offset: int, torch: Any
) -> Any:
    mask = torch.zeros((1, max_length, 1, query_length), dtype=torch.float16)
    for query_position in range(query_length):
        mask[:, offset + query_position + 1 :, :, query_position] = float("-inf")
    return mask


def _new_caches(model: Any, torch: Any) -> tuple[Any, Any]:
    from coreai_models.primitives.ios.cache import KVCacheHandler

    return KVCacheHandler.get_kv_cache_from_hf(model.config, dtype=torch.float16)


def _normalise_logits(output: Any, *, expected_query_length: int) -> Any:
    if str(output.dtype) != "torch.float16":
        raise ContractError(f"unexpected Apple iOS logit dtype: {output.dtype}")
    if output.ndim != 4 or output.shape[0] != 1 or output.shape[1] != 1:
        raise ContractError(f"unexpected Apple iOS logit layout: {tuple(output.shape)}")
    logits = output[0, 0]
    if logits.ndim != 2 or logits.shape[0] != expected_query_length:
        raise ContractError(
            f"unexpected normalized logit layout: {tuple(logits.shape)}"
        )
    return logits


def _teacher_forced_slice_bounds(
    *, prompt_length: int, completion_length: int, available_rows: int
) -> tuple[int, int]:
    if prompt_length <= 0 or completion_length <= 0:
        raise ContractError("teacher-forced prompt and completion must be non-empty")
    first = prompt_length - 1
    end = first + completion_length
    if end > available_rows:
        raise ContractError(
            "teacher-forced logit slicing exceeds the available positions: "
            f"[{first}:{end}] from {available_rows} rows"
        )
    return first, end


def greedy_completion(
    model: Any, input_token_ids: Sequence[int], eos_token_id: int
) -> dict[str, Any]:
    import torch

    prompt_length = len(input_token_ids)
    if prompt_length + CONTRACT.max_new_tokens > CONTRACT.max_total_context:
        raise ContractError("case would exceed the frozen context without truncation")
    key_cache, value_cache = _new_caches(model, torch)
    input_ids = torch.tensor([list(input_token_ids)], dtype=torch.int32)
    positions = torch.arange(prompt_length).to(torch.uint16).unsqueeze(0)
    offset = torch.tensor([0], dtype=torch.int32)
    mask = _construct_causal_mask(CONTRACT.max_total_context, prompt_length, 0, torch)

    generated: list[int] = []
    with torch.inference_mode():
        output = model(input_ids, positions, offset, mask, key_cache, value_cache)
        logits = _normalise_logits(output, expected_query_length=prompt_length)
        next_token = int(torch.argmax(logits[-1]).item())
        for generation_index in range(CONTRACT.max_new_tokens):
            generated.append(next_token)
            if next_token == eos_token_id:
                return {"tokenIDs": generated, "termination": "eos"}
            if generation_index + 1 == CONTRACT.max_new_tokens:
                break
            token_offset = prompt_length + generation_index
            token = torch.tensor([[next_token]], dtype=torch.int32)
            positions = torch.tensor([[token_offset]], dtype=torch.uint16)
            offset = torch.tensor([token_offset], dtype=torch.int32)
            mask = _construct_causal_mask(
                CONTRACT.max_total_context, 1, token_offset, torch
            )
            output = model(token, positions, offset, mask, key_cache, value_cache)
            logits = _normalise_logits(output, expected_query_length=1)
            next_token = int(torch.argmax(logits[-1]).item())
    return {"tokenIDs": generated, "termination": "max_new_tokens"}


def teacher_forced_logits(
    model: Any,
    input_token_ids: Sequence[int],
    reference_completion_ids: Sequence[int],
) -> Any:
    import torch

    if not reference_completion_ids:
        raise ContractError("reference completion is empty")
    teacher_input = list(input_token_ids) + list(reference_completion_ids[:-1])
    if (
        len(input_token_ids) + len(reference_completion_ids)
        > CONTRACT.max_total_context
    ):
        raise ContractError("teacher-forced case exceeds the frozen context")
    key_cache, value_cache = _new_caches(model, torch)
    query_length = len(teacher_input)
    input_ids = torch.tensor([teacher_input], dtype=torch.int32)
    positions = torch.arange(query_length).to(torch.uint16).unsqueeze(0)
    offset = torch.tensor([0], dtype=torch.int32)
    mask = _construct_causal_mask(CONTRACT.max_total_context, query_length, 0, torch)
    with torch.inference_mode():
        output = model(input_ids, positions, offset, mask, key_cache, value_cache)
        logits = _normalise_logits(output, expected_query_length=query_length)
        first, end = _teacher_forced_slice_bounds(
            prompt_length=len(input_token_ids),
            completion_length=len(reference_completion_ids),
            available_rows=int(logits.shape[0]),
        )
        selected = logits[first:end]
        if selected.shape[0] != len(reference_completion_ids):
            raise ContractError(
                "teacher-forced logit slicing produced the wrong position count"
            )
        return selected.detach().cpu().contiguous()


def _load_reference(model_dir: Path) -> tuple[Any, dict[str, Any]]:
    import torch
    import torch.nn as nn
    from coreai_models.models.ios.qwen3 import Qwen3ForCausalLMForiOS

    _reset_seeds()
    model = Qwen3ForCausalLMForiOS.from_hf(
        str(model_dir),
        max_context_length=CONTRACT.max_total_context,
        target_dtype=torch.float16,
        disable_embedding_quantization=True,
    ).eval()
    embedding = model.load_embeddings.embedding_table
    if embedding.dtype != torch.float16:
        raise ContractError(
            f"reference embedding is {embedding.dtype}, expected torch.float16"
        )
    if model.config.tie_word_embeddings is not True:
        raise ContractError("the frozen source model must use tied embeddings")
    expected_names = _expected_projection_names(int(model.config.num_hidden_layers))
    modules = dict(model.named_modules())
    invalid_projections = [
        name
        for name in expected_names
        if name not in modules
        or not isinstance(modules[name], nn.Conv2d)
        or modules[name].weight.dtype != torch.float16
    ]
    if len(expected_names) != 196 or invalid_projections:
        raise ContractError(
            "reference FP16 projection contract differs; "
            f"count={len(expected_names)}, invalid={invalid_projections[:8]}"
        )
    return model, {
        "role": "reference",
        "implementation": f"{Qwen3ForCausalLMForiOS.__module__}.{Qwen3ForCausalLMForiOS.__name__}",
        "embeddingQuantizationDisabled": True,
        "embeddingDType": str(embedding.dtype),
        "transformerPalettization": False,
        "transformerProjectionCount": len(expected_names),
        "transformerProjectionDType": "torch.float16",
        "computeDType": CONTRACT.target_dtype,
        "executionDevice": "cpu",
    }


def _expected_projection_names(layer_count: int) -> list[str]:
    names: list[str] = []
    for layer in range(layer_count):
        prefix = f"extend.model.layers.{layer}"
        names.extend(
            [
                f"{prefix}.self_attn.q_proj",
                f"{prefix}.self_attn.k_proj",
                f"{prefix}.self_attn.v_proj",
                f"{prefix}.self_attn.o_proj",
                f"{prefix}.mlp.up_proj",
                f"{prefix}.mlp.gate_proj",
                f"{prefix}.mlp.down_proj",
            ]
        )
    return names


def _load_candidate(
    model_dir: Path,
    recipe: Path,
    spawn_probe_directory: Path,
) -> tuple[Any, dict[str, Any]]:
    import torch
    import torch.nn as nn
    import torch.nn.utils.parametrize as parametrize
    from coreai_opt.palettization.kmeans import KMeansPalettizer
    from coreai_opt.palettization.spec.fake_palettize import _FakePalettizeImplBase
    from coreai_models.llm.export import _load_compression_config_object
    from coreai_models.models.ios.qwen3 import Qwen3ForCausalLMForiOS
    from coreai_models.primitives.ios.cache import KVCacheHandler

    _reset_seeds()
    model = Qwen3ForCausalLMForiOS.from_hf(
        str(model_dir),
        max_context_length=CONTRACT.max_total_context,
        target_dtype=torch.float16,
        disable_embedding_quantization=False,
    ).eval()
    embedding = model.load_embeddings.embedding_table
    if embedding.dtype != torch.int8:
        raise ContractError(
            f"candidate embedding is {embedding.dtype}, expected torch.int8"
        )
    if model.config.tie_word_embeddings is not True:
        raise ContractError("the frozen source model must use tied embeddings")
    layer_count = int(model.config.num_hidden_layers)
    expected_names = _expected_projection_names(layer_count)
    modules = dict(model.named_modules())
    missing_or_wrong = [
        name
        for name in expected_names
        if name not in modules
        or not isinstance(modules[name], nn.Conv2d)
        or modules[name].weight.dtype != torch.float16
    ]
    if missing_or_wrong:
        raise ContractError(
            f"candidate projection contract mismatch: {missing_or_wrong[:8]}"
        )
    if len(expected_names) != 196:
        raise ContractError(
            f"candidate exposes {len(expected_names)} projection weights; frozen recipe expects 196"
        )

    try:
        recipe_config = _load_compression_config_object(recipe, "iOS")
    except SystemExit as error:
        raise ContractError(
            f"Apple compression-recipe parser rejected the frozen recipe: {error}"
        ) from error
    query_length = 8
    _reset_seeds()
    input_ids = torch.randint(
        1,
        int(model.config.vocab_size),
        (1, query_length),
        dtype=torch.int32,
    )
    position_ids = torch.arange(query_length).to(torch.uint16).unsqueeze(0)
    in_step = torch.zeros((1,), dtype=torch.int32)
    causal_mask = torch.zeros(
        1,
        CONTRACT.max_total_context,
        1,
        query_length,
        dtype=torch.float16,
    )
    key_cache, value_cache = KVCacheHandler.get_kv_cache_from_hf(
        model.config, dtype=torch.float16
    )
    example_inputs = (
        input_ids,
        position_ids,
        in_step,
        causal_mask,
        key_cache,
        value_cache,
    )
    palettizer = KMeansPalettizer(model, recipe_config)
    model, spawn_contract = _prepare_with_deterministic_spawn(
        palettizer=palettizer,
        example_inputs=example_inputs,
        num_workers=32,
        expected_spawn_processes=32,
        probe_directory=spawn_probe_directory,
    )
    model = model.eval()

    prepared_modules = dict(model.named_modules())
    palettized_names: list[str] = []
    simulator_states: list[dict[str, Any]] = []
    for name, module in prepared_modules.items():
        if not parametrize.is_parametrized(module, "weight"):
            continue
        parametrizations = module.parametrizations.weight
        if any(
            isinstance(parametrization, _FakePalettizeImplBase)
            for parametrization in parametrizations
        ):
            palettized_names.append(name)
            simulators = [
                parametrization
                for parametrization in parametrizations
                if isinstance(parametrization, _FakePalettizeImplBase)
            ]
            if len(simulators) != 1:
                raise ContractError(
                    f"projection {name} has {len(simulators)} palettization simulators"
                )
            simulator = simulators[0]
            state = {
                "name": name,
                "nBits": int(simulator.n_bits),
                "granularity": type(simulator.granularity).__name__,
                "clusterDim": int(simulator.cluster_dim),
                "fakePalettizationEnabled": int(simulator.fake_palett_enabled.item()),
                "observerEnabled": int(simulator.observer_enabled.item()),
                "initialized": bool(simulator._initialized),
                "disabled": bool(simulator.is_disabled()),
            }
            if state != {
                "name": name,
                "nBits": 8,
                "granularity": "PerTensorGranularity",
                "clusterDim": 1,
                "fakePalettizationEnabled": 1,
                "observerEnabled": 0,
                "initialized": True,
                "disabled": False,
            }:
                raise ContractError(
                    f"prepared palettization state differs for {name}: {state}"
                )
            simulator_states.append(state)
    if sorted(palettized_names) != sorted(expected_names):
        unexpected = sorted(set(palettized_names) - set(expected_names))
        missing = sorted(set(expected_names) - set(palettized_names))
        raise ContractError(
            "prepared palettization targets differ from the frozen 196 projections; "
            f"missing={missing[:8]}, unexpected={unexpected[:8]}"
        )

    return model, {
        "role": "candidate",
        "implementation": f"{Qwen3ForCausalLMForiOS.__module__}.{Qwen3ForCausalLMForiOS.__name__}",
        "embeddingQuantizationDisabled": False,
        "embeddingDType": str(embedding.dtype),
        "embeddingQuantization": "Apple iOS symmetric per-tensor INT8",
        "transformerPalettization": "Apple coreai-opt KMeansPalettizer.prepare",
        "evaluationRepresentation": "enabled fake-palettized PyTorch authoring model",
        "palettizationWorkerCount": 32,
        "palettizationSpawnDeterminism": spawn_contract,
        "targetProjectionCount": len(palettized_names),
        "sourceProjectionDType": "torch.float16",
        "targetProjectionNamesSHA256": sha256_bytes(
            canonical_json_bytes(sorted(palettized_names))
        ),
        "palettizationSimulatorStatesSHA256": sha256_bytes(
            canonical_json_bytes(
                sorted(simulator_states, key=lambda item: item["name"])
            )
        ),
        "recipeSHA256": sha256_file(recipe),
        "computeDType": CONTRACT.target_dtype,
        "executionDevice": "cpu",
    }


def _decoded_completion(tokenizer: Any, token_ids: Sequence[int]) -> dict[str, Any]:
    text = tokenizer.decode(
        list(token_ids),
        skip_special_tokens=False,
        clean_up_tokenization_spaces=False,
    )
    return {"text": text, "utf8SHA256": sha256_bytes(text.encode("utf-8"))}


def _completion_fields(
    tokenizer: Any,
    completion: dict[str, Any],
) -> dict[str, Any]:
    completion_ids = completion["tokenIDs"]
    return {
        "completionTokenCount": len(completion_ids),
        "completionTokenIDs": completion_ids,
        "completionTokenIDsSHA256": token_ids_sha256(completion_ids),
        "completion": _decoded_completion(tokenizer, completion_ids),
        "termination": completion["termination"],
    }


def _teacher_forced_input_fields(
    input_token_ids: Sequence[int], reference_completion_ids: Sequence[int]
) -> dict[str, Any]:
    teacher_input = list(input_token_ids) + list(reference_completion_ids[:-1])
    return {
        "teacherForcedInputTokenCount": len(teacher_input),
        "teacherForcedInputTokenIDsSHA256": token_ids_sha256(teacher_input),
    }


def _failure(
    case: dict[str, Any], role: str, error: Exception, elapsed: float
) -> dict[str, Any]:
    return {
        "schema": "qwen3-coreai-ios-fidelity-model-run-v1",
        "caseID": case["id"],
        "split": case["split"],
        "modelRole": role,
        "status": "failed",
        "inputTokenCount": case["inputTokenCount"],
        "serializedInputSHA256": case["serializedUTF8SHA256"],
        "inputTokenIDsSHA256": case["inputTokenIDsSHA256"],
        "elapsedSeconds": elapsed,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": "".join(traceback.format_exception(error)),
        },
    }


def _global_role_failure(
    serialized_cases: Sequence[dict[str, Any]],
    role: str,
    error: Exception,
    raw_path: Path,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for case in serialized_cases:
        record = _failure(case, role, error, 0.0)
        record["failureScope"] = "model_load_or_compression"
        record["generationStatus"] = "not_started"
        record["teacherForceStatus"] = "not_started"
        if role == "reference":
            record["logitPersistenceStatus"] = "not_started"
        else:
            record["comparisonMetricStatus"] = "not_started"
        append_jsonl(raw_path, record)
        records[case["id"]] = record
    return records


def _reference_pass(
    *,
    model: Any,
    model_identity: dict[str, Any],
    tokenizer: Any,
    serialized_cases: Sequence[dict[str, Any]],
    scratch: Path,
    raw_path: Path,
    eos_token_id: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    import numpy as np

    records: dict[str, dict[str, Any]] = {}
    logit_paths: dict[str, Path] = {}
    for case in serialized_cases:
        started = time.monotonic()
        completion: dict[str, Any] | None = None
        teacher_force_completed = False
        print(f"REFERENCE_BEGIN case={case['id']}", flush=True)
        try:
            completion = greedy_completion(model, case["inputTokenIDs"], eos_token_id)
            completion_ids = completion["tokenIDs"]
            logits = teacher_forced_logits(model, case["inputTokenIDs"], completion_ids)
            teacher_force_completed = True
            logit_path = scratch / f"reference-{case['id']}.npy"
            with logit_path.open("xb") as handle:
                np.save(handle, logits.numpy(), allow_pickle=False)
            elapsed = time.monotonic() - started
            record = {
                "schema": "qwen3-coreai-ios-fidelity-model-run-v1",
                "caseID": case["id"],
                "split": case["split"],
                "modelRole": "reference",
                "status": "success",
                "inputTokenCount": case["inputTokenCount"],
                "serializedInputSHA256": case["serializedUTF8SHA256"],
                "inputTokenIDsSHA256": case["inputTokenIDsSHA256"],
                "generationStatus": "success",
                "teacherForceStatus": "success",
                "logitPersistenceStatus": "success",
                **_completion_fields(tokenizer, completion),
                **_teacher_forced_input_fields(case["inputTokenIDs"], completion_ids),
                "teacherForcedPositionCount": int(logits.shape[0]),
                "teacherForcedVocabularySize": int(logits.shape[1]),
                "teacherForcedLogitDType": str(logits.dtype),
                "ephemeralTeacherForcedLogitsFileSHA256": sha256_file(logit_path),
                "elapsedSeconds": elapsed,
                "modelIdentity": model_identity,
            }
            logit_paths[case["id"]] = logit_path
        except Exception as error:  # retain a record for every frozen case
            elapsed = time.monotonic() - started
            record = _failure(case, "reference", error, elapsed)
            if completion is None:
                record["generationStatus"] = "failed"
                record["teacherForceStatus"] = "not_started"
                record["logitPersistenceStatus"] = "not_started"
            else:
                record["generationStatus"] = "success"
                record["teacherForceStatus"] = (
                    "success" if teacher_force_completed else "failed"
                )
                record["logitPersistenceStatus"] = (
                    "failed" if teacher_force_completed else "not_started"
                )
                record.update(_completion_fields(tokenizer, completion))
                record.update(
                    _teacher_forced_input_fields(
                        case["inputTokenIDs"], completion["tokenIDs"]
                    )
                )
        append_jsonl(raw_path, record)
        records[case["id"]] = record
        print(f"REFERENCE_END case={case['id']} status={record['status']}", flush=True)
    return records, logit_paths


def _candidate_pass(
    *,
    model: Any,
    model_identity: dict[str, Any],
    tokenizer: Any,
    serialized_cases: Sequence[dict[str, Any]],
    reference_records: dict[str, dict[str, Any]],
    reference_logit_paths: dict[str, Path],
    raw_path: Path,
    comparison_path: Path,
    eos_token_id: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    import numpy as np

    records: dict[str, dict[str, Any]] = {}
    comparisons: list[dict[str, Any]] = []
    for case in serialized_cases:
        started = time.monotonic()
        completion: dict[str, Any] | None = None
        print(f"CANDIDATE_BEGIN case={case['id']}", flush=True)
        reference_record = reference_records[case["id"]]
        teacher_force_started = False
        teacher_force_completed = False
        reference_completion_ids: Sequence[int] | None = None
        try:
            completion = greedy_completion(model, case["inputTokenIDs"], eos_token_id)
            if reference_record.get("status") != "success":
                raise ContractError(
                    "reference case failed; shared-history comparison is unavailable"
                )
            reference_completion_ids = reference_record["completionTokenIDs"]
            teacher_force_started = True
            candidate_logits = teacher_forced_logits(
                model,
                case["inputTokenIDs"],
                reference_completion_ids,
            )
            teacher_force_completed = True
            candidate_teacher_input = _teacher_forced_input_fields(
                case["inputTokenIDs"], reference_completion_ids
            )
            if (
                candidate_teacher_input["teacherForcedInputTokenCount"]
                != reference_record["teacherForcedInputTokenCount"]
                or candidate_teacher_input["teacherForcedInputTokenIDsSHA256"]
                != reference_record["teacherForcedInputTokenIDsSHA256"]
            ):
                raise ContractError(
                    "candidate and reference teacher-forced input histories differ"
                )
            reference_path = reference_logit_paths[case["id"]]
            reference_logits = np.load(
                reference_path, mmap_mode="r", allow_pickle=False
            )
            metrics = compute_case_metrics(
                reference_logits,
                candidate_logits.numpy(),
                reference_completion_ids,
            )
            elapsed = time.monotonic() - started
            record = {
                "schema": "qwen3-coreai-ios-fidelity-model-run-v1",
                "caseID": case["id"],
                "split": case["split"],
                "modelRole": "candidate",
                "status": "success",
                "inputTokenCount": case["inputTokenCount"],
                "serializedInputSHA256": case["serializedUTF8SHA256"],
                "inputTokenIDsSHA256": case["inputTokenIDsSHA256"],
                "generationStatus": "success",
                "teacherForceStatus": "success",
                "comparisonMetricStatus": "success",
                **_completion_fields(tokenizer, completion),
                **candidate_teacher_input,
                "teacherForcedPositionCount": int(candidate_logits.shape[0]),
                "teacherForcedVocabularySize": int(candidate_logits.shape[1]),
                "teacherForcedLogitDType": str(candidate_logits.dtype),
                "teacherForcedHistory": "reference_completion",
                "elapsedSeconds": elapsed,
                "modelIdentity": model_identity,
            }
            comparison = {
                "schema": "qwen3-coreai-ios-fidelity-case-comparison-v1",
                "caseID": case["id"],
                "split": case["split"],
                "status": "success",
                "serializedInputSHA256": case["serializedUTF8SHA256"],
                "inputTokenIDsSHA256": case["inputTokenIDsSHA256"],
                "referenceCompletionTokenCount": reference_record[
                    "completionTokenCount"
                ],
                "candidateCompletionTokenCount": record["completionTokenCount"],
                "referenceCompletionTokenIDsSHA256": reference_record[
                    "completionTokenIDsSHA256"
                ],
                "candidateCompletionTokenIDsSHA256": record["completionTokenIDsSHA256"],
                "serializedInputBytesIdentical": True,
                "inputTokenIDsElementwiseIdentical": True,
                "referenceTeacherForcedInputTokenIDsSHA256": reference_record[
                    "teacherForcedInputTokenIDsSHA256"
                ],
                "candidateTeacherForcedInputTokenIDsSHA256": record[
                    "teacherForcedInputTokenIDsSHA256"
                ],
                "teacherForcedInputTokenIDsElementwiseIdentical": (
                    reference_record["teacherForcedInputTokenIDsSHA256"]
                    == record["teacherForcedInputTokenIDsSHA256"]
                    and reference_record["teacherForcedInputTokenCount"]
                    == record["teacherForcedInputTokenCount"]
                ),
                "evaluatedPositions": metrics["evaluatedPositions"],
                "T_i": metrics["evaluatedPositions"],
                "C_i": metrics["meanCosine"],
                "C_i_min": metrics["minimumCosine"],
                "A_i": metrics["top1Agreement"],
                "NLL_i_candidate": metrics["candidateMeanNLL"],
                "NLL_i_reference": metrics["referenceMeanNLL"],
                "Delta_i": metrics["meanNLLDelta"],
                "direction": CONTRACT.direction,
                "metrics": metrics,
            }
        except Exception as error:  # retain failure without replacing the case
            elapsed = time.monotonic() - started
            record = _failure(case, "candidate", error, elapsed)
            if completion is None:
                record["generationStatus"] = "failed"
                record["teacherForceStatus"] = "not_started"
                record["comparisonMetricStatus"] = "not_started"
            else:
                record["generationStatus"] = "success"
                if teacher_force_completed:
                    record["teacherForceStatus"] = "success"
                    record["comparisonMetricStatus"] = "failed"
                elif teacher_force_started:
                    record["teacherForceStatus"] = "failed"
                    record["comparisonMetricStatus"] = "not_started"
                else:
                    record["teacherForceStatus"] = "not_started"
                    record["comparisonMetricStatus"] = "not_started"
                record.update(_completion_fields(tokenizer, completion))
                if reference_completion_ids is not None:
                    record.update(
                        _teacher_forced_input_fields(
                            case["inputTokenIDs"], reference_completion_ids
                        )
                    )
            comparison = _failed_comparison(
                case=case,
                reference_record=reference_record,
                candidate_record=record,
                error=error,
            )
        append_jsonl(raw_path, record)
        append_jsonl(comparison_path, comparison)
        records[case["id"]] = record
        comparisons.append(comparison)
        print(f"CANDIDATE_END case={case['id']} status={record['status']}", flush=True)
    return records, comparisons


def _failed_comparison(
    *,
    case: dict[str, Any],
    reference_record: dict[str, Any],
    candidate_record: dict[str, Any],
    error: Exception,
) -> dict[str, Any]:
    reference_count = reference_record.get("completionTokenCount")
    candidate_count = candidate_record.get("completionTokenCount")
    return {
        "schema": "qwen3-coreai-ios-fidelity-case-comparison-v1",
        "caseID": case["id"],
        "split": case["split"],
        "status": "failed",
        "serializedInputSHA256": case["serializedUTF8SHA256"],
        "inputTokenIDsSHA256": case["inputTokenIDsSHA256"],
        "serializedInputBytesIdentical": True,
        "inputTokenIDsElementwiseIdentical": True,
        "referenceStatus": reference_record.get("status"),
        "candidateStatus": candidate_record.get("status"),
        "referenceCompletionTokenCount": reference_count,
        "candidateCompletionTokenCount": candidate_count,
        "referenceCompletionTokenIDsSHA256": reference_record.get(
            "completionTokenIDsSHA256"
        ),
        "candidateCompletionTokenIDsSHA256": candidate_record.get(
            "completionTokenIDsSHA256"
        ),
        "referenceTeacherForcedInputTokenIDsSHA256": reference_record.get(
            "teacherForcedInputTokenIDsSHA256"
        ),
        "candidateTeacherForcedInputTokenIDsSHA256": candidate_record.get(
            "teacherForcedInputTokenIDsSHA256"
        ),
        "teacherForcedInputTokenIDsElementwiseIdentical": (
            reference_record.get("teacherForcedInputTokenIDsSHA256") is not None
            and reference_record.get("teacherForcedInputTokenIDsSHA256")
            == candidate_record.get("teacherForcedInputTokenIDsSHA256")
            and reference_record.get("teacherForcedInputTokenCount")
            == candidate_record.get("teacherForcedInputTokenCount")
        ),
        "evaluatedPositions": None,
        "T_i": None,
        "intendedPositions": reference_count,
        "C_i": None,
        "C_i_min": None,
        "A_i": None,
        "NLL_i_candidate": None,
        "NLL_i_reference": None,
        "Delta_i": None,
        "direction": CONTRACT.direction,
        "metrics": None,
        "error": {"type": type(error).__name__, "message": str(error)},
    }


def _candidate_global_comparisons(
    *,
    serialized_cases: Sequence[dict[str, Any]],
    reference_records: dict[str, dict[str, Any]],
    error: Exception,
    comparison_path: Path,
) -> list[dict[str, Any]]:
    comparisons = []
    for case in serialized_cases:
        candidate_record = {
            "status": "failed",
        }
        record = _failed_comparison(
            case=case,
            reference_record=reference_records[case["id"]],
            candidate_record=candidate_record,
            error=error,
        )
        append_jsonl(comparison_path, record)
        comparisons.append(record)
    return comparisons


def _append_source_model_revalidation(
    *,
    phase: str,
    model_dir: Path,
    source_lock: Path,
    evidence_path: Path,
) -> None:
    lock = validate_source_model_lock(model_dir, source_lock)
    append_jsonl(
        evidence_path,
        {
            "schema": "qwen3-coreai-ios-source-model-revalidation-v1",
            "phase": phase,
            "validatedAtUnixSeconds": time.time(),
            "sourceModelCanonicalSHA256": lock["canonicalSHA256"],
            "fileCount": len(lock["files"]),
        },
    )


def _write_preflight_failure_evidence(
    *,
    run_id: str,
    output_dir: Path,
    error: Exception,
    started_wall: float,
    started_monotonic: float,
) -> int:
    raw_path = output_dir / "model-runs.jsonl"
    comparison_path = output_dir / "case-comparisons.jsonl"
    error_payload = {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
    }
    cases = [{"id": case_id, "split": "tuning"} for case_id in CONTRACT.tuning_ids] + [
        {"id": case_id, "split": "holdout"} for case_id in CONTRACT.holdout_ids
    ]
    for role in ("reference", "candidate"):
        for case in cases:
            append_jsonl(
                raw_path,
                {
                    "schema": "qwen3-coreai-ios-fidelity-model-run-v1",
                    "caseID": case["id"],
                    "split": case["split"],
                    "modelRole": role,
                    "status": "failed",
                    "failureScope": "preflight",
                    "inputTokenCount": None,
                    "serializedInputSHA256": None,
                    "inputTokenIDsSHA256": None,
                    "generationStatus": "not_started",
                    "teacherForceStatus": "not_started",
                    "comparisonMetricStatus": (
                        "not_started" if role == "candidate" else None
                    ),
                    "logitPersistenceStatus": (
                        "not_started" if role == "reference" else None
                    ),
                    "elapsedSeconds": 0.0,
                    "error": error_payload,
                },
            )
    comparisons = []
    for case in cases:
        comparison = {
            "schema": "qwen3-coreai-ios-fidelity-case-comparison-v1",
            "caseID": case["id"],
            "split": case["split"],
            "status": "failed",
            "failureScope": "preflight",
            "serializedInputSHA256": None,
            "inputTokenIDsSHA256": None,
            "serializedInputBytesIdentical": None,
            "inputTokenIDsElementwiseIdentical": None,
            "referenceStatus": "failed",
            "candidateStatus": "failed",
            "referenceCompletionTokenCount": None,
            "candidateCompletionTokenCount": None,
            "referenceCompletionTokenIDsSHA256": None,
            "candidateCompletionTokenIDsSHA256": None,
            "referenceTeacherForcedInputTokenIDsSHA256": None,
            "candidateTeacherForcedInputTokenIDsSHA256": None,
            "teacherForcedInputTokenIDsElementwiseIdentical": None,
            "evaluatedPositions": None,
            "T_i": None,
            "intendedPositions": None,
            "C_i": None,
            "C_i_min": None,
            "A_i": None,
            "NLL_i_candidate": None,
            "NLL_i_reference": None,
            "Delta_i": None,
            "direction": CONTRACT.direction,
            "metrics": None,
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        append_jsonl(comparison_path, comparison)
        comparisons.append(comparison)
    write_json(output_dir / "aggregates.json", aggregate_all(comparisons))
    write_json(
        output_dir / "preflight-failure.json",
        {
            "schema": "qwen3-coreai-ios-fidelity-preflight-failure-v1",
            "runID": run_id,
            "status": "failed",
            "error": error_payload,
        },
    )
    write_json(
        output_dir / "worker-run.json",
        {
            "schema": "qwen3-coreai-ios-fidelity-worker-run-v1",
            "runID": run_id,
            "status": "failed",
            "failurePhase": "preflight",
            "startedAtUnixSeconds": started_wall,
            "finishedAtUnixSeconds": time.time(),
            "elapsedSeconds": time.monotonic() - started_monotonic,
            "peakMemory": _peak_rss_record(),
            "terminatedChildProcessPeakMemory": _child_peak_rss_record(),
            "referenceSuccessfulCases": 0,
            "candidateSuccessfulCases": 0,
        },
    )
    return 2


def run_worker(
    *,
    run_id: str,
    coreai_repo: Path,
    model_dir: Path,
    source_lock: Path,
    output_dir: Path,
) -> int:
    started_wall = time.time()
    started_monotonic = time.monotonic()
    root = repository_root()
    try:
        environment, tokenizer, serialized_cases, eos_token_id = prepare_preflight(
            coreai_repo=coreai_repo,
            model_dir=model_dir,
            source_lock=source_lock,
        )
    except Exception as error:
        return _write_preflight_failure_evidence(
            run_id=run_id,
            output_dir=output_dir,
            error=error,
            started_wall=started_wall,
            started_monotonic=started_monotonic,
        )

    prompt_manifest_path = root / "paper/evidence/fidelity-v2/prompt-manifest.json"
    environment["runID"] = run_id
    environment["startedAtUnixSeconds"] = started_wall
    write_json(output_dir / "environment.json", environment)
    shutil.copyfile(
        root / "paper/evidence/fidelity-v2/environment.lock.json",
        output_dir / "environment.lock.json",
    )
    shutil.copyfile(
        coreai_repo / "uv.lock",
        output_dir / "coreai-models-uv.lock",
    )
    shutil.copyfile(prompt_manifest_path, output_dir / "prompt-manifest.json")
    serialized_payload = {
        "schema": "qwen3-coreai-ios-fidelity-serialized-inputs-v1",
        "systemMessage": SYSTEM_MESSAGE,
        "systemMessageUTF8SHA256": CONTRACT.system_message_utf8_sha256,
        "tokenEncoding": "u64be-count-followed-by-u32be-token-ids",
        "cases": serialized_cases,
    }
    serialized_payload["canonicalSHA256"] = sha256_bytes(
        canonical_json_bytes(serialized_payload)
    )
    write_json(output_dir / "serialized-inputs.json", serialized_payload)
    shutil.copyfile(source_lock, output_dir / "source-model-lock.json")
    source_revalidation_path = output_dir / "source-model-revalidations.jsonl"

    raw_path = output_dir / "model-runs.jsonl"
    comparison_path = output_dir / "case-comparisons.jsonl"
    recipe = root / "recipes/qwen3_1_7b_w8_per_tensor.yaml"
    reference_records: dict[str, dict[str, Any]]
    candidate_records: dict[str, dict[str, Any]]
    comparisons: list[dict[str, Any]]
    scratch_hashes: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix=f"fidelity-v2-{run_id}-") as temporary:
        scratch = Path(temporary)
        reference_model: Any | None = None
        try:
            print("REFERENCE_MODEL_LOAD_BEGIN", flush=True)
            _append_source_model_revalidation(
                phase="before_reference_load",
                model_dir=model_dir,
                source_lock=source_lock,
                evidence_path=source_revalidation_path,
            )
            reference_model, reference_identity = _load_reference(model_dir)
            _append_source_model_revalidation(
                phase="after_reference_load",
                model_dir=model_dir,
                source_lock=source_lock,
                evidence_path=source_revalidation_path,
            )
            print("REFERENCE_MODEL_LOAD_END", flush=True)
        except Exception as error:
            if reference_model is not None:
                del reference_model
                gc.collect()
            print("REFERENCE_MODEL_GLOBAL_FAILURE", file=sys.stderr, flush=True)
            traceback.print_exc()
            reference_records = _global_role_failure(
                serialized_cases, "reference", error, raw_path
            )
            reference_paths = {}
        else:
            try:
                reference_records, reference_paths = _reference_pass(
                    model=reference_model,
                    model_identity=reference_identity,
                    tokenizer=tokenizer,
                    serialized_cases=serialized_cases,
                    scratch=scratch,
                    raw_path=raw_path,
                    eos_token_id=eos_token_id,
                )
                for case_id, path in sorted(reference_paths.items()):
                    scratch_hashes.append(
                        {
                            "caseID": case_id,
                            "fileBasename": path.name,
                            "sha256": sha256_file(path),
                            "retainedAfterRun": False,
                        }
                    )
            finally:
                del reference_model
                gc.collect()

        candidate_model: Any | None = None
        try:
            print("CANDIDATE_MODEL_LOAD_AND_PALETTIZE_BEGIN", flush=True)
            _append_source_model_revalidation(
                phase="before_candidate_load",
                model_dir=model_dir,
                source_lock=source_lock,
                evidence_path=source_revalidation_path,
            )
            if sha256_file(recipe) != CONTRACT.recipe_sha256:
                raise ContractError("frozen candidate recipe changed during the run")
            candidate_model, candidate_identity = _load_candidate(
                model_dir,
                recipe,
                scratch / "candidate-spawn-probes",
            )
            _append_source_model_revalidation(
                phase="after_candidate_load",
                model_dir=model_dir,
                source_lock=source_lock,
                evidence_path=source_revalidation_path,
            )
            print("CANDIDATE_MODEL_LOAD_AND_PALETTIZE_END", flush=True)
        except Exception as error:
            if candidate_model is not None:
                del candidate_model
                gc.collect()
            print("CANDIDATE_MODEL_GLOBAL_FAILURE", file=sys.stderr, flush=True)
            traceback.print_exc()
            candidate_records = _global_role_failure(
                serialized_cases, "candidate", error, raw_path
            )
            comparisons = _candidate_global_comparisons(
                serialized_cases=serialized_cases,
                reference_records=reference_records,
                error=error,
                comparison_path=comparison_path,
            )
        else:
            try:
                candidate_records, comparisons = _candidate_pass(
                    model=candidate_model,
                    model_identity=candidate_identity,
                    tokenizer=tokenizer,
                    serialized_cases=serialized_cases,
                    reference_records=reference_records,
                    reference_logit_paths=reference_paths,
                    raw_path=raw_path,
                    comparison_path=comparison_path,
                    eos_token_id=eos_token_id,
                )
            finally:
                del candidate_model
                gc.collect()

    write_json(
        output_dir / "ephemeral-logits.json",
        {
            "schema": "qwen3-coreai-ios-fidelity-ephemeral-logits-v1",
            "description": (
                "Reference teacher-forced logits were retained only in an isolated temporary "
                "directory until the corresponding candidate comparison completed."
            ),
            "files": scratch_hashes,
        },
    )
    aggregates = aggregate_all(comparisons)
    write_json(output_dir / "aggregates.json", aggregates)

    finished_wall = time.time()
    all_success = all(
        record.get("status") == "success"
        for record in list(reference_records.values())
        + list(candidate_records.values())
    ) and all(split.get("status") == "success" for split in aggregates["splits"])
    write_json(
        output_dir / "worker-run.json",
        {
            "schema": "qwen3-coreai-ios-fidelity-worker-run-v1",
            "runID": run_id,
            "status": "success" if all_success else "failed",
            "startedAtUnixSeconds": started_wall,
            "finishedAtUnixSeconds": finished_wall,
            "elapsedSeconds": time.monotonic() - started_monotonic,
            "peakMemory": _peak_rss_record(),
            "terminatedChildProcessPeakMemory": _child_peak_rss_record(),
            "referenceSuccessfulCases": sum(
                record.get("status") == "success"
                for record in reference_records.values()
            ),
            "candidateSuccessfulCases": sum(
                record.get("status") == "success"
                for record in candidate_records.values()
            ),
        },
    )
    return 0 if all_success else 2
