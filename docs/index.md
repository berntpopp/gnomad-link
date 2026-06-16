# gnomAD-Link Documentation

Welcome to the documentation for gnomAD-link, an MCP server that bridges the gnomAD (Genome Aggregation Database) to AI applications. FastAPI is a thin host providing `/health` only; all domain functionality is exposed via MCP.

## 📖 Documentation Overview

### 🚀 **Getting Started**
- [**Usage Guide**](usage.md) - Complete usage instructions for all deployment modes
- [**MCP Connection Guide**](MCP_CONNECTION_GUIDE.md) - MCP integration instructions
- [**Claude And MCP Configuration**](claude_desktop_configurations.md) - AI assistant integration guide

### 🏗️ **Architecture & Development**
- [**Architecture Overview**](architecture.md) - System design and component documentation
- [**Development Guide**](development.md) - Development setup, testing, and contribution guidelines
- [**Implementation Summary**](IMPLEMENTATION_SUMMARY.md) - Technical implementation details

### 🔧 **Configuration & Deployment**
- [**MCP Connection Guide**](MCP_CONNECTION_GUIDE.md) - MCP integration instructions
- [**MCP Endpoint Explanation**](MCP_ENDPOINT_EXPLANATION.md) - Technical MCP details
- [**Directory Organization**](DIRECTORY_ORGANIZATION.md) - Project structure overview

### 📋 **Project Management**
- [**Implementation Plan**](PLAN.md) - Complete refactoring plan and strategy
- [**TODO & Status**](TODO.md) - Implementation tasks and completion status

### 🧬 **gnomAD Integration**
- [**GraphQL API Reference**](gnomad_graphql/gnomad_graphql_api_reference.md) - gnomAD API documentation
- [**Query Cookbook**](gnomad_graphql/gnomad_query_cookbook.md) - GraphQL query examples
- [**Quick Start Guide**](gnomad_graphql/gnomad_quick_start.md) - Getting started with gnomAD data

## 🎯 **Quick Navigation**

### For Users
- **New to gnomAD-link?** → Start with [Usage Guide](usage.md)
- **Setting up Claude or MCP?** → Follow [MCP Connection Guide](MCP_CONNECTION_GUIDE.md)
- **Configuring AI assistants?** → Follow [Claude And MCP Configuration](claude_desktop_configurations.md)

### For Developers
- **Contributing to the project?** → Read [Development Guide](development.md)
- **Understanding the architecture?** → Review [Architecture Overview](architecture.md)
- **Working with gnomAD data?** → Explore [GraphQL documentation](gnomad_graphql/)

### For Operators
- **Deploying the service?** → Follow [Usage Guide - Production Deployment](usage.md#production-deployment)
- **Monitoring and debugging?** → Check [Usage Guide - Monitoring](usage.md#monitoring-and-debugging)

## 🏆 **Project Status**

**Current Version**: 2.0.0  
**Architecture**: Unified server with transport selection  

### Key Features ✨
- **MCP-First Architecture**: Hand-authored FastMCP facade; FastAPI is `/health` only
- **15 MCP Tools**: Variants, genes, ClinVar, structural, mitochondrial, liftover, search
- **Transport**: Streamable HTTP only (unified FastAPI host + mounted MCP)
- **AI Assistant Integration**: Native MCP support for Claude Code, Claude Desktop, ChatGPT
- **Production Ready**: Docker Compose, health checks, structured error envelopes

## 🚀 **Quick Start**

### Installation
```bash
git clone <repository-url>
cd gnomad-link
uv sync --group dev
```

### Basic Usage
```bash
# Start MCP HTTP server
make dev

# MCP interface available at
# http://127.0.0.1:8000/mcp
# Health check at
# http://127.0.0.1:8000/health
```

### Claude HTTP Integration

Start the server:

```bash
make dev
```

Register the HTTP MCP endpoint:

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

## 🌟 **Key Capabilities**

### MCP Interface
- **AI Assistant Tools**: Native integration with Claude and MCP clients
- **Streamable HTTP**: Modern MCP transport for web deployments
- **Tool-Based Interface**: Structured data access for AI applications

### Data Sources
- **gnomAD v2**: Exome data with 125k+ individuals
- **gnomAD v3**: Genome data with 76k+ individuals  
- **gnomAD v4**: Latest release with 730k+ individuals
- **ClinVar**: Clinical variant annotations
- **Structural Variants**: Large genomic rearrangements
- **Mitochondrial Variants**: Mitochondrial genome variants

## 🔗 **External Resources**

### gnomAD Resources
- [gnomAD Browser](https://gnomad.broadinstitute.org/) - Interactive variant browser
- [gnomAD API](https://gnomad.broadinstitute.org/api) - GraphQL API playground
- [gnomAD Documentation](https://gnomad.broadinstitute.org/help) - Official help and documentation

### MCP Resources
- [MCP Specification](https://spec.modelcontextprotocol.io/) - Official MCP protocol specification
- [FastMCP Library](https://github.com/jlowin/fastmcp) - Python MCP implementation
- [Claude Desktop](https://claude.ai/desktop) - AI assistant with MCP support

### Development Resources
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Web framework documentation
- [Pydantic Documentation](https://docs.pydantic.dev/) - Data validation library
- [GraphQL Documentation](https://graphql.org/) - GraphQL specification

## 🤝 **Contributing**

We welcome contributions! Please see our [Development Guide](development.md) for:
- Development environment setup
- Code style guidelines
- Testing requirements
- Contribution workflow

## 📄 **License**

MIT License - see [LICENSE](../LICENSE) file for details.

## 🙏 **Acknowledgments**

- **gnomAD Team** - For creating and maintaining the world's largest genetic variation database
- **Broad Institute** - For hosting and supporting the gnomAD project
- **FastAPI Community** - For the excellent web framework
- **FastMCP Team** - For the MCP implementation library
- **Claude AI** - For MCP protocol development and AI assistant integration

---

*This documentation is maintained as part of the gnomAD-link project. For questions or suggestions, please open an issue in the project repository.*
