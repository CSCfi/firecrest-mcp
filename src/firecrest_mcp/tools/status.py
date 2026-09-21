from typing import Annotated

from fastmcp.tools import tool


class FirecrestStatusToolsMixin:
    @tool()
    def systems(self) -> list[dict]:
        """Returns available systems."""
        return self.client.systems()

    @tool()
    def nodes(
        self,
        system_name: Annotated[str, "the system name where the nodes belong to"],
    ) -> list[dict]:
        """Returns nodes of the system."""
        return self.client.nodes(system_name)

    @tool()
    def reservations(
        self,
        system_name: Annotated[str, "the system name where the reservations belong to"],
    ) -> list[dict]:
        """Returns reservations defined in the system."""
        return self.client.reservations(system_name)

    @tool()
    def partitions(
        self,
        system_name: Annotated[str, "the system name where the partitions belong to"],
    ) -> list[dict]:
        """Returns partitions defined in the system."""
        return self.client.partitions(system_name)

    @tool()
    def userinfo(self, system_name: Annotated[str, "the system name"]) -> dict:
        """Returns user and groups information."""
        return self.client.userinfo(system_name)
