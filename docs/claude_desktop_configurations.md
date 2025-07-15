# Claude Desktop Configuration Examples

This document provides complete configuration examples for integrating gnomAD-link with Claude Desktop.

## Overview

gnomAD-link supports multiple integration methods:

1. **STDIO Transport** (Recommended for Claude Desktop) - Direct process communication
2. **HTTP Transport** - Web-based integration for testing

## STDIO Transport Configuration (Recommended)

### For Unix/Linux/macOS

```json
{
  "mcpServers": {
    "gnomad-link": {
      "command": "python",
      "args": ["/path/to/gnomad-link/mcp_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

### For Windows

```json
{
  "mcpServers": {
    "gnomad-link": {
      "command": "python",
      "args": ["C:\\path\\to\\gnomad-link\\mcp_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

### Alternative: Using the Unified Server

You can also use the new unified server in STDIO mode:

```json
{
  "mcpServers": {
    "gnomad-link": {
      "command": "python",
      "args": ["/path/to/gnomad-link/server.py", "--transport", "stdio"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

## HTTP Transport Configuration (Advanced)

For testing or development, you can use HTTP transport with Claude Desktop:

### Step 1: Start the Server
```bash
python server.py --transport unified --port 8000
```

### Step 2: Configure Claude Desktop for HTTP MCP
```json
{
  "mcpServers": {
    "gnomad-link-http": {
      "transport": {
        "type": "http",
        "url": "http://localhost:8000/mcp"
      }
    }
  }
}
```

### Alternative HTTP Configuration (if above doesn't work)
Some Claude Desktop versions may require this format:
```json
{
  "mcpServers": {
    "gnomad-link-http": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", "@-",
        "http://localhost:8000/mcp"
      ],
      "env": {
        "CONTENT_TYPE": "application/json"
      }
    }
  }
}
```

### Testing HTTP MCP Connection
You can test the HTTP MCP endpoint with a proper MCP client:
```bash
# Start the server
python server.py --transport unified --port 8000

# The MCP endpoint will be available at:
# http://localhost:8000/mcp
# But requires MCP-compliant JSON-RPC messages
```

## Configuration File Locations

### macOS
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### Windows
```
%APPDATA%\Claude\claude_desktop_config.json
```

### Linux
```
~/.config/Claude/claude_desktop_config.json
```

## Environment Variables

You can customize the server behavior using environment variables:

```json
{
  "mcpServers": {
    "gnomad-link": {
      "command": "python",
      "args": ["/path/to/gnomad-link/mcp_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "WARNING",
        "GNOMAD_API_URL": "https://gnomad.broadinstitute.org/api",
        "CACHE_SIZE": "1024",
        "CACHE_TTL_MINUTES": "60"
      }
    }
  }
}
```

## Available Tools

Once configured, Claude Desktop will have access to these gnomAD tools:

- **get_variant_frequencies**: Query variant allele frequencies across populations
- **search_variants**: Search for variants by ID or position
- **search_genes**: Search for genes by symbol or ID
- **search_transcripts**: Search for transcripts with filtering options
- **get_structural_variants**: Query structural variants in genomic regions
- **search_clinvar_variants**: Search for ClinVar variants with clinical significance
- **get_gene_details**: Get comprehensive gene information
- **get_clinvar_variant_details**: Get detailed ClinVar annotations

## Troubleshooting

### Common Issues

1. **Server won't start**
   - Check that Python is in your PATH
   - Verify the path to the gnomAD-link directory
   - Check logs in Claude Desktop

2. **Tools not appearing**
   - Restart Claude Desktop after configuration changes
   - Check the JSON syntax in your config file
   - Verify PYTHONUNBUFFERED=1 is set

3. **Permission errors**
   - Ensure Python has execution permissions
   - Check file paths are accessible
   - On Windows, use full paths with backslashes

### Testing Your Configuration

Before using with Claude Desktop, test the MCP server directly:

```bash
# Test STDIO server
python mcp_server.py

# Test unified server
python server.py --transport stdio

# Test configuration validation
python server.py config --validate
```

### Debugging

For debugging, you can increase the log level:

```json
{
  "env": {
    "PYTHONUNBUFFERED": "1",
    "LOG_LEVEL": "DEBUG"
  }
}
```

## Performance Optimization

For better performance, you can adjust cache settings:

```json
{
  "env": {
    "PYTHONUNBUFFERED": "1",
    "LOG_LEVEL": "WARNING",
    "CACHE_SIZE": "2048",
    "CACHE_TTL_MINUTES": "120"
  }
}
```

## Security Considerations

- The STDIO transport is more secure than HTTP as it doesn't expose network endpoints
- Log levels should be set to WARNING or ERROR for production use
- Consider firewall rules if using HTTP transport

## Example Complete Configuration

Here's a complete, production-ready configuration:

```json
{
  "mcpServers": {
    "gnomad-link": {
      "command": "python",
      "args": ["/path/to/gnomad-link/mcp_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "WARNING",
        "GNOMAD_API_URL": "https://gnomad.broadinstitute.org/api",
        "CACHE_SIZE": "1024",
        "CACHE_TTL_MINUTES": "60",
        "CORS_ORIGINS": "*"
      }
    }
  }
}
```

This configuration provides optimal performance and security for Claude Desktop integration.