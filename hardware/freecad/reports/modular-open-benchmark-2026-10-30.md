# Modular assembly document-open benchmark

Date: 2026-10-30
Branch: `hardware-integration`
FreeCAD: 1.1.1 (`0108fd4b4850cc46e625b60e53cea7a7bbe69f8d`)

## Result

Two alternating trials in separate fresh `FreeCADCmd` processes measured `App.openDocument` without explicit recompute or save:

| Document | Median open time | File size | Loaded documents / objects |
|---|---:|---:|---:|
| Modular assembly | 0.468 s | 2,537,636 bytes | 6 / 178 |
| Original monolith | 5.330 s | 65,817,113 bytes | 1 / 816 |

The observed monolith-to-assembly open-time ratio was 11.38×. The modular load includes the assembly, master, and four component documents. The total tracked source bundle reported by the benchmark is 4,711,456 bytes.

## Scope and limits

Each run used a new process and the order alternated. The operating-system file cache was not flushed. This is evidence for saved-document open latency in the current environment only; it does not measure recomputation, rendering, or interactive editing performance, and it is not a guarantee for other computers. No CAD file was modified. CAD SHA-256 values before and after the run were unchanged:

- `pendant.FCStd`: `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`
- `pendant-modular-assembly.FCStd`: `d727c69f3e3bc68857fc29aa29438fc2a6f7a59954a6f64b3766d466fa57bbdb`
- `pendant-master.FCStd`: `a2990a24c9b4fa140e25c1c5ef721fe65a6cb36f48a55cc168a11778421e56cb`

Raw per-run records are in `modular-open-benchmark-2026-10-30.json`. Reproduce with:

```sh
python3 hardware/freecad/scripts/benchmark_document_open.py \
  --runs 2 --timeout 180 \
  --json /tmp/pendant-open-benchmark.json
```
