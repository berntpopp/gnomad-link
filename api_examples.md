# gnomAD API Examples

## FastAPI with Swagger UI Dropdowns

The FastAPI server now includes dropdown menus in the Swagger UI for all dataset and reference genome parameters. This ensures you can only select valid values.

### Available Enum Values

#### GnomadDataset
- `gnomad_r2_1` - gnomAD v2.1 (GRCh37)
- `gnomad_r3` - gnomAD v3 (GRCh38)
- `gnomad_r4` - gnomAD v4 (GRCh38) **[Default]**

#### StructuralVariantDataset
- `gnomad_sv_r2_1` - gnomAD SV v2.1
- `gnomad_sv_r4` - gnomAD SV v4 **[Default]**

#### ReferenceGenome
- `GRCh37` - Human genome build 37
- `GRCh38` - Human genome build 38 **[Default]**

### Example API Calls

#### Variant Lookup
```bash
# Get variant frequency data (dataset required in path)
curl -X 'GET' \
  'http://127.0.0.1:8000/variant/gnomad_r4/1-55039447-G-T' \
  -H 'accept: application/json'

# Get detailed variant information
curl -X 'GET' \
  'http://127.0.0.1:8000/variant/details/gnomad_r4/1-55039447-G-T' \
  -H 'accept: application/json'
```

#### Gene Operations
```bash
# Search for genes (defaults to GRCh38)
curl -X 'GET' \
  'http://127.0.0.1:8000/search/gene?query=BRCA1' \
  -H 'accept: application/json'

# Get gene information
curl -X 'GET' \
  'http://127.0.0.1:8000/gene/?gene_symbol=BRCA1&reference_genome=GRCh38' \
  -H 'accept: application/json'

# Get variants in a gene (defaults to gnomad_r4)
curl -X 'GET' \
  'http://127.0.0.1:8000/gene/variants/ENSG00000012048?dataset=gnomad_r4' \
  -H 'accept: application/json'
```

#### ClinVar Lookup
```bash
# Get ClinVar data (defaults to GRCh38)
curl -X 'GET' \
  'http://127.0.0.1:8000/clinvar/variant/1-55039447-G-T' \
  -H 'accept: application/json'
```

#### Structural Variants
```bash
# Get structural variant data (dataset required in path)
curl -X 'GET' \
  'http://127.0.0.1:8000/structural-variant/gnomad_sv_r4/DEL_1_12345' \
  -H 'accept: application/json'
```

#### Mitochondrial Variants
```bash
# Get mitochondrial variant data (dataset required in path)
curl -X 'GET' \
  'http://127.0.0.1:8000/mitochondrial-variant/gnomad_r4/MT-1234-A-G' \
  -H 'accept: application/json'
```

#### Region Query
```bash
# Get variants and genes in a region (defaults to gnomad_r4)
curl -X 'GET' \
  'http://127.0.0.1:8000/region/?chrom=1&start=55039000&stop=55040000' \
  -H 'accept: application/json'
```

#### Transcript Information
```bash
# Get transcript data (defaults to GRCh38)
curl -X 'GET' \
  'http://127.0.0.1:8000/transcript/ENST00000357654' \
  -H 'accept: application/json'
```

### Swagger UI Benefits

When you access the API documentation at `http://127.0.0.1:8000/docs`, you'll see:

1. **Dropdown menus** for all dataset and reference genome parameters
2. **Default values** pre-selected (gnomad_r4 for datasets, GRCh38 for reference genome)
3. **Clear descriptions** for each parameter
4. **Validation** ensuring only valid values are submitted

This prevents errors from invalid dataset names and makes the API more user-friendly.