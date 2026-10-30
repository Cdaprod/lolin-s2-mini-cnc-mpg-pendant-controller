# Top hanger propagation trace — partial, timed out

Date: 2026-10-30  
Branch: `hardware-integration` at `e26de2e`  
Source: `hardware/freecad/pendant.FCStd` (SHA-256 `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`)  
Candidate: disposable byte-for-byte copy under `/tmp/pendant-hanger-chain-propagation-20261030/`; not saved.

## Purpose and result

Repeated the small reversible hanger-profile perturbation in a fresh disposable copy to locate the first downstream feature that stops propagating. `SlotWidth` changed from 3.0 to 3.1 mm and `SlotCenterY` from 81.0 to 81.05 mm, holding the lower profile edge at Y=80.5 mm. FreeCADCmd was terminated by its external 170-second limit while recomputing `FrontFullWidthReceiver`.

The two profile sketches recomputed in milliseconds. The front pocket recompute completed in 2.87 s and changed its cached volume from 40,859.1678 to 40,840.1329 mm³. The rear pocket completed but took 82.05 s; its volume changed from 38,207.2519 to 38,187.7641 mm³. During dependency propagation, `RearFullWidthReceiver` changed to a candidate volume of 38,540.3190 mm³ and retained `Touched` state. An explicit recompute of that receiver took 8.22 s. The run then stalled in `FrontFullWidthReceiver` until timeout.

This run did not complete the front receiver, either boss-to-wall load-path feature, downstream transitions, or either Body Tip. It did not save the candidate and did not perform a cold reopen. Therefore it neither proves nor refutes propagation to the final shell Tips. In particular, the `Touched` state on receiver features and the timeout do not by themselves distinguish stale cache from slow cross-Body recomputation.

## What the earlier evidence still says

The previous controlled feature-level candidate recorded the receiver changes but no change in `FrontBossToWallLoadPaths` or `RearBossToWallLoadPaths`. Metadata inspection found these are generic `PartDesign::Feature` stored-shape objects with `BaseFeature` links but no Python proxy, `RegenerationScript`, or `RegenerationMethod`. `RearBossShoulderTransitions` is also stored geometry with no regeneration method; its notes report that native Chamfer recompute was invalid. Separate scripts exist for downstream `FrontHighToLowTransitions` and `RearBossWallRamps45`, but not for generating the two boss-to-wall inputs.

That combination makes a missing persisted construction recipe the most actionable blocker, but the present timeout provides no new confirmation beyond the earlier controlled test. The exact first failing recompute boundary in a complete fresh run remains unresolved.

## Disposition and next action

The dimensional candidate remains disposable and is not a design proposal. No production CAD was changed; the monolith, master, assembly, and component hashes were rechecked unchanged. Do not repeat this full-history recompute unchanged. Recover the source profiles, loft construction, clipping envelopes, and clearances for the two generic load-path features in a small isolated context. Then add a reproducible regeneration method and test local downstream propagation before attempting one bounded end-to-end two-shell test. Preserve the closed opening. Do not claim load capacity: the user specified PLA, flat broad-face printing, and a 5× assembled-mass proof target, but the complete pendant mass and exact bracket load/contact remain unmeasured.

The machine-readable run record, including available raw feature snapshots, is `top-hanger-chain-trace-partial-2026-10-30.json`.
