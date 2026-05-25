# gnomAD Link

A production-ready unified server that bridges the gnomAD (Genome Aggregation Database) to modern AI applications through dual interfaces: REST API and MCP (Model Context Protocol).

## 🎯 Core Purpose

This server provides programmatic access to human genetic variation data from gnomAD, the world's largest public database of human genetic variants. It enables:

- **Researchers**: Query variant frequencies across global populations via REST API
- **AI Assistants**: Access gnomAD data through native tool interfaces (MCP)
- **Developers**: Build applications using standardized genetic variant data

## 🚀 Key Features

- **Unified Architecture**: Single server process serving both REST and MCP interfaces
- **Transport Selection**: Support for unified, HTTP-only, and STDIO transport modes
- **Comprehensive Data Access**: Variants, genes, transcripts, structural variants, ClinVar annotations
- **Population Genetics**: Allele frequencies across 8 global populations
- **High Performance**: Async operations with intelligent caching (~10,000+ ops/sec STDIO)
- **Type Safety**: Full Pydantic v2 validation and auto-generated documentation
- **Production Ready**: Comprehensive error handling, logging, and monitoring
- **Zero Breaking Changes**: Full backwards compatibility maintained

## 📦 Quick Start

### Installation
```bash
git clone <repository-url>
cd gnomad-link
uv sync --group dev
```

### Basic Usage
```bash
# Start unified server (REST + MCP HTTP)
uv run python server.py --transport unified

# Access REST API at http://localhost:8000/docs
# MCP interface available at http://localhost:8000/mcp
```

### Transport Modes
```bash
# Unified: REST API + MCP HTTP (recommended)
uv run python server.py --transport unified --port 8000

# STDIO: High-performance AI assistant integration
uv run python server.py --transport stdio

# HTTP-only: Traditional REST API only
uv run python server.py --transport http --port 8000
```

## 🔧 Configuration

### Environment Variables
```env
# Transport Configuration
MCP_TRANSPORT=unified
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_PATH=/mcp

# gnomAD Configuration
GNOMAD_API_URL=https://gnomad.broadinstitute.org/api
CACHE_SIZE=1024
CACHE_TTL_MINUTES=60

# Logging Configuration
LOG_LEVEL=INFO
MCP_LOG_LEVEL=INFO
STDIO_LOG_LEVEL=WARNING
```

### Configuration File
```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

## 📡 Usage Examples

### REST API
```bash
# Query variant frequency
curl "http://localhost:8000/api/variants/1-55039447-G-T?dataset=gnomad_r4"

# Search for gene
curl "http://localhost:8000/api/search/gene?query=BRCA2&reference_genome=GRCh38"

# Get ClinVar annotations
curl "http://localhost:8000/api/clinvar/variant/7-117559590-ATCT-A?reference_genome=GRCh38"

