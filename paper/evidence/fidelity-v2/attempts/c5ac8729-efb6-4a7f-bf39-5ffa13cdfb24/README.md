# Successful fidelity attempt c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24

This directory publishes the single corrected formal attempt authorized by
`paper/FIDELITY_V2_AMENDMENT_1.md`. The attempt completed without interruption:
all ten reference runs, all ten W8 candidate runs, and all ten case comparisons
reported `success`. The process exited with code 0.

The registered case-level macro results were:

| Split | Cases | Mean cosine | Minimum cosine | Top-1 agreement | Mean NLL delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tuning | 6 | 0.9972995580522954 | 0.9634192756433698 | 0.9895833333333334 | 0.0041901005215974 |
| Holdout | 4 | 0.9968972864500013 | 0.9533912271441090 | 0.9696691176470589 | 0.008879966197800114 |

NLL delta is candidate minus reference. These measurements compare the
disclosed W8 authoring recipe with the pinned FP16 authoring reference under
the ten frozen inputs. They do not measure compiled-device logits, downstream
language capability, ANE performance, or general benchmark quality.

The prerequisite health probe also succeeded. Its Apple and Hugging Face
vectors selected the same top-1 token and had binary64 cosine
`0.9999970493198227`.

## Publication transform

The evaluator first sealed the untouched run directory with manifest SHA-256
`99d64dcdee03ec562982dbb80fac47ebdec9c44655fd46c01db069635acd89be`.
That original manifest is retained verbatim as
`raw/EVALUATOR_MANIFEST.sha256`.

The repository ignores `*.log`, so publication changed only two path names:
`stdout.log` became `stdout.txt`, and `stderr.log` became `stderr.txt`. Their
bytes and SHA-256 values did not change. `publication-transform.json` records
the mapping. `raw/MANIFEST.sha256` seals the actual published raw layout, and
`PUBLIC_MANIFEST.sha256` seals this complete attempt directory.

Apart from those two filename changes and the added publication records, the
files under `raw/` are byte-for-byte copies of the completed evaluator output.
