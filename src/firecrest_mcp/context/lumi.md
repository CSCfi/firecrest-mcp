### LUMI

LUMI partitions, all x86_64:
 - LUMI-C: 2x AMD EPYC Milan (Zen 3, AVX2, no AVX-512), 128 cores / 256 threads, 224 GiB/node
 - LUMI-G: 4x AMD MI250X = 8 GCDs/node, 56 usable cores, 480 GiB/node
 - LUMI-D: `largemem` (~4 TB/node), `lumid` (8x NVIDIA A40/node, visualisation)

Lustre is shared everywhere and CPU binaries run on both C and G. GPU code must
target ROCm/HIP, not CUDA; each GCD is a separate GPU. Per GCD use ≤7 cores and
≤60 GB. CPU-GPU binding needs full nodes (`standard-g` or `--exclusive`).
Slurm counts threads as CPUs. Default time limit is 1 min: always set `--time`.

Type: N = whole nodes, R = shared/partial nodes.

LUMI-C:
| Partition | Type | Time | Nodes | CPUs | Memory | Notes |
|---|---|---|---|---|---|---|
| `debug` | R | 30 min | 1–4 | 256/node | 224 GiB/node | quick tests |
| `interactive` | R | 8 h | 1 | 256/node | 1750 MB/CPU | |
| `small` | R | 3 days | 1–4 | 256/node | up to ~1 TB/node | serial, partial node |
| `standard` | N | 2 days | 1–512 | 256/node | 224 GiB/node | main multi-node |

LUMI-G (default mem 64 GiB/node in R partitions, set `--mem`):
| Partition | Type | Time | Nodes | GCDs | Notes |
|---|---|---|---|---|---|
| `dev-g` | R | 3 h | 1–32 | 1–8/node | debugging only |
| `small-g` | R | 3 days | 1–4 | 1–8/node | |
| `standard-g` | N | 2 days | 1–1024 | 8/node | |

LUMI-D:
| Partition | Type | Time | Nodes | Notes |
|---|---|---|---|---|
| `largemem` | N | 1 day | 1 | 256 CPUs, ~4 TB |
| `lumid` | R | 12 h | 1 | 8 A40s, 2000 GiB, local NVMe |

**Respect the file systems.** Lustre (`/scratch/<project>`, `/project/<project>`,
`/flash/<project>`, home) suffers under small-file/metadata load and is shared.
Avoid many small files (e.g. plain Conda; use containers or squashfs).
**LUMI-C/G nodes have no local disk: `/tmp` is in RAM and counts against job
memory.** For I/O-heavy work use `/flash/<project>` (billed 3x) and copy results
back to `/scratch` or `/project`.

`/project` and `/projappl` are the same directory. A path under one is allowed
wherever the config allows the other.
