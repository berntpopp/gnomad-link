"""Simplified GraphQL client using centralized query system."""

from typing import Dict, Any, Optional

from .base_client import BaseGnomadClient, VariantNotFoundError
from gnomad_mcp.graphql import QueryBuilder


class GnomadApiClient(BaseGnomadClient):
    """Client for basic gnomAD API operations."""

    async def get_variant(self, variant_id: str, dataset: str) -> Dict[str, Any]:
        """Fetch variant data from gnomAD.

        Args:
            variant_id: The variant identifier (e.g., "1-55039447-G-T").
            dataset: The dataset to query (e.g., "gnomad_r4").

        Returns:
            Raw variant data from the API.

        Raises:
            VariantNotFoundError: If the variant is not found.
            GnomadApiError: For other API errors.
        """
        # Determine version from dataset
        version = QueryBuilder.get_version_for_dataset(dataset)

        # Execute query
        result = await self.execute_query(
            "variant", {"variantId": variant_id, "dataset": dataset}, version
        )

        # Check if variant was found
        if not result.get("variant"):
            raise VariantNotFoundError(
                f"Variant {variant_id} not found in dataset {dataset}"
            )

        return result
