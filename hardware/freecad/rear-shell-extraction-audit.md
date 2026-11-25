# Rear shell standalone extraction audit

Date: 2026-10-29
Branch: `hardware-integration`
Starting commit: `d0aaba0 Correct rear bypass geometry comparison`

## Outcome

The validated `RemoveWarpProneTongues → Pocket015` bypass remains a useful
geometry-preserving monolithic candidate, but it is **not yet a standalone
rear-shell source**. The prior 47-object count follows `OutList` feature inputs
and omits Sketcher external-geometry references. A disposable `Document.copyObject`
probe exposed those hidden links: copying the rear Tip alone reports unresolved
front/rear subobjects, and copying the 47 listed objects recursively also reports
unresolved external geometry. Both probes were stopped before saving a candidate.

No production CAD document, master, or modular assembly was modified. The
authoritative `pendant.FCStd`, existing component files, backups, and untracked
recovery candidates remain untouched. No candidate was promoted.

## Dependency boundary found

The earlier 47-object count is reproducible for the traversal that follows each
feature's `OutList` and omits Body/Part containers. That is useful for ordinary
feature links, but it is not a complete extraction closure. Sketcher stores
external geometry and generated subelement references outside those ordinary
`OutList` links, so this number must not be presented as a complete standalone
dependency count.

Two copy diagnostics expose omitted dependencies:

| Consumer in the copied rear history | Diagnostic | Implication |
|---|---|---|
| `RearAlignedM2PassageSketch` | External reference `e12` could not resolve `RearScrewAlignmentBinder` | The active sketch has an external-geometry dependency not represented by the 47-object traversal. |
| `RearEnvelopeSeamProfile`, `RearEnvelopeBackProfile` | Missing subobject `RearExteriorEnvelope.` | Their reference context is not available in the copied feature set. |
| `Sketch020` and `Sketch019` encountered during recursive copy | Missing external subelements from `Pocket016`, `Pad017`, and `AdditiveLoft` | The recursive copy follows additional generated geometry from the front-shell history. |

The saved document's Body groups confirm that `Sketch020` is owned by the front
shell (`Body`), while `RearScrewAlignmentBinder` is owned by the rear shell
(`Body002`) and has `Support = Sketch020`. Thus the relevant relationship is a
front-shell sketch reference, even though it was absent from the earlier Tip
`OutList` closure. The support sketch itself contains generated-geometry
references into front-shell features. The active downstream rear sketches use
the binder-generated geometry; a standalone rear document cannot simply omit
that reference and still claim a complete native feature-history recompute.

The four `WidthControlled_RearMatchedProfile*` sketches also retain Python
proxy links to the `ExteriorEnvelope` parameter object. Their feature histories
must preserve the proxy implementation and its parameter source; copying their
cached shapes would not meet the editable-component requirement.

## Disposable copy probes

Two probes were performed against `/tmp/remove-warp-bypass.FCStd`, leaving the
repository documents unchanged:

1. `Document.copyObject(47_objects, recursive=True, return_all=True)` followed
   by placing copied PartDesign objects in a new Body produced missing external
   geometry diagnostics. The probe was terminated before recomputation or save.
2. `Document.copyObject(RearBossWallRamps45, recursive=True, return_all=True)`
   alone followed generated-reference paths beyond the nominal closure and
   reported missing `RearExteriorEnvelope` subobjects. It was terminated before
   recomputation or save.

These failures are not evidence that the rear shell geometry is invalid. They
show that the current copy operation does not preserve the source sketch
reference context. A cached shape or a successful mesh comparison in the
monolith does not resolve this problem.

## Next safe step

Before another extraction attempt, make a property-level inventory of the
external geometry in `RearAlignedM2PassageSketch`, `RearEnvelopeSeamProfile`,
`RearEnvelopeBackProfile`, and the `WidthControlled_RearMatchedProfile*` proxy
objects. Identify the exact source Body and subelement for every external
reference, then test a complete minimal reference package in a disposable
document. The package must retain native sketches/proxies and their intended
parameter source while avoiding unrelated front-shell feature history.

Only proceed to a standalone rear Body after all external geometry references
resolve and the native feature chain recomputes, saves, closes, reopens, and
recomputes independently. If the required references necessarily pull in the
front shell's construction history, keep the current static interim assembly
representation and document that precise boundary rather than freezing the
rear Body.

## Validation limits

- The monolithic bypass's prior feature-level comparison and identical 0.05 mm
  Tip meshes remain valid evidence for that monolithic candidate.
- No standalone Body passed recomputation, save/reopen, portability, or
  master-driven propagation; those tests were not claimed.
- The source's suppressed historical `Pad022` issue remains separate from this
  extraction blocker.
- The existing modular assembly and original monolith remain unchanged.
