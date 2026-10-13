"""Tools for information about the systems, their partitions and reservations, and
the user.
"""

import cachetools.func
from fastmcp.tools import tool
from firecrest.v2 import Firecrest

from firecrest_mcp.tools.params import SystemName


class FirecrestStatusToolsMixin:
    client: Firecrest

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60 * 3)
    def systems(self) -> list[dict]:
        """Returns available systems."""
        return self.client.systems()

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60 * 3)
    def reservations(
        self,
        system_name: SystemName,
    ) -> list[dict]:
        """Returns reservations defined in the system."""
        return self.client.reservations(system_name)

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60 * 3)
    def partitions(
        self,
        system_name: SystemName,
    ) -> list[dict]:
        """Returns partitions defined in the system."""
        return self.client.partitions(system_name)

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60 * 3)
    def userinfo(self, system_name: SystemName) -> dict:
        """Returns user and groups information."""
        return self.client.userinfo(system_name)
