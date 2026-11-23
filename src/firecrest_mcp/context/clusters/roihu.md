### Roihu

For anything not covered here, such as partitions, modules, software or quotas, search
CSC's documentation with the `search_csc_docs` tool from the CSC Documentation MCP
server. If it isn't available, tell the user that what you know about Roihu may be out
of date and suggest adding the server at `https://mcp.docs.csc.fi`.

Roihu replaces Puhti and Mahti. Many partition names and much of the software are the
same, but limits, hardware, module names and some job options differ, so look them up
for Roihu.

Roihu has two FirecREST systems with different CPU architectures. `cpu` runs the CPU
partitions on x86_64 and `gpu` runs the GPU partitions on aarch64. Submit each job to
the system that matches its partition, and build software, including Python
environments and containers with native code, on the side where it will run.

Every node has local NVMe storage in `$TMPDIR` without `--gres=nvme`, and
`$LOCAL_SCRATCH` is not a replacement for it. Lustre is shared by all users and suffers
under many small files, so stage such data in `$TMPDIR` and copy the results back
before the job ends.
