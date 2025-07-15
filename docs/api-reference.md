# API Reference

## REST API Endpoints

### Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

### Authentication
Currently, no authentication is required. All endpoints are publicly accessible.

## Variant Endpoints

### Get Variant Frequency
Get allele frequency data for a specific variant.

**Endpoint**: `GET /api/variants/{variant_id}`

**Parameters**:
- `variant_id` (path, required): Variant ID in format `chromosome-position-ref-alt`
- `dataset` (query, optional): gnomAD dataset (default: `gnomad_r4`)

**Example**:
```bash
curl "http://localhost:8000/api/variants/1-55039447-G-T?dataset=gnomad_r4"
```

**Response**:
```json
{
  "variant_id": "1-55039447-G-T",
  "reference_genome": "GRCh38",
  "chrom": "1",
  "pos": 55039447,
  "ref": "G",
  "alt": "T",
  "frequencies": {
    "total": {
      "ac": 12,
      "an": 152234,
      "af": 0.0000788,
      "homozygote_count": 0
    },
    "populations": {
      "afr": {"ac": 0, "an": 20324, "af": 0.0},
      "amr": {"ac": 2, "an": 11568, "af": 0.000173},
      "asj": {"ac": 0, "an": 10824, "af": 0.0},
      "eas": {"ac": 0, "an": 18844, "af": 0.0},
      "fin": {"ac": 0, "an": 13832, "af": 0.0},
      "nfe": {"ac": 9, "an": 64760, "af": 0.000139},
      "oth": {"ac": 1, "an": 8464, "af": 0.000118}
    }
  },
  "quality_metrics": {
    "filters": ["PASS"],
    "allele_number": 152234,
    "allele_count": 12
  }
}
```

### Search Variants
Search for variants by ID or region.

**Endpoint**: `GET /api/search/variant`

**Parameters**:
- `query` (query, required): Variant ID or region (e.g., `1-55039447-G-T` or `1:55000000-56000000`)
- `dataset` (query, optional): gnomAD dataset (default: `gnomad_r4`)
- `limit` (query, optional): Maximum results (default: 10, max: 100)

**Example**:
```bash
curl "http://localhost:8000/api/search/variant?query=1-55039447-G-T&dataset=gnomad_r4"
```

## Gene Endpoints

### Get Gene Information
Get comprehensive gene information including constraints and variants.

**Endpoint**: `GET /api/genes/{gene_id}`

**Parameters**:
- `gene_id` (path, required): Gene symbol (e.g., `BRCA2`) or Ensembl ID (e.g., `ENSG00000139618`)
- `reference_genome` (query, optional): Reference genome (default: `GRCh38`)
- `dataset` (query, optional): gnomAD dataset (default: `gnomad_r4`)

**Example**:
```bash
curl "http://localhost:8000/api/genes/BRCA2?reference_genome=GRCh38"
```

**Response**:
```json
{
  "gene_id": "ENSG00000139618",
  "symbol": "BRCA2",
  "name": "BRCA2 DNA repair associated",
  "reference_genome": "GRCh38",
  "chrom": "13",
  "start": 32315086,
  "stop": 32400268,
  "strand": "+",
  "gene_type": "protein_coding",
  "constraints": {
    "lof": {
      "obs": 23,
      "exp": 67.4,
      "oe": 0.341,
      "oe_lower": 0.225,
      "oe_upper": 0.498,
      "pli": 1.0
    },
    "missense": {
      "obs": 1433,
      "exp": 1504.8,
      "oe": 0.952,
      "oe_lower": 0.903,
      "oe_upper": 1.003,
      "z": 1.89
    },
    "synonymous": {
      "obs": 743,
      "exp": 728.5,
      "oe": 1.02,
      "oe_lower": 0.949,
      "oe_upper": 1.096,
      "z": 0.57
    }
  },
  "transcripts": [
    {
      "transcript_id": "ENST00000544455",
      "version": "6",
      "strand": "+",
      "start": 32315086,
      "stop": 32400268,
      "canonical": true,
      "mane_select": true
    }
  ]
}
```

### Search Genes
Search for genes by symbol, name, or Ensembl ID.

**Endpoint**: `GET /api/search/gene`

**Parameters**:
- `query` (query, required): Gene symbol, name, or Ensembl ID
- `reference_genome` (query, optional): Reference genome (default: `GRCh38`)
- `limit` (query, optional): Maximum results (default: 10, max: 100)

**Example**:
```bash
curl "http://localhost:8000/api/search/gene?query=BRCA&reference_genome=GRCh38"
```

