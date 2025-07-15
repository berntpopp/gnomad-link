# Usage Guide

## Quick Start

### Installation
```bash
git clone <repository-url>
cd gnomad-link
pip install -e .
```

### Basic Usage
```bash
# Start unified server (REST + MCP HTTP)
python server.py --transport unified

# Access REST API documentation
open http://localhost:8000/docs

# MCP interface available at
# http://localhost:8000/mcp
```

## Transport Modes

### 1. Unified Transport (Recommended)

**Best for**: Production deployments, web applications, AI assistants with HTTP access

```bash
# Start unified server
python server.py --transport unified --port 8000

# With custom configuration
python server.py --transport unified --port 8000 --mcp-path /api/mcp --host 0.0.0.0
```

**Features**:
- Single server process
- REST API at `/api/`
- MCP HTTP at `/mcp`
- Swagger documentation at `/docs`
- Health checks at `/health`

**Access Points**:
```bash
# REST API
curl "http://localhost:8000/api/variants/1-55039447-G-T?dataset=gnomad_r4"

# Interactive documentation
open http://localhost:8000/docs

# MCP HTTP endpoint
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

### 2. STDIO Transport (AI Assistants)

**Best for**: Local AI assistant integration, Claude Desktop, development tools

```bash
# Start STDIO server
python server.py --transport stdio

