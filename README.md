# gnomAD Link

A unified server that bridges the gnomAD (Genome Aggregation Database) to modern AI applications through dual interfaces: REST API and MCP (Model Context Protocol).

## 🎯 Core Purpose

This server provides programmatic access to human genetic variation data from gnomAD, the world's largest public database of human genetic variants. It enables:

- **Researchers**: Query variant frequencies across global populations via REST API
- **AI Assistants**: Access gnomAD data through native tool interfaces (MCP)
- **Developers**: Build applications using standardized genetic variant data

## 🚀 Key Features

- **Unified Architecture**: Single server process serving both REST and MCP interfaces
- **Comprehensive Data Access**: Variants, genes, transcripts, structural variants, ClinVar annotations
- **Population Genetics**: Allele frequencies across 8 global populations
- **High Performance**: Async operations with intelligent caching
- **Type Safety**: Full Pydantic validation and auto-generated documentation

## 📦 Quick Start

```bash
# Install
git clone <repository-url>
cd gnomad-link
pip install -e .

# Run unified server
python server.py

# Access REST API at http://localhost:8000/docs
# MCP interface available at http://localhost:8000/mcp
```

## 🔧 Configuration

Create `.env` file:
```env
GNOMAD_API_URL=https://gnomad.broadinstitute.org/api
CACHE_SIZE=1024
CACHE_TTL_MINUTES=60
LOG_LEVEL=INFO
```

## 📡 Usage Examples

### REST API
```bash
# Query variant frequency
curl "http://localhost:8000/api/variants/1-55039447-G-T?dataset=gnomad_r4"

# Search for gene
curl "http://localhost:8000/api/search/gene?query=BRCA2"

# Get ClinVar annotations
curl "http://localhost:8000/api/clinvar/variant/7-117559590-ATCT-A?reference_genome=GRCh38"
```

### MCP Integration

For Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "gnomad": {
      "command": "python",
      "args": ["/path/to/gnomad-link/mcp_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   REST Client   │     │  AI Assistant   │
└────────┬────────┘     └────────┬────────┘
         │ HTTP                  │ MCP/HTTP
         ▼                       ▼
┌─────────────────────────────────────────┐
│          Unified Server (FastAPI)        │
│  ┌────────────┐       ┌──────────────┐  │
│  │ REST Routes│       │ MCP Handler  │  │
│  └─────┬──────┘       └──────┬───────┘  │
│        └──────────┬──────────┘          │
│                   ▼                      │
│          ┌─────────────────┐            │
│          │ Frequency Service│            │
│          │   (with cache)   │            │
│          └────────┬────────┘            │
│                   ▼                      │
│          ┌─────────────────┐            │
│          │ GraphQL Client  │            │
│          └────────┬────────┘            │
└───────────────────┼─────────────────────┘
                    ▼
           ┌─────────────────┐
           │   gnomAD API    │
           └─────────────────┘
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
- `/api/health` - Service health check

## 🧬 Understanding gnomAD

gnomAD aggregates genetic data from hundreds of thousands of individuals to provide:
- **Population Frequencies**: How common variants are across different ancestries
- **Constraint Metrics**: How tolerant genes are to mutations
- **Clinical Annotations**: Disease associations from ClinVar
- **Quality Metrics**: Sequencing depth and quality scores

### Useful Resources
- [gnomAD Browser](https://gnomad.broadinstitute.org/)
- [gnomAD API Documentation](https://gnomad.broadinstitute.org/api)
- [GA4GH Standards Integration](https://gnomad.broadinstitute.org/news/2023-11-ga4gh-gks/)
- [gnomAD GraphQL Playground](https://gnomad.broadinstitute.org/api)

## 🛠️ Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint code
make lint

# Format code
make format

# Generate gnomAD API documentation
python scripts/generate_gnomad_docs.py
```

## 📖 Documentation

- **REST API**: Interactive docs at `http://localhost:8000/docs`
- **gnomAD Schema**: See `docs/gnomad_graphql/` for comprehensive API documentation
- **MCP Tools**: Available at `http://localhost:8000/mcp/docs`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests and linting
4. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- [gnomAD](https://gnomad.broadinstitute.org/) - Genome Aggregation Database
- [Broad Institute](https://www.broadinstitute.org/) - gnomAD maintainers
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP implementation

## 📚 Citation

If using this tool in research, please cite:

**gnomAD Database:**
```
Karczewski, K.J., Francioli, L.C., Tiao, G. et al. 
The mutational constraint spectrum quantified from variation in 141,456 humans. 
Nature 581, 434–443 (2020).
```