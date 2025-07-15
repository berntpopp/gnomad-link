# Architecture Overview

## System Architecture

gnomAD-link implements a **unified server architecture** that serves as a bridge between the gnomAD (Genome Aggregation Database) and modern AI applications. The system provides dual interfaces - REST API for web clients and MCP (Model Context Protocol) for AI assistants - while maintaining shared business logic and caching.

### Architecture Overview

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

## Core Components

### 1. Transport Layer

The transport layer provides three distinct interfaces:

#### FastAPI/HTTP (REST + Documentation)
- **Purpose**: Traditional REST API for web clients
- **Features**: OpenAPI/Swagger documentation, CORS support, health checks
- **Endpoints**: `/api/variants/`, `/api/genes/`, `/api/search/`, etc.
- **Access**: `http://localhost:8000/docs`

#### MCP/HTTP (Streamable)
- **Purpose**: HTTP-based MCP interface for web-deployed AI assistants
- **Features**: Streamable HTTP transport, SSE fallback, JSON-RPC protocol
- **Tools**: `get_variant_frequency`, `search_genes`, `search_transcripts`, etc.
- **Access**: `http://localhost:8000/mcp`

#### MCP/STDIO (AI Assistants)
- **Purpose**: STDIO transport for local AI assistant integration
- **Features**: High-performance binary protocol, minimal logging overhead
- **Integration**: Claude Desktop, AI development tools
- **Performance**: ~10,000+ operations/second

### 2. Unified Server Manager

The `UnifiedServerManager` class orchestrates the entire system:

```python
class UnifiedServerManager:
    """Manages multiple transport protocols for gnomAD server."""
    
    async def create_fastapi_app(self) -> FastAPI:
        """Create FastAPI application with proper lifecycle."""
        
    async def create_mcp_server(self, app: FastAPI) -> FastMCP:
        """Create FastMCP server from FastAPI app."""
        
    async def start_unified_server(self, config: ServerConfig):
        """Start server with FastAPI + MCP HTTP."""
        
    async def start_stdio_server(self, config: ServerConfig):
        """Start STDIO-only MCP server."""
        
    async def start_http_only_server(self, config: ServerConfig):
        """Start FastAPI-only server (no MCP)."""
```

**Key Responsibilities**:
- Transport selection and orchestration
- Async lifecycle management
- Shared service instance coordination
- Configuration validation and application
- Graceful shutdown handling

### 3. Business Logic Layer

#### FrequencyService
- **Purpose**: Core business logic for variant frequency queries
- **Features**: Async-LRU caching, version-aware routing, error handling
- **Cache**: Configurable size and TTL for optimal performance
- **Integration**: Shared across all transport interfaces

#### GraphQLClient (UnifiedGnomadClient)
- **Purpose**: Version-aware GraphQL communication with gnomAD API
- **Features**: Automatic version routing, timeout handling, connection pooling
- **Versions**: Supports gnomAD v2, v3, and v4 APIs
- **Queries**: Organized by version and functionality

#### CacheManager
- **Purpose**: Centralized caching for all data operations
- **Implementation**: Async-LRU with configurable parameters
- **Sharing**: Single cache instance across all transports
- **Monitoring**: Cache hit/miss metrics and statistics

### 4. Data Layer

#### GraphQL Query System
- **Structure**: Version-specific query organization (`v2/`, `v3/`, `v4/`, `common/`)
- **Loading**: Dynamic query loading with caching
- **Building**: Parameter processing and version-aware field selection
- **Fragments**: Reusable query components

#### gnomAD API Integration
- **Endpoints**: Direct integration with gnomAD's GraphQL API
- **Versions**: Automatic dataset-to-version mapping
- **Error Handling**: Comprehensive error parsing and classification
- **Timeouts**: Configurable timeouts with retry logic

## Transport Selection

The system supports three deployment modes:

### 1. Unified Transport (Recommended)
```bash
python server.py --transport unified --port 8000
```

**Features**:
- Single server process
- Both REST API and MCP HTTP available
- Shared cache and services
- Optimal resource utilization

**Access Points**:
- REST API: `http://localhost:8000/docs`
- MCP HTTP: `http://localhost:8000/mcp`
- Health Check: `http://localhost:8000/health`

### 2. STDIO Transport (AI Assistants)
```bash
python server.py --transport stdio
```

