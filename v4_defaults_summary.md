# v4 Default Configuration Summary

All components of the gnomAD MCP system now default to v4 (the latest version) wherever applicable.

## Default Values

### Datasets
- **GnomadDataset**: `gnomad_r4` (v4) is the default
- **StructuralVariantDataset**: `gnomad_sv_r4` (v4) is the default
- **ReferenceGenome**: `GRCh38` is the default (used by v3 and v4)

### API Version Mapping
```python
DATASET_VERSIONS = {
    "gnomad_r2_1": "v2",
    "gnomad_r3": "v3",
    "gnomad_r4": "v4",        # Default dataset
    "gnomad_sv_r2_1": "v2",
    "gnomad_sv_r4": "v4",     # Default SV dataset
    "gnomad_cnv_r4": "v4",
}
```

## Components with v4 Defaults

### 1. GraphQL Query System
- `QueryLoader.load_query()` - defaults to `version="v4"`
- `QueryBuilder.get_version_for_dataset()` - returns `"v4"` for unknown datasets
- `BaseGnomadClient.execute_query()` - defaults to `version="v4"`

### 2. Unified API Client
All methods default to gnomad_r4 dataset:
- `get_variant(dataset="gnomad_r4")`
- `search_variants(dataset="gnomad_r4")`
- `get_mitochondrial_variant(dataset="gnomad_r4")`
- `get_region(dataset="gnomad_r4")`
- `get_gene_variants(dataset="gnomad_r4")`

### 3. FastAPI Routes
All routes use enum types with defaults:
- **Variant routes**: `GnomadDataset` (defaults to gnomad_r4 in Query parameters)
- **Gene routes**: `GnomadDataset` (defaults to gnomad_r4) and `ReferenceGenome` (defaults to GRCh38)
- **Search routes**: `GnomadDataset` (defaults to gnomad_r4) and `ReferenceGenome` (defaults to GRCh38)
- **Region routes**: `GnomadDataset` (defaults to gnomad_r4)
- **ClinVar routes**: `ReferenceGenome` (defaults to GRCh38)
- **Transcript routes**: `ReferenceGenome` (defaults to GRCh38)

### 4. MCP Server
- `get_variant_allele_frequency(dataset="gnomad_r4")` - defaults to gnomad_r4

### 5. Services
- `UnifiedFrequencyService.get_variant_frequencies(dataset="gnomad_r4")`

## Usage Examples

### FastAPI (with defaults)
```bash
# Uses gnomad_r4 by default
curl http://127.0.0.1:8000/search/variant?query=rs1234567

# Uses GRCh38 by default
curl http://127.0.0.1:8000/gene/?gene_symbol=BRCA1

# Uses gnomad_r4 by default
curl http://127.0.0.1:8000/region/?chrom=1&start=55039000&stop=55040000
```

### MCP (with defaults)
```python
# Uses gnomad_r4 by default
result = await get_variant_allele_frequency("1-55039447-G-T")
```

### Python API (with defaults)
```python
client = UnifiedGnomadClient()

# All use gnomad_r4 by default
variant = await client.get_variant("1-55039447-G-T")
results = await client.search_variants("rs1234567")
region = await client.get_region("1", 55039000, 55040000)
```

## Benefits

1. **User Convenience**: Users get the latest data by default without specifying versions
2. **Backward Compatibility**: Users can still explicitly specify older versions when needed
3. **Consistency**: All components use the same default version
4. **Future-Proof**: When gnomAD releases v5, only enum definitions need updating