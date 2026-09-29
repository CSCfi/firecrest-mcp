from typing import Annotated

from fastmcp.tools import tool
import cachetools.func


class FirecrestStatusToolsMixin:
    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60*3)
    def systems(self) -> list[dict]:
        """Returns available systems."""
        return self.client.systems()

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60*3)
    def nodes(
        self,
        system_name: Annotated[str, "the system name where the nodes belong to"],
    ) -> list[dict]:
        """Returns nodes of the system."""
        return self.client.nodes(system_name)

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60*3)
    def reservations(
        self,
        system_name: Annotated[str, "the system name where the reservations belong to"],
    ) -> list[dict]:
        """Returns reservations defined in the system."""
        return self.client.reservations(system_name)

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60*3)
    def partitions(
        self,
        system_name: Annotated[str, "the system name where the partitions belong to"],
    ) -> list[dict]:
        """Returns partitions defined in the system."""
        return self.client.partitions(system_name)

    @tool()
    @cachetools.func.ttl_cache(maxsize=2, ttl=60*3)
    def userinfo(self, system_name: Annotated[str, "the system name"]) -> dict:
        """Returns user and groups information."""
        return self.client.userinfo(system_name)
