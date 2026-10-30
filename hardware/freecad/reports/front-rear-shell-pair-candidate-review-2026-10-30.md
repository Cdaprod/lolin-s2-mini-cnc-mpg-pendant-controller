# Preserved front/rear shell-pair candidate review

Date: 2026-10-30  
Branch: `hardware-integration`  
Candidate: `pendant-bodies/front-rear-shells.FCStd` (pre-existing, untracked local file; not modified or staged)

## Read-only dependency inventory

The local candidate is a 34,498,633-byte FCStd with SHA-256 `21c9c4564badcb77fd805f7bccc062c05faff4c52b363b10792e3c7f78f50d24`. Its saved active roots are `Body.RestoreUpperFaceplateHoles` and `Body002.RearBossWallRamps45`.

| Root | Ordinary closure | Expanded closure | Sketch external refs |
|---|---:|---:|---:|
| Front `Body` | 79 | 125 | 26 |
| Rear `Body002` | 48 | 162 | 37 |

These are Tip-rooted serialized-graph counts, not proof of recomputation or extraction readiness. The candidate includes both Bodies and substantial construction history in one document; it does not itself establish two independent component documents.

The static manifest finds two front-shell references in `Sketch003` whose source object `Pad002` is absent from the candidate XML. Both references are outside the active `Body` Tip path, so they are historical for that root. The rear references name objects present in the candidate, but static presence does not guarantee that their referenced generated subelements exist after recomputation.

## Context paths and portability

The auditor now emits active-tip-reachable `Context` XLinks separately from geometry dependencies. The front Tip reaches two external Context XLinks and the rear Tip reaches four; all point to `../pendant.FCStd`. They resolve at the candidate's current repository location, but all six fail resolution in a relocated copy without the monolith. These are classified as non-geometric document/container context, not as proof that the shell shapes consume monolith geometry. They still require explicit review before claiming portability or monolith independence.

The audit script was run on both the original candidate path and a relocated disposable copy. It reported the six resolved and six missing-context cases as expected. Python byte-compilation also passed.

## Bounded native recompute attempt

A disposable copy was placed under `/tmp/front-rear-shells-validation-20261030/` with the master alongside it, but without the monolith. FreeCADCmd opened it and began recomputing. The log reported unresolved external Context links to `../pendant.FCStd`, `Pad021.?Face97` missing for suppressed `Pad022`, failed `Binder015` internal offset, failed `Binder017` through-hole offset, and six missing generated subelements on `Sketch021` from `Binder017`. It also reported Body-scope links across the in-document front/rear shell pair. After 2 minutes 48 seconds the process remained CPU-active and had not reached the result/save stages; it was terminated to avoid a long full-history run after these concrete failures. No candidate was saved by the test.

Therefore this run does **not** establish final Tip validity, native save/reopen, or preserved geometry. It establishes that the candidate cannot yet be promoted as a self-contained editable shell pair and identifies active reference failures to resolve before another bounded recompute. No repair or broad extraction was attempted.

## Source preservation

The untracked candidate hash remained unchanged. The monolithic source hash remained `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`, and the master hash remained `a2990a24c9b4fa140e25c1c5ef721fe65a6cb36f48a55cc168a11778421e56cb`. No assembly, master, or monolithic CAD file was modified.
