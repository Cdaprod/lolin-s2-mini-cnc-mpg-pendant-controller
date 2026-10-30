# Modular document open-time benchmark

Date: 2026-10-30  
Branch: `hardware-integration`  
Scope: read-only saved-document open benchmark; no recompute or save.

## Method

Ran `scripts/benchmark_document_open.py` with two interleaved fresh FreeCADCmd processes per document. Each measurement times `App.openDocument()` only; the assembly load follows its relative `App::Link` sources. No GUI viewport was opened and no explicit recompute or save was requested. Checksums for the monolith, master, and assembly were recorded before and after; they were unchanged.

## Results

| Document | Median open time | File size | Documents loaded | Total objects loaded |
|---|---:|---:|---:|---:|
| Monolithic `pendant.FCStd` | 4.950 s | 65,817,113 B | 1 | 816 |
| `pendant-modular-assembly.FCStd` | 0.429 s | 2,537,636 B | 6 | 178 |

The assembly open resolved the master and four editable source files: display retainer, USB tethered cover, faceplate locators, and breakout board. The assembly, master, and those four component files total 4,711,456 B. The measured monolith-to-assembly open-time ratio is 11.53×.

## Limits

This two-run sample demonstrates faster saved-document loading for the current linked assembly on this machine. It does not measure recomputation, GUI rendering, interactive editing, cold filesystem cache behavior, or equivalent full editability: four legacy physical components in the assembly remain static interim BREP shapes. It is not evidence that all modularization goals are complete.

Machine-readable raw runs: `modular-document-open-benchmark-2026-10-30.json`.
