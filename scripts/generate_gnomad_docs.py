#!/usr/bin/env python3
"""Generate comprehensive gnomAD GraphQL API documentation.

This script performs deep introspection of the gnomAD API and generates
well-structured, user-friendly documentation with complete type analysis.

Usage:
    python generate_gnomad_docs.py

This will:
1. Introspect the gnomAD GraphQL API schema
2. Analyze type relationships and dependencies
3. Generate multiple documentation files:
   - gnomad_graphql_api_reference.md - Main API reference
   - gnomad_type_reference.md - Detailed type documentation
   - gnomad_query_cookbook.md - Example queries organized by use case
   - gnomad_quick_start.md - Quick start guide for beginners
   - gnomad_graphql_schema.json - Raw schema data

Output:
    All files are saved to ../docs/gnomad_graphql/

Requirements:
    - httpx
    - Python 3.7+

Note:
    The script connects directly to https://gnomad.broadinstitute.org/api/
    No authentication is required.
"""

import asyncio
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx


class GnomADDocumentationGenerator:
    """Generate comprehensive documentation for the gnomAD GraphQL API.

    This class handles the entire documentation generation process:
    - Performs GraphQL introspection to get the complete schema
    - Analyzes relationships between types
    - Categorizes types into logical groups
    - Generates multiple markdown documentation files

    Attributes:
        url (str): The gnomAD GraphQL API endpoint
        schema_data (dict): Raw schema data from introspection
        type_relationships (defaultdict): Maps types to where they're used
        type_categories (dict): Categorization of types (unused, kept for future)
        predefined_categories (dict): Logical grouping of all gnomAD types
    """

    def __init__(self):
        """Initialize the documentation generator with gnomAD API endpoint."""
        self.url = "https://gnomad.broadinstitute.org/api/"
        self.schema_data = None
        self.type_relationships = defaultdict(list)  # Track which types use other types
        self.type_categories = {}

        # Pre-define categories for better organization
        self.predefined_categories = {
            "Core Variant Types": [
                "Variant",
                "VariantDetails",
                "VariantSequencingTypeData",
                "VariantJointSequencingTypeData",
                "VariantQualityMetrics",
            ],
            "Specialized Variant Types": [
                "MitochondrialVariant",
                "MitochondrialVariantDetails",
                "StructuralVariant",
                "StructuralVariantDetails",
                "CopyNumberVariant",
                "CopyNumberVariantDetails",
                "MultiNucleotideVariant",
                "MultiNucleotideVariantDetails",
            ],
            "Population & Frequency Data": [
                "VariantPopulation",
                "PopulationFrequency",
                "VariantFilteringAlleleFrequency",
                "VariantLocalAncestryPopulation",
                "MitochondrialVariantPopulation",
                "StructuralVariantPopulation",
                "CopyNumberVariantPopulation",
                "Fafmax",
                "VAGrpMaxFAF95",
            ],
            "Gene & Transcript Types": [
                "Gene",
                "Transcript",
                "Exon",
                "GeneTranscript",
                "TranscriptGene",
                "RegionGene",
                "RegionGeneTranscript",
                "ManeSelectTranscript",
            ],
            "Functional Annotation": [
                "TranscriptConsequence",
                "VariantInSilicoPredictor",
                "LoFCuration",
                "LoFCurationInGene",
                "MultiNucleotideVariantConsequence",
                "StructuralVariantConsequence",
            ],
            "Clinical & Disease Data": [
                "ClinVarVariant",
                "ClinVarVariantDetails",
                "ClinVarCondition",
                "ClinVarSubmission",
                "ClinVarVariantGnomadData",
                "GnomadInClinVar",
            ],
            "Constraint & Conservation": [
                "GnomadConstraint",
                "ExacConstraint",
                "GnomadV2RegionalMissenseConstraint",
                "GnomadV2RegionalMissenseConstraintRegion",
                "MitochondrialGeneConstraint",
                "MitochondrialRegionConstraint",
                "NonCodingConstraintRegion",
            ],
            "Quality Metrics": [
                "VariantSiteQualityMetric",
                "VariantGenotypeQuality",
                "VariantGenotypeDepth",
                "VariantAlleleBalance",
                "MitochondrialVariantGenotypeQualityMetric",
                "MitochondrialVariantSiteQualityMetric",
            ],
            "Coverage Data": [
                "Coverage",
                "VariantCoverage",
                "CoverageBin",
                "FeatureCoverage",
                "RegionCoverage",
                "MitochondrialCoverageBin",
                "CNVTrackCallableCoverageBin",
            ],
            "Expression & Tissue Data": [
                "GtexTissue",
                "PextRegion",
                "PextRegionTissue",
                "Pext",
            ],
            "Search & Utility Types": [
                "VariantSearchResult",
                "GeneSearchResult",
                "LiftoverVariant",
                "LiftoverResult",
                "Region",
                "BrowserMetadata",
            ],
            "Statistical & Analysis Types": [
                "VariantCooccurrence",
                "VariantCooccurrenceInPopulation",
                "HeterozygousVariantCooccurrenceCounts",
                "HomozygousVariantCooccurrenceCounts",
                "ContingencyTableTest",
                "CochranMantelHaenszelTest",
            ],
            "Variant Alliance Types": [
                "VAAllele",
                "VACohort",
                "VACohortAlleleFrequency",
                "VASequenceLocation",
                "VAQualityMeasures",
                "VAAncillaryResults",
            ],
            "Short Tandem Repeats": [
                "ShortTandemRepeat",
                "ShortTandemRepeatDetails",
                "ShortTandemRepeatGene",
                "ShortTandemRepeatAssociatedDisease",
                "ShortTandemRepeatReferenceRegion",
            ],
            "Histogram & Distribution Types": [
                "Histogram",
                "VariantAgeDistribution",
                "MitochondrialVariantAgeDistribution",
                "StructuralVariantAgeDistribution",
            ],
        }

    async def generate_all_documentation(self):
        """Generate all documentation files.

        This is the main entry point that orchestrates the entire documentation
        generation process. It performs the following steps:
        1. Introspects the GraphQL schema
        2. Analyzes type relationships
        3. Generates multiple documentation files
        4. Saves the raw schema

        The generated files are:
        - gnomad_graphql_api_reference.md: Main API reference with queries and types
        - gnomad_quick_start.md: Quick start guide for beginners
        - gnomad_type_reference.md: Detailed documentation of all types
        - gnomad_query_cookbook.md: Example queries for common use cases
        - gnomad_graphql_schema.json: Raw introspection data
        """
        print("🚀 Starting gnomAD API documentation generation...")

        # Perform introspection
        success = await self._introspect_schema()
        if not success:
            print("❌ Failed to introspect schema")
            return

        # Analyze type relationships
        self._analyze_type_relationships()

        # Generate different documentation files
        print("\n📝 Generating documentation files...")

        # 1. Main API reference
        api_ref = self._generate_api_reference()
        self._save_documentation("gnomad_graphql_api_reference.md", api_ref)

        # 2. Quick start guide
        quick_start = self._generate_quick_start_guide()
        self._save_documentation("gnomad_quick_start.md", quick_start)

        # 3. Type reference
        type_ref = self._generate_type_reference()
        self._save_documentation("gnomad_type_reference.md", type_ref)

        # 4. Query cookbook
        cookbook = self._generate_query_cookbook()
        self._save_documentation("gnomad_query_cookbook.md", cookbook)

        # Save schema
        self._save_schema()

        print("\n✅ Documentation generation complete!")

    async def _introspect_schema(self) -> bool:
        """Perform full schema introspection.

        Executes a comprehensive GraphQL introspection query to retrieve
        the complete schema including:
        - All queries available in the API
        - All types (objects, enums, scalars, etc.)
        - All fields with their descriptions and types
        - Arguments for queries and fields
        - Deprecation information

        Returns:
            bool: True if introspection succeeded, False otherwise
        """
        introspection_query = """
        query IntrospectionQuery {
          __schema {
            queryType {
              name
              fields {
                name
                description
                args {
                  name
                  description
                  type {
                    ...TypeRef
                  }
                  defaultValue
                }
                type {
                  ...TypeRef
                }
                isDeprecated
                deprecationReason
              }
            }
            types {
              ...FullType
            }
          }
        }

        fragment FullType on __Type {
          kind
          name
          description
          fields(includeDeprecated: true) {
            name
            description
            args {
              ...InputValue
            }
            type {
              ...TypeRef
            }
            isDeprecated
            deprecationReason
          }
          inputFields {
            ...InputValue
          }
          interfaces {
            ...TypeRef
          }
          enumValues(includeDeprecated: true) {
            name
            description
            isDeprecated
            deprecationReason
          }
          possibleTypes {
            ...TypeRef
          }
        }

        fragment InputValue on __InputValue {
          name
          description
          type {
            ...TypeRef
          }
          defaultValue
        }

        fragment TypeRef on __Type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                  ofType {
                    kind
                    name
                    ofType {
                      kind
                      name
                      ofType {
                        kind
                        name
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.url,
                    json={"query": introspection_query},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and "__schema" in data["data"]:
                        self.schema_data = data["data"]["__schema"]
                        return True

            except Exception as e:
                print(f"❌ Error during introspection: {e}")

        return False

    def _analyze_type_relationships(self):
        """Analyze relationships between types.

        Builds a map of type dependencies by examining which types
        reference other types in their fields. This helps understand
        the schema structure and generate better documentation.

        Updates self.type_relationships with entries like:
        {
            "VariantPopulation": [
                {"used_by": "Variant", "field": "populations", "kind": "field"},
                {"used_by": "VariantDetails", "field": "populations", "kind": "field"}
            ]
        }
        """
        for type_def in self.schema_data.get("types", []):
            if type_def["name"].startswith("__"):
                continue

            type_name = type_def["name"]

            # Analyze fields
            fields = type_def.get("fields") or []
            for field in fields:
                field_type = self._get_base_type_name(field["type"])
                if field_type and not field_type.startswith("__"):
                    self.type_relationships[field_type].append(
                        {"used_by": type_name, "field": field["name"], "kind": "field"}
                    )

    def _get_base_type_name(self, type_ref: dict[str, Any]) -> Optional[str]:
        """Extract the base type name from a type reference.

        GraphQL type references can be nested (e.g., [String!]!)
        This method recursively extracts the base type name.

        Args:
            type_ref: GraphQL type reference object

        Returns:
            The base type name (e.g., "String") or None
        """
        if type_ref.get("name"):
            return type_ref["name"]
        elif type_ref.get("ofType"):
            return self._get_base_type_name(type_ref["ofType"])
        return None

    def _format_type(self, type_ref: dict[str, Any]) -> str:
        """Format a type reference into a readable string.

        Converts GraphQL type references into human-readable format:
        - NON_NULL types: add ! suffix (e.g., String!)
        - LIST types: wrap in brackets (e.g., [String])
        - Nested types: handle recursively (e.g., [String!]!)

        Args:
            type_ref: GraphQL type reference object

        Returns:
            Formatted type string (e.g., "[String!]!")
        """
        if not type_ref:
            return "Unknown"

        kind = type_ref.get("kind", "")
        name = type_ref.get("name", "")

        if name:
            return name
        elif kind == "NON_NULL":
            inner = self._format_type(type_ref.get("ofType", {}))
            return f"{inner}!"
        elif kind == "LIST":
            inner = self._format_type(type_ref.get("ofType", {}))
            return f"[{inner}]"
        elif type_ref.get("ofType"):
            return self._format_type(type_ref["ofType"])
        else:
            return "Unknown"

    def _generate_api_reference(self) -> str:
        """Generate the main API reference documentation.

        Creates a comprehensive API reference with:
        - Table of contents
        - Overview and quick start
        - All available queries grouped by category
        - Data types organized by functional area
        - Enumerations
        - Best practices

        Returns:
            Complete markdown content for the API reference
        """
        lines = []

        # Header with navigation
        lines.extend(
            [
                "# gnomAD GraphQL API Reference",
                "",
                f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
                "",
                "## 📚 Table of Contents",
                "",
                "- [Overview](#overview)",
                "- [Quick Start](#quick-start)",
                "- [Available Queries](#available-queries)",
                "  - [Variant Queries](#variant-queries)",
                "  - [Gene Queries](#gene-queries)",
                "  - [Search Queries](#search-queries)",
                "  - [Clinical Data Queries](#clinical-data-queries)",
                "  - [Utility Queries](#utility-queries)",
                "- [Data Types](#data-types)",
                "- [Enumerations](#enumerations)",
                "- [Best Practices](#best-practices)",
                "",
                "---",
                "",
                "## Overview",
                "",
                "The gnomAD (Genome Aggregation Database) GraphQL API provides programmatic access to:",
                "",
                "- **🧬 Genetic Variants**: Population frequencies, functional annotations, quality metrics",
                "- **🧪 Clinical Data**: ClinVar annotations, disease associations, pathogenicity",
                "- **📊 Gene Information**: Constraint scores, expression data, transcript details",
                "- **🔍 Search Functions**: Find variants and genes by various criteria",
                "- **🛠️ Utilities**: Coordinate liftover, metadata, co-occurrence analysis",
                "",
                "### Available Datasets",
                "",
                "| Dataset | Reference | Samples | Description |",
                "|---------|-----------|---------|-------------|",
                "| `gnomad_r4` | GRCh38 | 807,162 | Latest release (v4.1) |",
                "| `gnomad_r3` | GRCh38 | 76,156 | Previous release (v3.1.2) |",
                "| `gnomad_r2_1` | GRCh37 | 141,456 | Legacy release (v2.1.1) |",
                "| `gnomad_sv_r4` | GRCh38 | - | Structural variants |",
                "| `gnomad_cnv_r4` | GRCh38 | - | Copy number variants |",
                "",
                "---",
                "",
                "## Quick Start",
                "",
                "### API Endpoint",
                "```",
                "POST https://gnomad.broadinstitute.org/api/",
                "Content-Type: application/json",
                "```",
                "",
                "### Basic Query Structure",
                "```graphql",
                "query {",
                '  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {',
                "    variant_id",
                "    genome {",
                "      af",
                "    }",
                "  }",
                "}",
                "```",
                "",
                "---",
                "",
                "## Available Queries",
                "",
            ]
        )

        # Group queries by category
        query_type = self.schema_data.get("queryType", {})
        queries = query_type.get("fields", [])

        query_categories = self._categorize_queries(queries)

        for category, category_queries in query_categories.items():
            if not category_queries:
                continue

            lines.append(f"### {category}")
            lines.append("")

            for query in sorted(category_queries, key=lambda x: x["name"]):
                lines.extend(self._document_query(query))
                lines.append("")

        # Data types section
        lines.extend(
            [
                "---",
                "",
                "## Data Types",
                "",
                "The API uses the following type categories:",
                "",
            ]
        )

        # Document types by category
        all_types = {
            t["name"]: t
            for t in self.schema_data.get("types", [])
            if not t["name"].startswith("__") and t["kind"] == "OBJECT"
        }

        for category, type_names in self.predefined_categories.items():
            category_types = [
                all_types[name] for name in type_names if name in all_types
            ]
            if category_types:
                lines.append(f"### {category}")
                lines.append("")

                # Add a summary table
                lines.append("| Type | Description | Key Fields |")
                lines.append("|------|-------------|------------|")

                for type_def in category_types:
                    name = type_def["name"]
                    desc = (type_def.get("description") or "").replace("\n", " ")[:80]
                    if len(desc) == 80:
                        desc += "..."

                    # Get key fields
                    fields = type_def.get("fields", [])
                    key_fields = []
                    for field in fields[:3]:  # First 3 fields
                        if not field["name"].startswith("_"):
                            key_fields.append(f"`{field['name']}`")

                    lines.append(
                        f"| [{name}](#type-{name.lower()}) | {desc} | {', '.join(key_fields)} |"
                    )

                lines.append("")

        # Enum section
        lines.extend(self._document_enums())

        # Best practices
        lines.extend(
            [
                "---",
                "",
                "## Best Practices",
                "",
                "### 1. Request Only Needed Fields",
                "```graphql",
                "# ❌ Bad - requests all fields",
                "query {",
                '  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {',
                "    ... on VariantDetails  # Don't use fragments for everything",
                "  }",
                "}",
                "",
                "# ✅ Good - requests only needed fields",
                "query {",
                '  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {',
                "    variant_id",
                "    genome { af }",
                "  }",
                "}",
                "```",
                "",
                "### 2. Use Appropriate Datasets",
                "- For GRCh38: Use `gnomad_r4` (latest) or `gnomad_r3`",
                "- For GRCh37: Use `gnomad_r2_1`",
                "- Match dataset to your reference genome",
                "",
                "### 3. Handle Errors Gracefully",
                "- Check for `errors` in response",
                "- Handle null results (variant not found)",
                "- Implement timeout handling",
                "",
                "### 4. Variant ID Format",
                "- Format: `chromosome-position-reference-alternate`",
                "- Example: `1-55516888-G-A`",
                "- Chromosome can be 1-22, X, Y, or MT",
                "",
                "---",
                "",
                "*For more examples, see the [Query Cookbook](gnomad_query_cookbook.md)*",
            ]
        )

        return "\n".join(lines)

    def _categorize_queries(
        self, queries: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Categorize queries for better organization.

        Groups queries into logical categories based on their names:
        - Variant Queries: variant data queries
        - Gene Queries: gene and transcript queries
        - Search Queries: search functionality
        - Clinical Data Queries: ClinVar related
        - Utility Queries: liftover, metadata, etc.

        Args:
            queries: List of query field definitions

        Returns:
            Dictionary mapping category names to lists of queries
        """
        categories = {
            "Variant Queries": [],
            "Gene Queries": [],
            "Search Queries": [],
            "Clinical Data Queries": [],
            "Utility Queries": [],
        }

        for query in queries:
            name = query["name"].lower()

            if "variant" in name and "search" not in name:
                if "clinvar" in name:
                    categories["Clinical Data Queries"].append(query)
                else:
                    categories["Variant Queries"].append(query)
            elif "gene" in name or "transcript" in name:
                if "search" in name:
                    categories["Search Queries"].append(query)
                else:
                    categories["Gene Queries"].append(query)
            elif "search" in name:
                categories["Search Queries"].append(query)
            elif "clinvar" in name:
                categories["Clinical Data Queries"].append(query)
            else:
                categories["Utility Queries"].append(query)

        return categories

    def _document_query(self, query: dict[str, Any]) -> list[str]:
        """Document a single query.

        Generates documentation for a query including:
        - Name and description
        - Return type
        - Arguments table (in collapsible section)
        - Example query (in collapsible section)

        Args:
            query: Query field definition from schema

        Returns:
            List of markdown lines documenting the query
        """
        lines = []
        name = query["name"]
        description = query.get("description") or "No description available"
        return_type = self._format_type(query["type"])

        lines.append(f"#### `{name}`")
        lines.append("")
        lines.append(f"{description}")
        lines.append("")
        lines.append(f"**Returns:** `{return_type}`")
        lines.append("")

        # Arguments
        args = query.get("args", [])
        if args:
            lines.append("<details>")
            lines.append("<summary><strong>Arguments</strong></summary>")
            lines.append("")
            lines.append("| Argument | Type | Required | Description |")
            lines.append("|----------|------|----------|-------------|")

            for arg in args:
                arg_name = arg["name"]
                arg_type = self._format_type(arg["type"])
                required = "!" in arg_type
                arg_desc = (arg.get("description") or "-").replace("\n", " ")

                lines.append(
                    f"| `{arg_name}` | `{arg_type}` | {'Yes' if required else 'No'} | {arg_desc} |"
                )

            lines.append("")
            lines.append("</details>")
            lines.append("")

        # Add example
        lines.append("<details>")
        lines.append("<summary><strong>Example</strong></summary>")
        lines.append("")
        lines.append("```graphql")
        lines.extend(self._generate_query_example(name, args))
        lines.append("```")
        lines.append("")
        lines.append("</details>")

        return lines

    def _generate_query_example(
        self, query_name: str, args: list[dict[str, Any]]
    ) -> list[str]:
        """Generate an example query.

        Creates a sample GraphQL query showing how to use a specific query.
        Automatically generates appropriate example values based on
        argument names and types.

        Args:
            query_name: Name of the query (e.g., "variant")
            args: List of argument definitions for the query

        Returns:
            List of lines forming a complete example query
        """
        lines = ["query {"]

        # Build arguments
        arg_parts = []
        for arg in args:
            arg_name = arg["name"]
            arg_type = self._format_type(arg["type"])

            # Generate example value
            if "variant" in arg_name.lower() or arg_name == "variantId":
                arg_parts.append(f'{arg_name}: "1-55516888-G-A"')
            elif arg_name == "dataset":
                arg_parts.append(f"{arg_name}: gnomad_r4")
            elif arg_name == "reference_genome":
                arg_parts.append(f"{arg_name}: GRCh38")
            elif arg_name == "gene_symbol":
                arg_parts.append(f'{arg_name}: "BRCA2"')
            elif arg_name == "gene_id":
                arg_parts.append(f'{arg_name}: "ENSG00000139618"')
            elif arg_name == "query":
                arg_parts.append(f'{arg_name}: "APOE"')
            elif "!" in arg_type:  # Required
                if "String" in arg_type:
                    arg_parts.append(f'{arg_name}: "example"')
                elif "Int" in arg_type:
                    arg_parts.append(f"{arg_name}: 123")
                elif "Boolean" in arg_type:
                    arg_parts.append(f"{arg_name}: true")

        if arg_parts:
            lines.append(f"  {query_name}({', '.join(arg_parts)}) {{")
        else:
            lines.append(f"  {query_name} {{")

        # Add sample fields based on query type
        if "variant" in query_name:
            lines.extend(["    variant_id", "    genome { af }"])
        elif "gene" in query_name:
            lines.extend(["    gene_id", "    symbol"])
        else:
            lines.append("    # Add fields here")

        lines.append("  }")
        lines.append("}")

        return lines

    def _document_enums(self) -> list[str]:
        """Document enum types.

        Generates documentation for all enumeration types in the schema.
        Enums are important for understanding valid values for arguments
        like dataset IDs and reference genomes.

        Returns:
            List of markdown lines documenting all enum types
        """
        lines = ["---", "", "## Enumerations", ""]

        enums = [
            t
            for t in self.schema_data.get("types", [])
            if t["kind"] == "ENUM" and not t["name"].startswith("__")
        ]

        for enum in sorted(enums, key=lambda x: x["name"]):
            name = enum["name"]
            description = enum.get("description", "")

            lines.append(f"### `{name}`")
            if description:
                lines.append(f"{description}")
            lines.append("")

            values = enum.get("enumValues", [])
            if values:
                lines.append("| Value | Description |")
                lines.append("|-------|-------------|")

                for value in values:
                    val_name = value["name"]
                    val_desc = value.get("description", "-")
                    deprecated = " *(deprecated)*" if value.get("isDeprecated") else ""
                    lines.append(f"| `{val_name}` | {val_desc}{deprecated} |")

            lines.append("")

        return lines

    def _generate_type_reference(self) -> str:
        """Generate detailed type reference documentation.

        Creates a comprehensive type reference that documents all
        object types in the schema, organized by category.
        Each type includes:
        - Description
        - Where it's used (from relationship analysis)
        - All fields with their types and descriptions

        Returns:
            Complete markdown content for the type reference
        """
        lines = [
            "# gnomAD Type Reference",
            "",
            "This document provides detailed information about all data types in the gnomAD GraphQL API.",
            "",
            "## Table of Contents",
            "",
        ]

        # Generate TOC
        for category in self.predefined_categories.keys():
            anchor = category.lower().replace(" ", "-").replace("&", "and")
            lines.append(f"- [{category}](#{anchor})")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Document each category
        all_types = {
            t["name"]: t
            for t in self.schema_data.get("types", [])
            if not t["name"].startswith("__")
        }

        documented_types = set()

        for category, type_names in self.predefined_categories.items():
            category_types = [
                all_types[name]
                for name in type_names
                if name in all_types and all_types[name]["kind"] == "OBJECT"
            ]

            if not category_types:
                continue

            lines.append(f"## {category}")
            lines.append("")

            for type_def in category_types:
                lines.extend(self._document_type_detailed(type_def))
                documented_types.add(type_def["name"])
                lines.append("")

        # Document remaining types
        remaining_types = [
            t
            for t in all_types.values()
            if t["name"] not in documented_types and t["kind"] == "OBJECT"
        ]

        if remaining_types:
            lines.append("## Other Types")
            lines.append("")
            lines.append("These types are used internally or in specific contexts:")
            lines.append("")

            for type_def in sorted(remaining_types, key=lambda x: x["name"]):
                lines.extend(self._document_type_detailed(type_def))
                lines.append("")

        return "\n".join(lines)

    def _document_type_detailed(self, type_def: dict[str, Any]) -> list[str]:
        """Generate detailed documentation for a type.

        Creates comprehensive documentation for a single type including:
        - Type name and description
        - Where the type is used (from relationship analysis)
        - All fields in a collapsible table
        - Field types and descriptions
        - Deprecation information

        Args:
            type_def: Type definition from the schema

        Returns:
            List of markdown lines documenting the type
        """
        lines = []
        name = type_def["name"]
        description = type_def.get("description", "")

        lines.append(f'### <a id="type-{name.lower()}"></a>`{name}`')
        lines.append("")

        if description:
            lines.append(f"{description}")
            lines.append("")

        # Show where this type is used
        if name in self.type_relationships:
            uses = self.type_relationships[name][:3]  # Show first 3
            if uses:
                lines.append(
                    "**Used by:** "
                    + ", ".join([f"`{u['used_by']}.{u['field']}`" for u in uses])
                )
                if len(self.type_relationships[name]) > 3:
                    lines.append(
                        f" and {len(self.type_relationships[name]) - 3} more..."
                    )
                lines.append("")

        # Document fields
        fields = type_def.get("fields", [])
        if fields:
            lines.append("<details>")
            lines.append("<summary><strong>Fields</strong></summary>")
            lines.append("")
            lines.append("| Field | Type | Description |")
            lines.append("|-------|------|-------------|")

            # Sort fields: required first, then alphabetical
            sorted_fields = sorted(
                fields,
                key=lambda f: ("!" not in self._format_type(f["type"]), f["name"]),
            )

            for field in sorted_fields:
                field_name = field["name"]
                field_type = self._format_type(field["type"])
                field_desc = (field.get("description") or "-").replace("\n", " ")
                deprecated = " *(deprecated)*" if field.get("isDeprecated") else ""

                # Highlight important fields
                if field_name in [
                    "variant_id",
                    "gene_id",
                    "transcript_id",
                    "af",
                    "ac",
                    "an",
                ]:
                    field_name = f"**{field_name}**"

                lines.append(
                    f"| {field_name} | `{field_type}` | {field_desc}{deprecated} |"
                )

            lines.append("")
            lines.append("</details>")

        return lines

    def _generate_quick_start_guide(self) -> str:
        """Generate a quick start guide.

        Creates a beginner-friendly guide that helps users get started
        with the gnomAD API in 5 minutes. Includes:
        - Basic setup code
        - Essential queries with examples
        - Common patterns
        - Tips and tricks

        Returns:
            Complete markdown content for the quick start guide
        """
        return """# gnomAD API Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### 1. Basic Setup

```python
import requests

# API endpoint
url = "https://gnomad.broadinstitute.org/api/"

# Helper function
def query_gnomad(query):
    response = requests.post(url, json={"query": query})
    return response.json()
```

### 2. Your First Query - Get Variant Frequency

```python
# Get allele frequency for a variant
query = '''
{
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome {
      af
      ac
      an
    }
  }
}
'''

result = query_gnomad(query)
print(f"Allele frequency: {result['data']['variant']['genome']['af']}")
```

### 3. Essential Queries

#### Get Gene Constraint Scores
```graphql
{
  gene(gene_symbol: "BRCA2", reference_genome: GRCh38) {
    symbol
    gnomad_constraint {
      pLI
      oe_lof
      oe_lof_lower
      oe_lof_upper
    }
  }
}
```

#### Search for Variants in a Gene
```graphql
{
  variant_search(query: "APOE", dataset: gnomad_r4) {
    variant_id
    af
    consequence
  }
}
```

#### Get ClinVar Annotations
```graphql
{
  clinvar_variant(variant_id: "7-117559590-ATCT-A", reference_genome: GRCh38) {
    clinical_significance
    review_status
    conditions {
      name
    }
  }
}
```

#### Liftover Coordinates
```graphql
{
  liftover(source_variant_id: "17-7577121-G-A", reference_genome: GRCh37) {
    liftover {
      variant_id
      reference_genome
    }
  }
}
```

### 4. Common Patterns

#### Pattern 1: Get Population-Specific Frequencies
```graphql
{
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    genome {
      populations {
        id
        af
      }
    }
  }
}
```

#### Pattern 2: Get Functional Predictions
```graphql
{
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    transcript_consequences {
      gene_symbol
      consequence
      polyphen_prediction
      sift_prediction
      lof
    }
  }
}
```

### 5. Tips & Tricks

1. **Variant ID Format**: `chromosome-position-reference-alternate`
   - Example: `1-55516888-G-A`

2. **Choose the Right Dataset**:
   - `gnomad_r4`: Latest, GRCh38
   - `gnomad_r2_1`: Legacy, GRCh37

3. **Request Only What You Need**:
   - Don't request all fields
   - Use specific field selection

4. **Handle Nulls**:
   - Variants may not exist in all datasets
   - Some fields may be null

### 6. Next Steps

- [Full API Reference](gnomad_graphql_api_reference.md)
- [Query Cookbook](gnomad_query_cookbook.md)
- [Type Reference](gnomad_type_reference.md)
"""

    def _generate_query_cookbook(self) -> str:
        """Generate a cookbook of useful queries.

        Creates a collection of ready-to-use queries organized by use case:
        - Population genetics queries
        - Clinical genetics queries
        - Research queries
        - Advanced patterns

        Each query includes context about when and how to use it.

        Returns:
            Complete markdown content for the query cookbook
        """
        return """# gnomAD Query Cookbook

## 🍳 Ready-to-Use Query Recipes

### Population Genetics Queries

#### Get Variant with All Population Frequencies
```graphql
query GetVariantPopulations($variantId: String!, $dataset: DatasetId!) {
  variant(variantId: $variantId, dataset: $dataset) {
    variant_id
    reference_genome

    # Overall frequencies
    genome {
      af
      ac
      an
      ac_hom
      ac_hemi

      # Population breakdown
      populations {
        id
        af
        ac
        an
        ac_hom
        ac_hemi
      }
    }

    # Exome frequencies (if available)
    exome {
      af
      populations {
        id
        af
      }
    }
  }
}
```

#### Find Rare Variants in a Gene
```graphql
query FindRareVariants($gene: String!, $dataset: DatasetId!) {
  variant_search(query: $gene, dataset: $dataset) {
    variant_id
    af
    consequence
    hgvsp
  }
}

# Then filter client-side for af < 0.001
```

### Clinical Genetics Queries

#### Get Complete Clinical Information
```graphql
query GetClinicalData($variantId: String!, $dataset: DatasetId!, $referenceGenome: ReferenceGenomeId!) {
  # gnomAD data
  variant(variantId: $variantId, dataset: $dataset) {
    variant_id
    rsid
    genome { af }

    transcript_consequences {
      gene_symbol
      consequence
      hgvsc
      hgvsp
      polyphen_prediction
      sift_prediction
      lof
      lof_filter
    }
  }

  # ClinVar data
  clinvar_variant(variant_id: $variantId, reference_genome: $referenceGenome) {
    clinical_significance
    review_status
    last_evaluated

    conditions {
      name
      medgen_id
      omim_id
    }

    submissions {
      clinical_significance
      review_status
      submitter_name
      conditions {
        name
      }
    }
  }
}
```

#### Get Gene Constraint for Disease Gene List
```graphql
query GetConstraintScores($genes: [String!]!, $referenceGenome: ReferenceGenomeId!) {
  gene1: gene(gene_symbol: $genes[0], reference_genome: $referenceGenome) {
    ...GeneConstraint
  }
  gene2: gene(gene_symbol: $genes[1], reference_genome: $referenceGenome) {
    ...GeneConstraint
  }
  # Repeat for each gene...
}

fragment GeneConstraint on Gene {
  symbol
  gnomad_constraint {
    pLI
    oe_lof
    oe_lof_lower
    oe_lof_upper
    oe_mis
    oe_mis_lower
    oe_mis_upper
  }
}
```

### Structural Variant Queries

#### Get Structural Variants in a Region
```graphql
query GetSVsInRegion($chrom: String!, $start: Int!, $stop: Int!, $dataset: StructuralVariantDatasetId!) {
  region(chrom: $chrom, start: $start, stop: $stop) {
    structural_variants(dataset: $dataset) {
      variant_id
      chrom
      pos
      end
      length
      type
      populations {
        id
        af
      }
    }
  }
}
```

### Research Queries

#### Compare Frequencies Across Datasets
```graphql
query CompareDatasets($variantId: String!) {
  v4: variant(variantId: $variantId, dataset: gnomad_r4) {
    genome { af }
  }

  v3: variant(variantId: $variantId, dataset: gnomad_r3) {
    genome { af }
  }

  v2: variant(variantId: $variantId, dataset: gnomad_r2_1) {
    genome { af }
  }
}
```

#### Get Mitochondrial Variant with Haplogroups
```graphql
query GetMitoVariant($variantId: String!, $dataset: DatasetId!) {
  mitochondrial_variant(variant_id: $variantId, dataset: $dataset) {
    variant_id

    # Overall frequencies
    ac_hom
    ac_het
    an
    af_hom
    af_het

    # Haplogroup distribution
    haplogroups {
      id
      ac_hom
      ac_het
      an
      af_hom
      af_het
    }

    # Population distribution
    populations {
      id
      ac_hom
      ac_het
      an
    }
  }
}
```

### Advanced Patterns

#### Batch Query Multiple Variants
```graphql
query BatchVariants {
  var1: variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    ...VariantInfo
  }
  var2: variant(variantId: "2-234567890-C-T", dataset: gnomad_r4) {
    ...VariantInfo
  }
  var3: variant(variantId: "3-123456789-A-G", dataset: gnomad_r4) {
    ...VariantInfo
  }
}

fragment VariantInfo on VariantDetails {
  variant_id
  genome { af }
  transcript_consequences {
    gene_symbol
    consequence
  }
}
```

#### Get Variant with Coverage Information
```graphql
query GetVariantWithCoverage($variantId: String!, $dataset: DatasetId!) {
  variant(variantId: $variantId, dataset: $dataset) {
    variant_id
    genome { af }

    # Coverage at this position
    coverage {
      genome {
        mean
        median
        over_20
      }
    }
  }
}
```

### Utility Queries

#### Get All Available Datasets
```graphql
query GetDatasets {
  meta {
    datasets {
      gnomad_r4 {
        label
        reference_genome
        sample_count
      }
      gnomad_r3 {
        label
        reference_genome
        sample_count
      }
      gnomad_r2_1 {
        label
        reference_genome
        sample_count
      }
    }
  }
}
```

#### Check Variant Co-occurrence
```graphql
query CheckCooccurrence($variant1: String!, $variant2: String!, $dataset: DatasetId!) {
  variant_cooccurrence(
    variants: [$variant1, $variant2]
    dataset: $dataset
  ) {
    variant_ids
    genotype_counts {
      genotype
      count
    }
  }
}
```

## 📝 Query Tips

1. **Use Fragments** for repeated structures
2. **Alias Fields** when querying multiple items
3. **Request Only Needed Fields** to improve performance
4. **Handle Null Results** - not all variants exist in all datasets
5. **Check Rate Limits** - implement appropriate delays

## 🔗 Related Documentation

- [API Reference](gnomad_graphql_api_reference.md)
- [Type Reference](gnomad_type_reference.md)
- [Quick Start Guide](gnomad_quick_start.md)
"""

    def _save_documentation(self, filename: str, content: str):
        """Save documentation to file.

        Saves the generated documentation to the docs/gnomad_graphql directory.
        Creates the directory if it doesn't exist.

        Args:
            filename: Name of the file to save (e.g., "api_reference.md")
            content: Markdown content to write to the file
        """
        docs_dir = Path("/mnt/c/development/scholl-lab/gnomad-link/docs/gnomad_graphql")
        docs_dir.mkdir(parents=True, exist_ok=True)

        filepath = docs_dir / filename
        with open(filepath, "w") as f:
            f.write(content)

        print(f"✅ Saved: {filename}")

    def _save_schema(self):
        """Save the raw schema.

        Saves the complete introspection result as JSON.
        This raw schema data can be useful for:
        - Debugging documentation issues
        - Understanding the full schema structure
        - Building additional tools
        """
        docs_dir = Path("/mnt/c/development/scholl-lab/gnomad-link/docs/gnomad_graphql")
        schema_path = docs_dir / "gnomad_graphql_schema.json"

        with open(schema_path, "w") as f:
            json.dump(self.schema_data, f, indent=2)

        print("✅ Saved: gnomad_graphql_schema.json")


async def main():
    """Run the documentation generator.

    Entry point for the script. Creates a generator instance
    and runs the documentation generation process.

    To run:
        python generate_gnomad_docs.py
    """
    generator = GnomADDocumentationGenerator()
    await generator.generate_all_documentation()


if __name__ == "__main__":
    asyncio.run(main())
