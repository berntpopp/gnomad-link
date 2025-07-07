#!/usr/bin/env python
"""Test the unified query system."""

import asyncio
from gnomad_mcp.graphql import QueryLoader, QueryBuilder


async def test_unified_system():
    """Test the unified system components."""

    print("Testing Unified gnomAD System\n")

    # Test 1: Query Loading
    print("1. Testing centralized query loading:")
    loader = QueryLoader()

    try:
        # Load variant query
        variant_query = loader.load_query("variant")
        print(f"   ✓ Loaded variant query ({len(variant_query)} chars)")
        print(f"     Fragment resolution: {'PopulationFields' in variant_query}")

        # Load gene query
        gene_query = loader.load_query("gene", "v4")
        print(f"   ✓ Loaded gene query ({len(gene_query)} chars)")

        # Load common query
        meta_query = loader.load_query("meta")
        print(f"   ✓ Loaded meta query ({len(meta_query)} chars)")

    except Exception as e:
        print(f"   ✗ Error loading queries: {e}")

    # Test 2: Query Builder
    print("\n2. Testing query builder:")
    builder = QueryBuilder()

    # Test dataset version mapping
    print(f"   gnomad_r4 -> {builder.get_version_for_dataset('gnomad_r4')}")
    print(f"   gnomad_r2_1 -> {builder.get_version_for_dataset('gnomad_r2_1')}")
    print(f"   gnomad_sv_r4 -> {builder.get_version_for_dataset('gnomad_sv_r4')}")

    # Test variable processing
    variables = builder.process_variables(
        "variant", {"variantId": "1-55039447-G-T", "dataset": "gnomad_r4"}
    )
    print(f"   ✓ Processed variant variables: {variables}")

    # Test 3: Available queries
    print("\n3. Available queries:")
    for version in ["v2", "v3", "v4", "common"]:
        queries = loader._list_available_queries(version)
        if queries:
            print(f"   {version}: {', '.join(sorted(queries))}")

    print("\n✅ Unified system test complete!")


if __name__ == "__main__":
    asyncio.run(test_unified_system())
