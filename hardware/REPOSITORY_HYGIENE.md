## Published hardware history cleanup — 2026-11-25

The user authorized a hardware-only published-history rewrite. Historical
`hardware/` trees were removed and the selected current hardware snapshot restored
at engineering branch tips. All 27 branch names were retained. Every one of the
706 rewritten commits and every branch tip was checked for identical non-hardware
file trees. Firmware and other source content were not changed. Commit IDs may
change because of ancestry.

Historical candidate links and old commit IDs in prior reports are archival
references; remote branches no longer retain those experiments. Recovery is from
the verified complete offline bundle:

`/Users/davidcannan/Documents/Codex/archives/pendant-before-hardware-rewrite-20261125.bundle`

SHA-256: `9e6e67dad273199c20b932ecd11dfeb03908c21995e839eb75161f95d998830c`.

The separate pre-clean CAD archive remains available too. Do not push old local
branches or the backup bundle into this remote: doing so can restore the large
history. Preserve unpushed work before making a fresh clone in Working Copy or
other clients. Existing clones retain their old objects; fetching does not erase
them. Normal all-branch clones should receive only the retained hardware payload.

Earlier statements below describing remote recovery branches or a pending history
proposal describe the pre-rewrite state and are superseded by this section.


---

# CAD artifact audit — 2026-11-25

## Accepted source and preservation

The current remote already has a reduced-history hardware snapshot:
`hardware-integration-clean` at `9b7cb18`. This cleanup builds on that existing
snapshot; it does not recreate it, promote unaccepted experiments, or merge old
CAD history into it. The legacy engineering tip is `6db72e0`.

The eight selected FreeCAD documents retain their existing relative paths.
`freecad/README.md` records their roles. The original monolith is a protected
baseline, the small master stores shared parameters, four component documents
support the linked assembly, and the fused encoder handoff supports a later user
split. The assembly still contains four static interim shapes. Newer candidate
filenames on the legacy branch do not establish engineering acceptance.

No CAD binary, measurement, generator, KiCad source, or user-arranged 3MF was
changed by this policy cleanup. The firmware feature checkout and its untracked
FreeCAD backup and KiCad local history were left untouched. A separate worktree
was necessary to preserve that active firmware branch.

The existing 745 MiB recovery archive was rehashed and matches its recorded
SHA-256:

`/Users/davidcannan/Documents/Codex/archives/pendant-cad-pre-clean-branch-archive-2026-11-01.tar.gz`

`d317a86bc968d9a9d8aaa13d14b6d0aa42e9a7dcf25dfcfa0e05b276e78b37d9`

## Storage measurements

These are distinct measurements; the prior tree reduction predates this cleanup.

| Scope | Bytes | Approximate size |
| --- | ---: | ---: |
| Legacy remote hardware tree, 407 files | 468584297 | 447 MiB |
| Existing clean remote hardware tree, 328 files | 86383869 | 82 MiB |
| Retained eight FreeCAD documents | 70676203 | 67 MiB |
| All unique reachable historical blobs, all fetched refs | 2490998089 | 2.32 GiB uncompressed |
| Historical FreeCAD blobs, 135 versions | 2326868314 | 2.17 GiB uncompressed |

Before the remote refresh the shared local Git database occupied about 2.0 GiB;
after fetching current branch tips it occupies about 2.2 GiB (1.98 GiB loose
objects plus 216 MiB packed objects). These are local storage figures, not a
prediction of network transfer size. GitHub repository metadata reported about
629 MiB. This cleanup adds only text policy/documentation and does not reclaim
historical storage. The clean working directory occupies about 83 MiB on disk;
its CAD payload remains unchanged after this task.

The largest historical blob is the 67,411,088-byte encoder working document,
followed by the 65,817,113-byte monolith and many older 59–64 MB monolith versions.
This confirms accumulated CAD history, but does not diagnose the phone client's
memory-window error.

## Artifact lifecycle

1. Work in the existing source project. Place experimental geometry under ignored
   `.workbench/`, and generated exports under ignored `build/`.
2. Inspect dimensions, visible geometry, dependencies, and save/reopen behavior.
   Record unresolved validity or physical-fit issues.
3. Review significance before promoting source. No automatic CAD commits.
4. Keep the approved document inventory deliberate. The original 62.77 MiB
   monolith is an existing storage exception because shell histories are not yet
   fully migrated. The existing user-arranged 3MF is retained to preserve plate work.
5. Publish reviewed manufacturing exports separately through Releases or a
   deliberately configured LFS workflow. New binaries warn above 5 MiB, require
   justification above 10 MiB, and are blocked above 25 MiB in ordinary Git.

`hardware/scripts/validate_sources.py` checks the selected document inventory,
ZIP integrity, saved external document paths, required KiCad sources, and tracked
transient/generated files. CI runs it for PRs targeting the clean hardware branch.
It deliberately does not regenerate or modify CAD.

## Validation and limitations

The source inventory, all eight ZIP archives, and saved file dependencies passed
fresh inspection. The recovery archive checksum matched. CAD binaries match the
clean remote baseline byte-for-byte. Earlier native recompute and reversible
parameter checks are recorded in
[the migration report](freecad/reports/clean-branch-migration-validation-2026-11-01.md).

Host tests completed with 178 passes and 17 reported failures (including six
subtest failures) in deployment mount checks, hardware profiles, and host bridge
motion behavior. No firmware or tests changed in this cleanup. The test runner
needed the standard-library `code` module preloaded: the repository's CircuitPython
`code.py` shadows it and enters the application loop when pytest imports `pdb`.

Fresh headless FreeCAD validation succeeded (worker exit 0): a disposable copy
of the retained assembly cold-opened and recomputed; all five live links resolved
as valid single solids, and all four static interim shapes were valid single
solids. No project CAD files were saved or modified. This is assembly validation,
not full monolith-history regeneration or a physical-fit/manufacturing signoff.
The GUI RPC document endpoint failed and reports an add-on/protocol mismatch;
the independent headless worker avoided that endpoint. Electrical ERC was not run.

## Historical remediation proposal

No published refs were rewritten or deleted. Ordinary all-branch fetches continue
to include legacy CAD history. For a lightweight hardware checkout use the
single-branch command in `BRANCHING_AND_PUBLICATION.md`; firmware users should
select `main`. A shallow single-branch clone can further limit history when needed.

Before any future filter-repo/LFS migration, inventory every remote branch and tag,
release attachment, open PR, collaborator checkout, and commit-pinned link. Known
recovery refs include `hardware-integration`, `hardware/kicad`, and
`safety/hardware-integration-20261027-183929`. Rewriting would change commit IDs and
require coordinated reclones and link updates. Collaborators and release assets
have not been fully enumerated, so no destructive migration is ready for approval.
Retain the clean branch and external archive while preparing that separate plan.
