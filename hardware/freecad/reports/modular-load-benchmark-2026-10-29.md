# Modular assembly document-load benchmark

Date: 2026-10-29  
FreeCAD: 1.1.1  
Branch: `hardware-integration`

## Method

Ran three interleaved trials per document. Every trial used a fresh `freecadcmd` process. The timer covered `App.openDocument()`; it excluded FreeCAD process startup and did not explicitly recompute or save. Opening the assembly also loaded its relative linked documents. The operating-system file cache was not flushed, so these are repeatable warm-cache measurements rather than cold-start guarantees.

Run the bounded benchmark with:

```sh
python3 hardware/freecad/scripts/benchmark_document_open.py --runs 3 --timeout 170
```

Raw per-run data is in `modular-load-benchmark-2026-10-29.json`.

## Results

| Document opened | Median `openDocument` | File size | Loaded documents / objects |
| --- | ---: | ---: | ---: |
| Original monolith `pendant.FCStd` | 5.714 s | 65,817,113 bytes | 1 / 816 |
| `pendant-modular-assembly.FCStd` | 0.422 s | 2,545,943 bytes | 5 / 167 |

The assembly-open median was **13.6× faster** in this run. Its loaded document set was the assembly, master, display retainer, USB cover, and locator component document. Those five files total 4,705,387 bytes. The result measures saved-document loading only; it does not establish a 13.6× improvement in recomputation, viewport rendering, or interactive editing.

The assembly still contains six static BREP interim components. This benchmark demonstrates a loading advantage for the current modular assembly and its three editable linked sources; it does not claim that all pendant components have been modularized.

## Updated five-live-link assembly measurement

After the breakout-board Body was added as the fifth live Body link, the same three-run interleaved test was repeated on 2026-10-29. The script now includes all four linked component documents in its source-bundle byte count; the two locator Bodies share one component document.

| Document opened | Median `openDocument` | File size | Loaded documents / objects |
| --- | ---: | ---: | ---: |
| Original monolith `pendant.FCStd` | 5.232 s | 65,817,113 bytes | 1 / 816 |
| Current five-link assembly | 0.431 s | 2,544,667 bytes | 6 / 178 |

The measured ratio is **12.15× faster assembly document loading** in this warm-cache run. The assembly loads itself, the master, and four editable component source documents. The assembly and those five linked files total **4,718,768 bytes**. The five remaining shell/faceplate/encoder interim solids are static BREPs and do not add source documents to the load set. These measurements still cover only `App.openDocument()`; they do not measure recompute time, viewport rendering, or editing responsiveness. The original three-source result above is retained as the historical pre-breakout baseline.

The full raw run record is `modular-load-benchmark-five-link-2026-10-29.json`. The benchmark script accepts `--json PATH` to save a machine-readable record alongside its console output.
