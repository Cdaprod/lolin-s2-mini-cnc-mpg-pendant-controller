# Modular document open-time benchmark — five runs

Date: 2026-10-30  
Branch: `hardware-integration`  
Scope: saved-document loading only; no explicit recompute or save.

## Method

Ran `scripts/benchmark_document_open.py --runs 5 --timeout 170`. Each sample used a fresh FreeCADCmd process, opened either the modular assembly and its relative `App::Link` sources or the monolithic document, and timed `App.openDocument()` only. Document order alternated between runs. The operating-system file cache was not flushed. The production CAD documents were not saved.

## Results

| Document | Median | Range | File size | Loaded docs / objects |
|---|---:|---:|---:|---:|
| Modular assembly | 0.421 s | 0.414–0.466 s | 2,537,636 B | 6 / 178 |
| Monolith | 5.098 s | 5.053–5.164 s | 65,817,113 B | 1 / 816 |

The median monolith-to-assembly open-time ratio is **12.12×**. The assembly resolves the master and five linked source documents: breakout board, display retainer, faceplate locators, USB tethered cover, plus the assembly itself (six loaded documents including the master). The aggregate assembly/master/four editable source bundle remains 4,711,456 B.

## Limits

This five-run sample makes the load-time comparison more repeatable than the earlier two-run sample. It still measures only saved-document loading on this machine and does not measure recomputation, GUI viewport rendering, cold filesystem cache, interactive editing, or equivalent full editability; four physical items remain static interim BREP representations. No CAD source hashes changed during the benchmark.

Machine-readable individual runs: `modular-document-open-benchmark-5run-2026-10-30.json`.
