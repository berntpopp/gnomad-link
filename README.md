# gnomAD MCP Server

A production-ready unified server that provides gnomAD (Genome Aggregation Database) variant allele frequency data through dual interfaces:
- **FastAPI**: RESTful HTTP API with automatic OpenAPI documentation
- **MCP (Model Context Protocol)**: Native tool interface for AI assistants and language models

Built with modern Python async/await patterns, this server provides efficient access to population-specific variant frequencies from the gnomAD database through a single application process.

## Features

- 🚀 **Unified Server**: Single process serves both REST API and MCP tools
- 📊 **Population-Specific Data**: Allele frequencies across global populations (AFR, EAS, NFE, etc.)
- 🧬 **Comprehensive Coverage**: Both exome and genome sequencing datasets
- 📝 **Interactive Documentation**: Auto-generated Swagger UI at `/docs`
- 🔍 **Type Safety**: Pydantic v2 models with full validation
- ⚡ **High Performance**: Async GraphQL client with connection pooling and shared LRU caching
- 🛡️ **Production Ready**: SSL verification, error handling, and logging
- 🔄 **Shared State**: Both interfaces share the same cache and service instances

## Installation

### Prerequisites

- Python 3.9+
- pip or conda package manager

### Quick Start

1. Clone and navigate to the project:
```bash
git clone <repository-url>
cd GnomAD-MCP
```

2. Create and activate a virtual environment:
```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n gnomad-mcp python=3.10
conda activate gnomad-mcp
```

3. Install the package and dependencies:
```bash
# Quick install
./install.sh

# Or manual install
pip install -e .

# For development (includes testing tools)
pip install -e ".[dev]"
```

**Note**: The server requires `async-lru` for caching. If you see import errors, ensure all dependencies are installed with `pip install -e .`

## Configuration

The server can be configured using environment variables. Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Available configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `GNOMAD_API_URL` | gnomAD GraphQL API endpoint | `https://gnomad.broadinstitute.org/api` |
| `CACHE_SIZE` | Maximum number of variants to cache | `1024` |
| `CACHE_TTL_MINUTES` | Cache time-to-live in minutes | `60` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `*` |

## Usage

### Starting the Unified Server

The project now includes a single unified server that provides both REST API and MCP interfaces:

```bash
# Production mode
uvicorn server:app --host 0.0.0.0 --port 8000

# Development mode with auto-reload
python server.py
```

This single server process:
- Serves the REST API on the root path (`/`)
- Mounts the MCP interface at `/mcp`
- Shares cache and service instances between both interfaces
- Uses a unified lifespan manager for proper startup/shutdown

### Accessing the APIs

#### FastAPI Interface

Once the unified server is running:

- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc  
- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **Health Check**: http://localhost:8000/health
- **Cache Statistics**: http://localhost:8000/cache/stats

##### Example Requests

```bash
# Get variant frequency data
curl http://localhost:8000/variant/1-55039447-G-T?dataset=gnomad_r4

# Check server health
curl http://localhost:8000/health

# Get API info
curl http://localhost:8000/

# Check cache statistics
curl http://localhost:8000/cache/stats

# Clear cache (POST request)
curl -X POST http://localhost:8000/cache/clear
```

##### Example Response

```json
{
  "variant_id": "1-55039447-G-T",
  "dataset": "gnomad_r4",
  "exome": {
    "populations": [
      {
        "name": "afr",
        "allele_count": 2,
        "allele_number": 15300,
        "homozygote_count": 0
      },
      {
        "name": "eas",
        "allele_count": 0,
        "allele_number": 19950,
        "homozygote_count": 0
      }
    ]
  },
  "genome": null
}
```

#### MCP Interface

The MCP (Model Context Protocol) interface is now available through HTTP at `/mcp` when the unified server is running.

##### Connecting to the MCP Interface

**Option 1: Claude Desktop Configuration (HTTP)**

For Claude Desktop configurations that support HTTP endpoints, add to your config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "gnomad": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Option 2: Direct HTTP Access**

The MCP tools are available via HTTP at:
```
http://localhost:8000/mcp
```

You can interact with the MCP interface using any HTTP client that supports the MCP protocol.

##### Available MCP Tools

1. **get_variant_allele_frequency**
   - Retrieves population allele frequency data for a genetic variant
   - Parameters:
     - `variant_id`: Variant identifier (e.g., "1-55039447-G-T")
     - `dataset`: gnomAD dataset (defaults to GNOMAD_R4)

2. **get_gene_summary**
   - Retrieves a concise summary for a gene
   - Parameters:
     - `gene_symbol`: HGNC gene symbol (e.g., "BRCA1", "TP53")
   - Returns: gene ID, symbol, and pLI score

##### Example Tool Usage

Once connected via Claude Desktop or another MCP client:

```python
# Get variant frequency data
result = await get_variant_allele_frequency(
    variant_id="1-55039447-G-T",
    dataset="gnomad_r4"
)

# Get gene summary
gene_info = await get_gene_summary(
    gene_symbol="BRCA1"
)
```

