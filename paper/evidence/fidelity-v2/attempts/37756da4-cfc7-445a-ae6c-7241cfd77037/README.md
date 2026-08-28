# Failed fidelity attempt 37756da4-cfc7-445a-ae6c-7241cfd77037

This directory preserves the first formal fidelity attempt exactly as it
ended. It is a failed implementation attempt and supplies no fidelity result
for the manuscript.

The FP16 reference produced the same degenerate output for the first three
different prompts: 64 token IDs equal to zero, decoded as 64 exclamation
marks. Each corresponding teacher-forced logit file had the same SHA-256.
While the process was still running, inspection showed that the arrays were
FP16 tensors of shape `(64, 151936)` whose entries were all zero. A separate
reconstruction of an all-zero NumPy array with that shape produced the same
`.npy` SHA-256. Because a zero reference norm makes the registered cosine
metric undefined, the run could not yield a valid comparison.

The orchestrator was therefore interrupted during the fourth reference case.
It forwarded `SIGINT`, waited for the worker to stop, wrote
`process-result.json`, and sealed the files with `MANIFEST.sha256`. The raw
manifest verifies without modification. The temporary logit arrays were
removed by the evaluator's temporary-directory cleanup; only their hashes and
shape metadata remain in the sealed raw records.

Postmortem analysis traced the failure to an unfrozen numerical control in the
pinned Apple implementation. The iOS RMSNorm class squares FP16 activations
directly by default. Its Hugging Face parity branch first promotes the
activation to FP32, but that branch is selected only when `USE_HF_IMPL=true`
at module construction. The failed evaluator neither fixed nor recorded this
environment variable. Apple's own iOS primitive and model-comparison tests set
it to `true`. A two-element synthetic RMSNorm example reproduced the failure:
FP16 inputs `[300, -300]` overflow when squared and normalize to exact signed
zeros while still passing a finite-value check.

`supplemental-failure-record.json` separates direct observations from the
postmortem interpretation and records two additional procedural limitations:
the checkpoint files were owner-writable although the run instructions called
for a read-only snapshot, and the interrupted worker did not write the full
set of failure records required for a completed experiment. Neither issue is
hidden or retroactively repaired in `raw/`.

The public raw copy contains no user home path, email address, account name, or
host name. Generic temporary paths from the Python traceback are retained
because they identify the frozen Apple checkout and do not identify a person.
A later corrected attempt, if conducted, must use a prospective amendment, a
new evaluator commit, a new UUID, and a new output directory. It must not
replace or delete this record.
