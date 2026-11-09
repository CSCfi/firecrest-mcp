### Roihu

Roihu has separate CPU and GPU architectures:
 - Roihu-CPU: x86_64, Zen 5, AVX-512
 - Roihu-GPU: aarch64, Grace CPU + Hopper H100

Lustre is shared by both: files are shared, binaries are not. Software (incl.
Python envs and containers with native code) must be built and run on the same
architecture.

CPU partitions:
| Partition | Type | Time | Nodes | CPUs | Memory | Notes |
|---|---|---|---|---|---|---|
| `test` | R | 15 min | 1–2 | 384/node | 744 GiB/node | |
| `small` | R | 72 h | 1 | 384/job | 1500 GiB/job | default workhorse |
| `medium` | N | 36 h | 1–6 | 384/node | 744 GiB/node | full nodes only |
| `large` | N | 36 h | 6–60 | 384/node | 744 GiB/node | needs approved scalability test |
| `longrun` | R | 10 days | 1 | 192/job | 1500 GiB/job | use shorter if you can |
| `hugemem` | C | 36 h | 1 | 128/job | 6037 GiB/job | |
| `hugemem_longrun` | C | 10 days | 1 | 128/job | 6037 GiB/job | |
| `interactive` | R | 36 h | 1 | 32/job | 64 GiB/job | for `sinteractive` |

GPU partitions (217 GiB memory/GPU):
| Partition | Type | Time | Nodes | GPUs | Notes |
|---|---|---|---|---|---|
| `gputest` | G | 15 min | 1–2 | 1–4/node | |
| `gpumedium` | G | 36 h | 1–4 | 1–4/job | |
| `gpularge` | G | 36 h | 1–10 | min 4, 4/node | needs scalability test + GPU-utilization evidence |
| `gpuinteractive` | G | 12 h | 1 | slices (1/7 GH200, 12 GiB) | memory TBA |

**Respect the file systems.** Lustre (`/scratch`, `/projappl`, home) is built for
parallel I/O on large files and melts under small-file/metadata load. Hundreds
of files: fine; thousands: pay attention; hundreds of thousands: don't. For
I/O-heavy or many-small-file work, **stage onto the node-local NVMe `$TMPDIR`**
(automatic, free, wiped when the job ends; copy results back).
