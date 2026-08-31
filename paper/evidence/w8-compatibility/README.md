# Sanitized W8 compatibility events

`sanitized-load-events.jsonl` contains one record per admitted load attempt and
one device-transition record linked to the second old-artifact attempt. Each
load record preserves the result, exact artifact identity, and host termination
result from its named source capture. The transition record preserves the full
reboot request, the command timeout while waiting for the device, and the
subsequent observation that the same physical device was again booted and
connected before install and launch. It explicitly records that no boot-session
identifier or uptime was captured, so the sequence is not presented as an
independently instrumented boot transition. The source SHA-256 digests identify
the retained private originals; they do not independently prove the manual
extraction mapping.

The sanitization removes unique device identifiers, application-container
paths, process identifiers, audit tokens, wall-clock timestamps, and unrelated
device-state fields. It does not alter the recorded failure phase, status
codes, allocation-request size, load duration, memory values, unload result,
or process termination result.

The original captures are retained privately because they contain persistent
device identifiers and ephemeral application paths. The candidate event also
keeps its source-harness labels, but marks them as labels rather than evidence
of public-artifact timing or ANE execution. The sanitized records are
the event-level evidence distributed with the report; the derived
`results/w8-aot-compatibility-evidence.json` provides the publication summary
and claim boundaries.
