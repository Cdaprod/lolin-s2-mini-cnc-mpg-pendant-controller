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

The static manifest finds two front-shell references in `Sketch003` whose source object `Pad002` is absent from the candidate XML. Both references are outside the active `Body` Tip path, so they are historical for that root. The rear root reaches suppressed `Pad022 → Pad021 → Binder016` through `RemoveWarpProneTongues`; this is the pre-bypass history, not the separately validated `Pocket015` bypass. The Tip-rooted audit also shows that `Sketch021` and its `Binder017` references are not active-Tip-reachable.

## Context paths and portability

The auditor now emits active-tip-reachable `Context` XLinks separately from geometry dependencies. The front Tip reaches two external Context XLinks and the rear Tip reaches four; all point to `../pendant.FCStd`. They resolve at the candidate's current repository location, but all six fail resolution in a relocated copy without the monolith. These are classified as non-geometric document/container context, not as proof that the shell shapes consume monolith geometry. They still require explicit review before claiming portability or monolith independence.

The audit script was run on both the original candidate path and a relocated disposable copy. It reported the six resolved and six missing-context cases as expected. Python byte-compilation also passed.

## Bounded native recompute attempt

A disposable copy was placed under `/tmp/front-rear-shells-validation-20261030/` with the master alongside it, but without the monolith. FreeCADCmd opened it and began recomputing. The log reported unresolved external Context links to `../pendant.FCStd` and `Pad021.?Face97` missing for suppressed `Pad022`. The static Tip audit shows `Pad022` is suppressed but still appears in the active rear-Tip ancestry through `RemoveWarpProneTongues`; this candidate has not adopted the later validated bypass. The log also reported failed `Binder015` internal offset, failed `Binder017` through-hole offset, and six missing generated subelements from `Binder017` on `Sketch021`. The manifest confirms `Binder015`, `Binder017`, and `Sketch021` are outside the active rear Tip closure, so those three errors are historical whole-document warnings rather than evidence of the active Tip's failure. FreeCAD also reported Body-scope links across the in-document front/rear shell pair. After 2 minutes 48 seconds the process remained CPU-active and had not reached the result/save stages; it was terminated to avoid a long full-history run after the active `Pad022` reference failure. No candidate was saved by the test.

Therefore this run does **not** establish final Tip validity, native save/reopen, or preserved geometry. It establishes that this pre-bypass candidate cannot yet be promoted as a self-contained editable shell pair and identifies the active `Pad022` reference path plus monolith Context links for follow-up. The inactive `Sketch021`/`Binder017` messages should not be treated as active-Tip blockers. No repair or broad extraction was attempted.

## Source preservation

The untracked candidate hash remained unchanged. The monolithic source hash remained `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`, and the master hash remained `a2990a24c9b4fa140e25c1c5ef721fe65a6cb36f48a55cc168a11778421e56cb`. No assembly, master, or monolithic CAD file was modified.
