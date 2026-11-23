### LUMI

For anything not covered here, such as partitions, modules, software, billing or
quotas, search LUMI's documentation with the `retrieve_docs` tool. Check
`get_service_status` for maintenance breaks and outages. Both tools come from the LUMI
AI Factory MCP server. If they aren't available, tell the user that what you know about
LUMI may be out of date and suggest adding the server at
`https://lumi-aif-agents.2.rahtiapp.fi/mcp`.

LUMI-G nodes have AMD MI250X GPUs, so GPU code must target ROCm and HIP, not CUDA.
Slurm counts each MI250X as two GPUs, so a node has 8 GPUs, and only 56 of its 64
cores are usable. A job that asks for 64 cores per node never runs. On LUMI-C and
LUMI-G, `/tmp` is in RAM and counts against the job's memory. Lustre is shared by all
users and suffers under many small files, so use a container instead of a plain Conda
or pip environment.

`/project` and `/projappl` are the same directory. A path under one is allowed
wherever the config allows the other.
