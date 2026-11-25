# Faceplate locator passage: shared master parameter

Date: 2026-10-30
Branch: `hardware-integration`

The two faceplate locator screw-passage radii now use the existing shared master alias `InternalHardware.ShellMountPassageDiameter / 2`. The baseline remains 2.30 mm diameter. Only `LocatorPassageProfile0.Constraints[2]` and `LocatorPassageProfile1.Constraints[2]` changed; the native sketches, feature order, seat dimensions, placements, and Body tips were preserved.

## Validation

- At the nominal 2.30 mm master value, both parameterized candidate Bodies had valid zero-volume symmetric difference against the saved pre-change Bodies.
- A disposable cold-start test changed the shared diameter 2.30 → 2.32 → 2.30 mm. Each locator remained a valid one-solid PartDesign Body, its feature history recomputed, and its assembly `App::Link` matched the source Body by volume and bounding box.
- At 2.32 mm, each locator Body volume changed from about 88.29496 to 88.09902 mm³. Restoring 2.30 mm returned both Bodies and links to baseline; the restored Boolean symmetric differences were valid and zero.
- The refresh workflow saved/reopened the assembly in baseline, changed, and restored states. Both expressions remained valid after reopening.
- A before/after native-document inventory found the same 30 objects, unchanged feature and sketch inventory, constraints, sketch geometry, placements, and Body Tips; only the two intended external expressions were added.
- A fresh read-only open of the canonical modular assembly confirmed both links still match their one-solid source Bodies at the restored baseline.

The 2.32 mm value is only a reversible propagation test. It is not a design recommendation, and this parameterization does not validate screw fit or alter the locator seat geometry. The master, assembly, and original monolithic pendant were not modified. The original locator component was backed up outside the worktree before the validated candidate replaced it; the backup is `/tmp/faceplate-locators-before-passage-parameterization-20261029-224423.FCStd`.

Machine-readable metrics and file hashes are in `faceplate-locator-shared-passage-propagation-2026-10-30.json`.