## API Reference

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information and endpoints |
| `/health` | GET | Health check endpoint |
| `/docs` | GET | Interactive API documentation |
| `/variant/{variant_id}` | GET | Get variant frequency data |
| `/gene/` | GET | Get gene information |
| `/search/variant` | GET | Search for variants |
| `/search/gene` | GET | Search for genes |
| `/clinvar/variant/{variant_id}` | GET | Get ClinVar variant data |
| `/structural-variant/{variant_id}` | GET | Get structural variant data |
| `/mitochondrial-variant/{variant_id}` | GET | Get mitochondrial variant data |
| `/region/` | GET | Query genomic region |
| `/transcript/{transcript_id}` | GET | Get transcript data |
| `/cache/stats` | GET | Cache statistics |
| `/cache/clear` | POST | Clear variant cache |

### MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_variant_allele_frequency` | Retrieve population allele frequencies | `variant_id`: str, `dataset`: GnomadDataset |
| `get_gene_summary` | Get gene summary with pLI score | `gene_symbol`: str |

### Data Models

#### VariantFrequencyResponse
- `variant_id`: Variant identifier
- `dataset`: Dataset used for query
- `exome`: Population frequencies from exome sequencing (optional)
- `genome`: Population frequencies from genome sequencing (optional)

#### PopulationFrequency
- `name`: Population group identifier (e.g., "afr", "eas", "nfe")
- `allele_count`: Number of alternate alleles observed
- `allele_number`: Total number of alleles assessed
- `homozygote_count`: Number of homozygous individuals
- `allele_frequency`: Calculated AF (property)

## Development

### Running Tests

Execute the test suite:

```bash
pytest
```

With coverage:

```bash
pytest --cov=gnomad_mcp
```

### Code Quality

Run linting:

```bash
ruff check .
```

Format code:

```bash
ruff format .
```

### Project Structure

```
gnomad-mcp-server/
├── gnomad_mcp/
│   ├── api/              # GraphQL client and queries
│   ├── models/           # Pydantic data models
│   ├── services/         # Business logic layer
│   └── config.py         # Configuration management
├── tests/                # Test suite
├── server.py             # Unified server application
└── pyproject.toml        # Project configuration
```

## Architecture Benefits

The unified server architecture provides several advantages:

1. **Shared Resources**: Both REST API and MCP tools use the same service instances and cache
2. **Single Process**: Easier deployment and monitoring with one process instead of two
3. **Consistent State**: No synchronization issues between separate processes
4. **Unified Configuration**: One set of environment variables for both interfaces
5. **Simplified Lifecycle**: Single lifespan manager handles startup/shutdown for all components

## Deployment

### Docker

Build and run with Docker:

```bash
docker build -t gnomad-mcp-server .
docker run -p 8000:8000 gnomad-mcp-server
```

### Production Considerations

1. **Environment Variables**: Set appropriate values for production
2. **CORS**: Configure allowed origins for your deployment
3. **Logging**: Adjust log levels as needed
4. **Rate Limiting**: Consider adding rate limiting middleware
5. **Monitoring**: The unified server simplifies monitoring with single process metrics

## Troubleshooting

### Common Issues

1. **SSL Certificate Error**
   - The server uses SSL verification by default
   - If behind a corporate proxy, you may need to configure certificates

2. **Variant Not Found**
   - Ensure variant ID format is correct: `chromosome-position-ref-alt`
   - Check that the dataset ID matches available gnomAD releases
   - Some variants may not be present in all datasets

3. **Connection Timeouts**
   - The gnomAD API can be slow for complex queries
   - Default timeout is 30 seconds, configurable in the client

4. **Invalid Variant ID Format**
   - The server validates variant IDs and will reject malformed inputs
   - No quotes or special characters allowed in the ID

### Performance Tips

- **Shared LRU Cache**: Both interfaces benefit from the same cache
- **Cache Monitoring**: Use `/cache/stats` to monitor hit rates
- **Connection Pooling**: GraphQL client reuses connections
- **Async Operations**: All I/O operations are non-blocking
- **Cache Tuning**: Adjust `CACHE_SIZE` and `CACHE_TTL_MINUTES` based on usage patterns

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

## Acknowledgments

- [gnomAD](https://gnomad.broadinstitute.org/) - Genome Aggregation Database by the Broad Institute
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework for building APIs
- [FastMCP](https://github.com/jlowin/fastmcp) - Model Context Protocol implementation
- [gql](https://github.com/graphql-python/gql) - GraphQL client for Python

## Citation

If you use this tool in your research, please cite:

```
gnomAD MCP Server: A unified dual-interface server for gnomAD variant data
[Your Name], 2024
https://github.com/[your-username]/gnomad-mcp-server
```

And the gnomAD database:
```
Karczewski, K.J., Francioli, L.C., Tiao, G. et al. 
The mutational constraint spectrum quantified from variation in 141,456 humans. 
Nature 581, 434–443 (2020).
```