## Transcript Endpoints

### Get Transcript Information
Get detailed transcript information including exons and coding sequences.

**Endpoint**: `GET /api/transcripts/{transcript_id}`

**Parameters**:
- `transcript_id` (path, required): Ensembl transcript ID (e.g., `ENST00000544455`)
- `reference_genome` (query, optional): Reference genome (default: `GRCh38`)

**Example**:
```bash
curl "http://localhost:8000/api/transcripts/ENST00000544455?reference_genome=GRCh38"
```

**Response**:
```json
{
  "transcript_id": "ENST00000544455",
  "version": "6",
  "gene_id": "ENSG00000139618",
  "gene_symbol": "BRCA2",
  "strand": "+",
  "chrom": "13",
  "start": 32315086,
  "stop": 32400268,
  "canonical": true,
  "mane_select": true,
  "cds_start": 32315507,
  "cds_stop": 32398770,
  "exons": [
    {
      "exon_number": 1,
      "start": 32315086,
      "stop": 32315145
    },
    {
      "exon_number": 2,
      "start": 32316422,
      "stop": 32316527
    }
  ]
}
```

### Search Transcripts
Search for transcripts with optional filtering.

**Endpoint**: `GET /api/search/transcript`

**Parameters**:
- `query` (query, required): Transcript ID or gene symbol
- `reference_genome` (query, optional): Reference genome (default: `GRCh38`)
- `canonical_only` (query, optional): Only canonical transcripts (default: false)
- `limit` (query, optional): Maximum results (default: 10, max: 100)

## Clinical Annotation Endpoints

### Get ClinVar Variant
Get clinical significance and annotations from ClinVar.

**Endpoint**: `GET /api/clinvar/variant/{variant_id}`

**Parameters**:
- `variant_id` (path, required): Variant ID in format `chromosome-position-ref-alt`
- `reference_genome` (query, optional): Reference genome (default: `GRCh38`)

**Example**:
```bash
curl "http://localhost:8000/api/clinvar/variant/7-117559590-ATCT-A?reference_genome=GRCh38"
```

**Response**:
```json
{
  "variant_id": "7-117559590-ATCT-A",
  "clinical_significance": "Pathogenic",
  "review_status": "criteria provided, multiple submitters, no conflicts",
  "last_evaluated": "2023-01-15",
  "conditions": [
    {
      "name": "Cystic fibrosis",
      "medgen_id": "C0010674",
      "omim_id": "219700"
    }
  ],
  "submissions": [
    {
      "submitter": "ClinGen Cystic Fibrosis Variant Curation Expert Panel",
      "clinical_significance": "Pathogenic",
      "last_evaluated": "2023-01-15",
      "method": "clinical testing"
    }
  ],
  "molecular_consequence": "frameshift_variant",
  "gnomad_frequency": {
    "ac": 0,
    "an": 152234,
    "af": 0.0
  }
}
```

### Get Structural Variant
Get structural variant information and population frequencies.

**Endpoint**: `GET /api/structural-variant/{variant_id}`

**Parameters**:
- `variant_id` (path, required): Structural variant ID (e.g., `1-1000000-2000000-DEL`)
- `dataset` (query, optional): gnomAD dataset (default: `gnomad_r4`)

### Get Mitochondrial Variant
Get mitochondrial variant information and heteroplasmy data.

**Endpoint**: `GET /api/mitochondrial-variant/{variant_id}`

**Parameters**:
- `variant_id` (path, required): Mitochondrial variant ID (e.g., `MT-8993-T-G`)
- `dataset` (query, optional): gnomAD dataset (default: `gnomad_r3`)

## Utility Endpoints

### Coordinate Liftover
Convert variant coordinates between reference genomes.

**Endpoint**: `GET /api/liftover/`

**Parameters**:
- `source_variant_id` (query, optional): Source variant ID for forward liftover
- `liftover_variant_id` (query, optional): Target variant ID for reverse liftover
- `reference_genome` (query, required): Source reference genome (`GRCh37` or `GRCh38`)

**Note**: Provide either `source_variant_id` OR `liftover_variant_id`, not both.

**Example**:
```bash
# Forward liftover (GRCh37 to GRCh38)
curl "http://localhost:8000/api/liftover/?source_variant_id=17-7577121-G-A&reference_genome=GRCh37"

# Reverse liftover (GRCh38 to GRCh37)
curl "http://localhost:8000/api/liftover/?liftover_variant_id=17-7674221-G-A&reference_genome=GRCh38"
```

