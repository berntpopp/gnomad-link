# gnomAD MCP Server

A production-ready server that provides gnomAD (Genome Aggregation Database) variant allele frequency data through dual interfaces:
- **FastAPI**: RESTful HTTP API with automatic OpenAPI documentation
- **MCP (Model Context Protocol)**: Native tool interface for AI assistants and language models

Built with modern Python async/await patterns, this server provides efficient access to population-specific variant frequencies from the gnomAD database.

## Features

- 🚀 **Dual Interface**: RESTful API and MCP protocol support
- 📊 **Population-Specific Data**: Allele frequencies across global populations (AFR, EAS, NFE, etc.)
- 🧬 **Comprehensive Coverage**: Both exome and genome sequencing datasets
- 📝 **Interactive Documentation**: Auto-generated Swagger UI at `/docs`
- 🔍 **Type Safety**: Pydantic v2 models with full validation
- ⚡ **High Performance**: Async GraphQL client with connection pooling and LRU caching
- 🛡️ **Production Ready**: SSL verification, error handling, and logging
- 🔧 **Flexible Deployment**: Run standalone or integrated servers

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

### Starting the Server

The project includes two optimized servers that share the same caching layer:

1. **FastAPI Server** (HTTP/REST API):
```bash
# Production mode
uvicorn server:app --host 0.0.0.0 --port 8000

# Development mode with auto-reload
python server.py
```

2. **MCP Server** (for language model tools):
```bash
python mcp_server.py
```

Both servers share the same configuration and caching layer, ensuring consistent performance and behavior.

### Accessing the APIs

#### FastAPI Interface

Once the FastAPI server is running:

- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc  
- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **Health Check**: http://localhost:8000/health
- **Cache Statistics**: http://localhost:8000/cache/stats

##### Example Requests

```bash
# Get variant frequency data
curl http://localhost:8000/variant/gnomad_r4/1-55039447-G-T

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

The MCP (Model Context Protocol) server provides tools for language models. Unlike the REST API, MCP doesn't use HTTP by default - it uses STDIO (standard input/output) for communication.

##### How MCP Works

MCP servers communicate through different transport mechanisms:

1. **STDIO Transport (Default)** - Used by Claude Desktop and most MCP clients
   - The server reads from stdin and writes to stdout
   - No URL or port - it's a direct process communication
   - This is why there's no "http://localhost:8001" URL

2. **HTTP Transport (Alternative)** - For web-based integrations
   - Requires explicit configuration
   - See `mcp_server_http.py` for HTTP example

##### Connecting to the MCP Server

**Option 1: Claude Desktop Configuration (Recommended)**

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "gnomad": {
      "command": "python",
      "args": ["/absolute/path/to/gnomad-mcp-server/mcp_server.py"]
    }
  }
}
```

Then restart Claude Desktop. The gnomAD tools will appear in Claude's tool menu.

**Option 2: Direct STDIO Testing**

You can test the MCP server directly:

```bash
# Start the server
python mcp_server.py

# The server is now waiting for JSON-RPC messages on stdin
# Send a request (example):
{"jsonrpc": "2.0", "method": "tools/list", "id": 1}
```

**Option 3: HTTP Transport (Web Integration)**

If you need HTTP access (e.g., for web applications):

```bash
# Create mcp_server_http.py with HTTP transport
python mcp_server_http.py

# Now accessible at http://localhost:8001/mcp
```

##### Example Tool Usage

Once connected via Claude Desktop or another MCP client:

```python
# The tool will be available in your MCP client
result = await get_variant_allele_frequency(
    variant_id="1-55039447-G-T",
    dataset="gnomad_r4"
)
```

##### Why No URL for Default MCP?

The default MCP server uses STDIO because:
- It's more secure (no network exposure)
- It's faster (no HTTP overhead)
- It's the standard for AI assistant integrations
- Claude Desktop expects STDIO communication

If you need HTTP access, use the FastAPI server on port 8000 or create an HTTP-enabled MCP server.

## API Reference

### Endpoints

#### `GET /variant/{dataset}/{variant_id}`

Retrieve allele frequency data for a specific variant.

**Parameters:**
- `dataset` (path): gnomAD dataset ID (e.g., "gnomad_r4", "gnomad_r3", "gnomad_r2_1")
- `variant_id` (path): Variant identifier in format "chromosome-position-reference-alternate"

**Response:** `VariantFrequencyResponse` object containing population frequencies

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
├── server.py             # Main server application
└── pyproject.toml        # Project configuration
```

## Deployment

### Docker

Build and run with Docker:

```bash
docker build -t gnomad-mcp-server .
docker run -p 8000:8000 gnomad-mcp-server
```

### Production Considerations

1. **Environment Variables**: Set appropriate values for production
2. **CORS**: Configure allowed origins in `server.py`
3. **Logging**: Adjust log levels as needed
4. **Rate Limiting**: Consider adding rate limiting middleware
5. **Monitoring**: Integrate with monitoring solutions

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

- **Built-in LRU Cache**: The server automatically caches variant queries
- **Cache Monitoring**: Use `/cache/stats` to monitor hit rates
- **Connection Pooling**: GraphQL client reuses connections
- **Async Operations**: All I/O operations are non-blocking
- **Cache Tuning**: Adjust `CACHE_SIZE` and `CACHE_TTL_MINUTES` based on usage patterns

## Development

### Code Style

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Run tests
pytest

# Run tests with coverage
pytest --cov=gnomad_mcp --cov-report=html
```

### Adding New Features

1. Create feature branch from `main`
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass
5. Submit pull request

## API Reference

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information and endpoints |
| `/health` | GET | Health check endpoint |
| `/docs` | GET | Interactive API documentation |
| `/variant/{dataset}/{variant_id}` | GET | Get variant frequency data |
| `/cache/stats` | GET | Cache statistics |
| `/cache/clear` | POST | Clear variant cache |

### MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_variant_allele_frequency` | Retrieve population allele frequencies | `variant_id`: str, `dataset`: str |

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
gnomAD MCP Server: A dual-interface server for gnomAD variant data
[Your Name], 2024
https://github.com/[your-username]/gnomad-mcp-server
```

And the gnomAD database:
```
Karczewski, K.J., Francioli, L.C., Tiao, G. et al. 
The mutational constraint spectrum quantified from variation in 141,456 humans. 
Nature 581, 434–443 (2020).
```