# Alternative (backwards compatible)
python mcp_server.py
```

**Features**:
- High-performance binary protocol
- Minimal logging (stderr only)
- Optimized for AI assistant integration
- ~10,000+ operations/second

**Claude Desktop Configuration**:
```json
{
  "mcpServers": {
    "gnomad": {
      "command": "python",
      "args": ["/path/to/gnomad-link/server.py", "--transport", "stdio"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### 3. HTTP-Only Transport (Pure REST)

**Best for**: Traditional web APIs, microservices, REST-only deployments

```bash
# Start HTTP-only server
python server.py --transport http --port 8000
```

**Features**:
- FastAPI-only deployment
- No MCP overhead
- Traditional REST API server
- Full Swagger documentation

## Configuration

### Command Line Options
```bash
python server.py --help

usage: server.py [-h] [--transport {unified,http,stdio}] [--host HOST] [--port PORT]
                [--mcp-path MCP_PATH] [--log-level LOG_LEVEL] [--dev]

Options:
  --transport {unified,http,stdio}  Transport mode (default: unified)
  --host HOST                      Server host (default: 127.0.0.1)
  --port PORT                      Server port (default: 8000)
  --mcp-path MCP_PATH             MCP endpoint path (default: /mcp)
  --log-level LOG_LEVEL           Logging level (default: INFO)
  --dev                           Development mode with auto-reload
```

### Environment Variables
```bash
# Transport Configuration
export MCP_TRANSPORT=unified
export MCP_HOST=127.0.0.1
export MCP_PORT=8000
export MCP_PATH=/mcp

# gnomAD Configuration
export GNOMAD_API_URL=https://gnomad.broadinstitute.org/api
export CACHE_SIZE=1024
export CACHE_TTL_MINUTES=60

# Logging Configuration
export LOG_LEVEL=INFO
export MCP_LOG_LEVEL=INFO
export STDIO_LOG_LEVEL=WARNING

# Production Configuration
export ENABLE_SWAGGER=true
export ENABLE_MONITORING=true
export CORS_ORIGINS="*"
```

### Configuration File (.env)
```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

## API Usage

### REST API

#### Variant Queries
```bash
# Get variant frequency data
curl "http://localhost:8000/api/variants/1-55039447-G-T?dataset=gnomad_r4"

# Search variants
curl "http://localhost:8000/api/search/variant?query=1-55039447-G-T&dataset=gnomad_r4"

# Liftover coordinates
curl "http://localhost:8000/api/liftover/?source_variant_id=17-7577121-G-A&reference_genome=GRCh37"
```

#### Gene Queries
```bash
# Get gene information
curl "http://localhost:8000/api/genes/ENSG00000139618?reference_genome=GRCh38"

# Search genes
curl "http://localhost:8000/api/search/gene?query=BRCA2&reference_genome=GRCh38"
```

#### Transcript Queries
```bash
# Get transcript information
curl "http://localhost:8000/api/transcripts/ENST00000544455?reference_genome=GRCh38"

# Search transcripts
curl "http://localhost:8000/api/search/transcript?query=ENST00000544455&reference_genome=GRCh38"
```

#### Clinical Variants
```bash
# Get ClinVar annotations
curl "http://localhost:8000/api/clinvar/variant/7-117559590-ATCT-A?reference_genome=GRCh38"

# Structural variants
curl "http://localhost:8000/api/structural-variant/1-1000000-2000000-DEL?dataset=gnomad_r4"

# Mitochondrial variants
curl "http://localhost:8000/api/mitochondrial-variant/MT-8993-T-G?dataset=gnomad_r3"
```

### MCP Interface

#### Available Tools
- `get_variant_frequency`: Query variant allele frequencies
- `search_genes`: Search for genes by symbol or ID
- `search_transcripts`: Search for transcripts with filters
- `get_structural_variants`: Query structural variants in regions
- `search_clinvar_variants`: Search ClinVar variants with significance

#### Example MCP Calls
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

# Search genes
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_genes",
      "arguments": {
        "query": "BRCA2",
        "reference_genome": "GRCh38"
      }
    },
    "id": 1
  }'
```

## AI Assistant Integration

### Claude Desktop Setup

1. **Install gnomAD-link**:
   ```bash
   git clone <repository-url>
   cd gnomad-link
   pip install -e .
   ```

2. **Configure Claude Desktop**:
   ```json
   {
     "mcpServers": {
       "gnomad": {
         "command": "python",
         "args": ["/absolute/path/to/gnomad-link/server.py", "--transport", "stdio"],
         "env": {
           "PYTHONUNBUFFERED": "1"
         }
       }
     }
   }
   ```

3. **Test Integration**:
   - Restart Claude Desktop
   - Ask: "What's the frequency of variant 1-55039447-G-T in gnomAD?"
   - Claude should use the gnomAD tools to answer

### Other AI Assistants

For HTTP-based AI assistants, use the unified transport:

```bash
# Start server with HTTP MCP
python server.py --transport unified --port 8000

# MCP endpoint available at
# http://localhost:8000/mcp
```

## Monitoring and Debugging

### Health Checks
```bash
# Overall health
curl http://localhost:8000/health

# Cache statistics
curl http://localhost:8000/api/cache/stats
```

### Cache Management
```bash
# Get cache statistics
curl http://localhost:8000/api/cache/stats

# Clear cache
curl -X POST http://localhost:8000/api/cache/clear
```

### Logging
```bash
# Start with debug logging
python server.py --transport unified --log-level DEBUG

# STDIO transport (minimal logging)
python server.py --transport stdio --log-level WARNING
```

### Development Mode
```bash
# Start with auto-reload
python server.py --transport unified --dev

# Features:
# - Auto-reload on code changes
# - Enhanced debugging
# - Detailed error messages
# - Performance profiling
```

## Error Handling

### Common Errors

#### Configuration Errors
```bash
# Invalid transport
python server.py --transport invalid
# Error: Invalid transport type

# Port already in use
python server.py --port 8000
# Error: Port 8000 already in use
```

#### API Errors
```bash
# Invalid variant ID
curl "http://localhost:8000/api/variants/invalid-variant"
# HTTP 422: Invalid variant ID format

# Timeout (usually indicates invalid ID)
curl "http://localhost:8000/api/variants/1-999999999-G-T"
# HTTP 504: Request timeout
```

#### MCP Errors
```bash
# Invalid MCP request
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"invalid": "request"}'
# JSON-RPC error response
```

### Debugging Tips

1. **Check Logs**: Review server logs for detailed error information
2. **Validate Configuration**: Use `--log-level DEBUG` for detailed output
3. **Test Endpoints**: Use `/health` endpoint to verify service status
4. **Cache Issues**: Clear cache using `/api/cache/clear` endpoint
5. **Transport Issues**: Try different transport modes to isolate problems

## Performance Optimization

### Caching
```bash
# Optimize cache settings
export CACHE_SIZE=2048
export CACHE_TTL_MINUTES=120

# Monitor cache performance
curl http://localhost:8000/api/cache/stats
```

### Connection Pooling
- HTTP connections are automatically pooled
- GraphQL client maintains persistent connections
- Async operations prevent blocking

### Resource Management
- Proper async context management
- Graceful shutdown with signal handling
- Memory-efficient caching with LRU eviction

## Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["python", "server.py", "--transport", "unified", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  gnomad-unified:
    build: .
    environment:
      - MCP_TRANSPORT=unified
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8000
      - ENABLE_MONITORING=true
      - LOG_LEVEL=INFO
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Environment-Specific Configuration
```bash
# Development
export MCP_TRANSPORT=unified
export LOG_LEVEL=DEBUG
export ENABLE_SWAGGER=true

# Production
export MCP_TRANSPORT=unified
export LOG_LEVEL=INFO
export ENABLE_MONITORING=true
export CORS_ORIGINS="https://yourdomain.com"
```

This usage guide covers the essential patterns for deploying and using gnomAD-link in various environments and configurations.