**Response**:
```json
{
  "results": [
    {
      "source": {
        "variant_id": "17-7577121-G-A",
        "reference_genome": "GRCh37"
      },
      "liftover": {
        "variant_id": "17-7674221-G-A",
        "reference_genome": "GRCh38"
      },
      "datasets": ["gnomad_r2_1", "gnomad_r4"]
    }
  ],
  "query_type": "forward"
}
```

### Region Query
Get variants in a genomic region.

**Endpoint**: `GET /api/region/{region}`

**Parameters**:
- `region` (path, required): Genomic region (e.g., `1:55000000-56000000`)
- `dataset` (query, optional): gnomAD dataset (default: `gnomad_r4`)

## System Endpoints

### Health Check
Check system health and status.

**Endpoint**: `GET /api/health`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-07-15T18:30:00Z",
  "version": "2.0.0",
  "transport": "unified",
  "services": {
    "gnomad_api": "healthy",
    "cache": "healthy",
    "mcp": "healthy"
  }
}
```

### Cache Statistics
Get cache performance metrics.

**Endpoint**: `GET /api/cache/stats`

**Response**:
```json
{
  "cache_size": 1024,
  "cache_used": 234,
  "hit_rate": 0.87,
  "miss_rate": 0.13,
  "total_hits": 1420,
  "total_misses": 213,
  "evictions": 45
}
```

### Clear Cache
Clear the application cache.

**Endpoint**: `POST /api/cache/clear`

**Response**:
```json
{
  "message": "Cache cleared successfully",
  "timestamp": "2025-07-15T18:30:00Z"
}
```

## MCP Tools

### Available Tools
The MCP interface provides the following tools for AI assistants:

#### get_variant_frequency
Get variant allele frequencies across populations.

**Parameters**:
- `variant_id` (required): Variant ID (e.g., `1-55039447-G-T`)
- `dataset` (optional): gnomAD dataset (default: `gnomad_r4`)

#### search_genes
Search for genes by symbol or ID.

**Parameters**:
- `query` (required): Gene symbol, name, or Ensembl ID
- `reference_genome` (optional): Reference genome (default: `GRCh38`)
- `limit` (optional): Maximum results (default: 10)

#### search_transcripts
Search for transcripts with filtering options.

**Parameters**:
- `query` (required): Transcript ID or gene symbol
- `reference_genome` (optional): Reference genome (default: `GRCh38`)
- `canonical_only` (optional): Only canonical transcripts (default: false)
- `limit` (optional): Maximum results (default: 10)

#### get_structural_variants
Query structural variants in a genomic region.

**Parameters**:
- `region` (required): Genomic region (e.g., `1:1000000-2000000`)
- `dataset` (optional): gnomAD dataset (default: `gnomad_r4`)
- `variant_type` (optional): Structural variant type filter

#### search_clinvar_variants
Search for ClinVar variants with clinical significance.

**Parameters**:
- `query` (required): Variant ID or gene symbol
- `reference_genome` (optional): Reference genome (default: `GRCh38`)
- `significance` (optional): Clinical significance filter
- `limit` (optional): Maximum results (default: 10)

### MCP Usage Examples

```bash
# List available tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Get variant frequency
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_variant_frequency",
      "arguments": {
        "variant_id": "1-55039447-G-T",
        "dataset": "gnomad_r4"
      }
    },
    "id": 1
  }'
```

## Error Handling

### HTTP Status Codes
- `200 OK`: Successful request
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error
- `504 Gateway Timeout`: Request timeout (usually invalid ID)

### Error Response Format
```json
{
  "detail": "Error message describing the issue",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-07-15T18:30:00Z"
}
```

### Common Error Scenarios

#### Invalid Variant ID Format
```json
{
  "detail": "Invalid variant ID format. Expected: chromosome-position-ref-alt",
  "error_code": "INVALID_VARIANT_ID"
}
```

#### Variant Not Found
```json
{
  "detail": "Variant not found in specified dataset",
  "error_code": "VARIANT_NOT_FOUND"
}
```

#### Request Timeout
```json
{
  "detail": "Request timeout. This usually indicates an invalid ID.",
  "error_code": "REQUEST_TIMEOUT"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. All requests are processed without restrictions.

## Interactive Documentation

Visit `http://localhost:8000/docs` when the server is running to access the interactive Swagger UI documentation with:
- Complete API schema
- Request/response examples
- Try-it-out functionality
- Parameter descriptions
- Authentication details

This comprehensive API reference provides all the information needed to integrate with the gnomAD-link REST API and MCP interface.