# Coordinate liftover
curl "http://localhost:8000/api/liftover/?source_variant_id=17-7577121-G-A&reference_genome=GRCh37"
```

### MCP Integration

#### Claude / MCP HTTP (Recommended)

Start the unified server:

```bash
make mcp-serve-http
```

Claude Code:

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

Claude Desktop HTTP config:

```json
{
  "mcpServers": {
    "gnomad-link": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

#### stdio Fallback

Use stdio only for local desktop workflows that cannot connect to HTTP MCP
endpoints:

```json
{
  "mcpServers": {
    "gnomad-link-stdio": {
      "command": "gnomad-link-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

#### MCP Tools Available
- `get_variant_frequency`: Query variant allele frequencies
- `search_genes`: Search for genes by symbol or ID
- `search_transcripts`: Search transcripts with filtering
- `get_structural_variants`: Query structural variants in regions
- `search_clinvar_variants`: Search ClinVar variants with significance

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Transport Layer                          │
├─────────────────┬─────────────────┬─────────────────────────┤
│   FastAPI/HTTP  │  MCP/HTTP       │    MCP/STDIO            │
│   (REST + Docs) │  (Streamable)   │    (AI Assistants)      │
└─────────────────┴─────────────────┴─────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                 FastMCP Integration Layer                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │            Unified Server Manager                       ││
│  │  • Transport Selection Logic                           ││
│  │  • Lifecycle Coordination                              ││
│  │  • Configuration Management                            ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  Business Logic Layer                      │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ FrequencyService │ │ GraphQLClient │ │ CacheManager   │  │
│  │ (async-lru)     │ │ (versioned)   │ │ (shared)       │  │
│  └───────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                             │
│            gnomAD GraphQL API (v2, v3, v4)                 │
└─────────────────────────────────────────────────────────────┘
```

## 📚 Available Endpoints

### Core Variant Data
- `/api/variants/{variant_id}` - Variant allele frequencies
- `/api/genes/{gene_id}` - Gene information and constraints
- `/api/transcripts/{transcript_id}` - Transcript details

### Search & Discovery
- `/api/search/variant` - Search variants by ID or region
- `/api/search/gene` - Search genes by symbol or name
- `/api/search/transcript` - Search transcripts

### Clinical & Specialized
- `/api/clinvar/variant/{variant_id}` - ClinVar clinical significance
- `/api/structural-variant/{variant_id}` - Structural variants
- `/api/mitochondrial-variant/{variant_id}` - Mitochondrial variants
- `/api/liftover` - Convert coordinates between genome builds

### Utilities
- `/api/region/{region}` - Query genomic regions
- `/api/cache/stats` - Cache performance metrics
- `/api/cache/clear` - Clear application cache
- `/api/health` - Service health check

## 🧬 Understanding gnomAD

gnomAD aggregates genetic data from hundreds of thousands of individuals to provide:
- **Population Frequencies**: How common variants are across different ancestries
- **Constraint Metrics**: How tolerant genes are to mutations
- **Clinical Annotations**: Disease associations from ClinVar
- **Quality Metrics**: Sequencing depth and quality scores

### Data Sources
- **gnomAD v2**: Exome data with 125k+ individuals
- **gnomAD v3**: Genome data with 76k+ individuals  
- **gnomAD v4**: Latest release with 730k+ individuals
- **ClinVar**: Clinical variant annotations
- **Structural Variants**: Large genomic rearrangements
- **Mitochondrial Variants**: Mitochondrial genome variants

### Useful Resources
- [gnomAD Browser](https://gnomad.broadinstitute.org/)
- [gnomAD API Documentation](https://gnomad.broadinstitute.org/api)
- [GA4GH Standards Integration](https://gnomad.broadinstitute.org/news/2023-11-ga4gh-gks/)
- [gnomAD GraphQL Playground](https://gnomad.broadinstitute.org/api)

## 🛠️ Development

### Development Setup
```bash
# Install development dependencies
make install

# Resolve dependency lock
make lock

# Run tests
make test

# Run tests with coverage
make test-cov

# Lint code with Ruff
make lint

# Format code with Ruff
make format

# Run local CI checks
make ci-local
```

### Development Commands
```bash
# Start development server
make dev

# Run production server
make run-prod

# Run STDIO MCP server
make mcp-serve

# Clean build artifacts
make clean
```

### Docker Commands
```bash
# Build and start the Docker service
make docker-build
make docker-up

# Render hardened Compose configs
make docker-prod-config
make docker-npm-config

# Follow logs and stop the service
make docker-logs
make docker-down
```

### Code Quality Standards
- **Dependency management**: uv with `uv.lock` as the lock source of truth
- **Testing**: pytest with route and service coverage
- **Linting**: Ruff and mypy type checking
- **Formatting**: Ruff formatter
- **Type Safety**: Full Pydantic v2 validation throughout

## 📖 Documentation

### Comprehensive Documentation
- **[Documentation Hub](docs/index.md)** - Complete documentation index
- **[Architecture Guide](docs/architecture.md)** - System design and components
- **[Usage Guide](docs/usage.md)** - Complete usage instructions
- **[Development Guide](docs/development.md)** - Development setup and guidelines
- **[API Reference](docs/api-reference.md)** - Complete REST API and MCP documentation

### Interactive Documentation
- **REST API**: Interactive docs at `http://localhost:8000/docs`
- **gnomAD Schema**: See `docs/gnomad_graphql/` for comprehensive API documentation
- **MCP Interface**: Available at `http://localhost:8000/mcp`

### Configuration Examples
- **[Claude Desktop Configuration](docs/claude_desktop_configurations.md)** - AI assistant integration
- **[MCP Connection Guide](docs/MCP_CONNECTION_GUIDE.md)** - MCP integration instructions

## 🚀 Production Deployment

### Docker Deployment

The Docker setup follows the same structure as the companion MCP repositories:
a multi-stage `uv` image, Compose overlays for development/production/Nginx
Proxy Manager, service-level health checks, and a root `.env.docker.example`
template.

```bash
cp .env.docker.example .env.docker
make docker-build
make docker-up
curl http://localhost:8020/health
```

For production or Nginx Proxy Manager deployment details, see
[docker/README.md](docker/README.md).

### Health Monitoring
```bash
# Check service health
curl http://localhost:8000/health

# Monitor cache performance
curl http://localhost:8000/api/cache/stats

# Clear cache if needed
curl -X POST http://localhost:8000/api/cache/clear
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Follow development guidelines in [docs/development.md](docs/development.md)
4. Run local CI: `make ci-local`
5. Submit a pull request

### Contribution Guidelines
- All tests must pass
- Code must pass `make ci-local`
- Maintain backwards compatibility
- Update documentation for new features
- Follow existing code patterns and style

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- **[gnomAD](https://gnomad.broadinstitute.org/)** - Genome Aggregation Database
- **[Broad Institute](https://www.broadinstitute.org/)** - gnomAD maintainers
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern web framework
- **[FastMCP](https://github.com/jlowin/fastmcp)** - MCP implementation
- **[Claude AI](https://claude.ai/)** - MCP protocol development

## 📚 Citation

If using this tool in research, please cite:

**gnomAD Database:**
```
Karczewski, K.J., Francioli, L.C., Tiao, G. et al. 
The mutational constraint spectrum quantified from variation in 141,456 humans. 
Nature 581, 434–443 (2020).
```

**gnomAD v4:**
```
Chen, S., Francioli, L.C., Goodrich, J.K. et al.
A genomic mutational constraint map using variation in 76,156 human genomes.
Nature 625, 92–100 (2024).
```

---

**Current Version**: 2.0.0 | **Status**: Production Ready