**Features**:
- High-performance binary protocol
- Minimal logging overhead (stderr only)
- Optimized for AI assistant integration
- Claude Desktop compatible

**Usage**:
```json
{
  "mcpServers": {
    "gnomad": {
      "command": "python",
      "args": ["/path/to/server.py", "--transport", "stdio"]
    }
  }
}
```

### 3. HTTP-Only Transport (Pure REST)
```bash
python server.py --transport http --port 8000
```

**Features**:
- FastAPI-only deployment
- No MCP overhead
- Traditional REST API server
- Swagger documentation

## Configuration System

### ServerConfig
```python
@dataclass
class ServerConfig:
    """Server configuration with transport selection."""
    
    transport: Literal["unified", "http", "stdio"] = "unified"
    host: str = "127.0.0.1"
    port: int = 8000
    mcp_path: str = "/mcp"
    enable_docs: bool = True
    log_level: str = "INFO"
```

### Environment Variables
```bash
# Transport Configuration
MCP_TRANSPORT=unified
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_PATH=/mcp

# Logging Configuration
LOG_LEVEL=INFO
MCP_LOG_LEVEL=INFO
STDIO_LOG_LEVEL=WARNING

# gnomAD Configuration
GNOMAD_API_URL=https://gnomad.broadinstitute.org/api
CACHE_SIZE=1024
CACHE_TTL_MINUTES=60
```

## Error Handling

### Exception Hierarchy
```python
class TransportError(Exception):
    """Base exception for transport-related errors."""

class ConfigurationError(TransportError):
    """Configuration validation errors."""

class StartupError(TransportError):
    """Server startup errors."""

class MCPIntegrationError(TransportError):
    """MCP integration errors."""
```

### Error Responses
- **REST API**: Standard HTTP status codes with JSON error responses
- **MCP HTTP**: JSON-RPC error format with proper error codes
- **STDIO**: Structured error objects with context information

## Logging System

### Transport-Aware Logging
```python
class TransportAwareFormatter(logging.Formatter):
    """Formatter that includes transport context in log messages."""
    
    def format(self, record):
        # Add transport context to log messages
        if hasattr(record, 'transport'):
            record.transport_prefix = f"[{record.transport.upper()}]"
        return super().format(record)
```

### Log Levels by Transport
- **Unified/HTTP**: Full logging with configurable levels
- **STDIO**: WARNING level only to stderr (protocol compatibility)
- **Development**: DEBUG level with enhanced output

## Performance Considerations

### Caching Strategy
- **Async-LRU**: Non-blocking cache operations
- **Shared Cache**: Single cache instance across all transports
- **Configurable TTL**: Balance between freshness and performance
- **Cache Statistics**: Monitoring and optimization metrics

### Connection Pooling
- **HTTP Connections**: Reused across requests
- **GraphQL Client**: Persistent connection to gnomAD API
- **Resource Cleanup**: Proper async context management

### Monitoring
- **Health Checks**: Per-transport health endpoints
- **Metrics**: Request/response times, cache hit rates
- **Logging**: Structured logging with performance context

## Security

### Input Validation
- **Pydantic Models**: Comprehensive input validation
- **Type Safety**: Full type annotations throughout
- **Error Sanitization**: Safe error messages without sensitive data

### CORS Configuration
- **Configurable Origins**: Environment-based CORS setup
- **Development Mode**: Permissive CORS for local development
- **Production Mode**: Strict CORS configuration

### Transport Security
- **HTTP**: Standard web security headers
- **STDIO**: Isolated process communication
- **Error Handling**: No sensitive data in error responses

## Deployment Patterns

### Docker Deployment
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["python", "server.py", "--transport", "unified", "--port", "8000"]
```

### Production Configuration
```yaml
services:
  gnomad-unified:
    environment:
      - MCP_TRANSPORT=unified
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8000
      - ENABLE_MONITORING=true
      - LOG_LEVEL=INFO
    ports:
      - "8000:8000"
```

### Health Checks
```bash
# REST API health
curl http://localhost:8000/health

# MCP HTTP health
curl http://localhost:8000/mcp/health

# Cache statistics
curl http://localhost:8000/api/cache/stats
```

This unified architecture provides a robust, scalable, and maintainable foundation for bridging gnomAD data to both traditional web clients and modern AI applications through a single, efficient server implementation.