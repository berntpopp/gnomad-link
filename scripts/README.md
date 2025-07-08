# Scripts Directory

This directory contains utility scripts for the gnomAD MCP project.

## generate_gnomad_docs.py

A comprehensive documentation generator for the gnomAD GraphQL API.

### Purpose

This script automatically generates up-to-date documentation for the gnomAD GraphQL API by:
1. Performing GraphQL introspection to retrieve the complete schema
2. Analyzing type relationships and dependencies
3. Generating well-structured, user-friendly documentation

### Usage

```bash
python generate_gnomad_docs.py
```

### Output

The script generates the following files in `../docs/gnomad_graphql/`:

| File | Description |
|------|-------------|
| `gnomad_graphql_api_reference.md` | Main API reference with all queries, types, and enums |
| `gnomad_type_reference.md` | Detailed documentation of all 126+ GraphQL types |
| `gnomad_query_cookbook.md` | Ready-to-use example queries organized by use case |
| `gnomad_quick_start.md` | 5-minute beginner's guide to using the API |
| `gnomad_graphql_schema.json` | Raw introspection data for reference |

### Features

- **Automatic categorization**: Groups 126+ types into 15 logical categories
- **Relationship tracking**: Shows where each type is used in the schema
- **Smart examples**: Generates appropriate example values for queries
- **Collapsible sections**: Uses markdown details tags for cleaner docs
- **Complete coverage**: Documents all queries, types, enums, and fields

### Requirements

- Python 3.7+
- httpx

Install requirements:
```bash
pip install httpx
```

### How It Works

1. **Introspection**: Sends a comprehensive introspection query to gnomAD's GraphQL endpoint
2. **Analysis**: 
   - Extracts all queries, types, and enums from the schema
   - Analyzes which types reference other types
   - Categorizes types into logical groups
3. **Generation**:
   - Creates markdown documentation with proper formatting
   - Generates examples based on field names and types
   - Adds navigation and cross-references

### Type Categories

The script organizes types into these categories:
- Core Variant Types
- Specialized Variant Types  
- Population & Frequency Data
- Gene & Transcript Types
- Functional Annotation
- Clinical & Disease Data
- Constraint & Conservation
- Quality Metrics
- Coverage Data
- Expression & Tissue Data
- Search & Utility Types
- Statistical & Analysis Types
- Variant Alliance Types
- Short Tandem Repeats
- Histogram & Distribution Types

### Maintenance

Run this script periodically to keep documentation up-to-date with the latest gnomAD API changes.

### Example Documentation Output

The generated API reference includes:

```markdown
#### `variant`

Query variant data from gnomAD.

**Returns:** `VariantDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variantId` | `String` | No | Variant ID in chr-pos-ref-alt format |
| `dataset` | `DatasetId!` | Yes | gnomAD dataset to query |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

</details>
```

### Troubleshooting

If the script fails:
1. Check internet connection to https://gnomad.broadinstitute.org
2. Verify the API endpoint is accessible
3. Check for any GraphQL errors in the response
4. Ensure write permissions to the docs directory