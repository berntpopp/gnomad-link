"""Centralized GraphQL query loader."""

from pathlib import Path
from typing import Dict, Optional, Set
import logging

logger = logging.getLogger(__name__)


class QueryLoader:
    """Load and cache GraphQL queries from files."""

    def __init__(self):
        self.base_path = Path(__file__).parent / "queries"
        self._query_cache: Dict[str, str] = {}
        self._fragments_cache: Optional[str] = None

    def load_query(self, query_name: str, version: str = "v4") -> str:
        """Load a GraphQL query from file.

        Args:
            query_name: Name of the query (e.g., 'variant', 'gene')
            version: API version (v2, v3, v4)

        Returns:
            Query string with fragments resolved
        """
        cache_key = f"{version}/{query_name}"

        # Check cache
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        # Try version-specific first, then common
        query_path = self.base_path / version / f"{query_name}.graphql"
        if not query_path.exists():
            query_path = self.base_path / "common" / f"{query_name}.graphql"

        if not query_path.exists():
            raise FileNotFoundError(
                f"Query '{query_name}' not found for {version}. "
                f"Available: {self._list_available_queries(version)}"
            )

        # Load query
        query_content = query_path.read_text().strip()

        # Resolve fragments if needed (check for any fragment usage)
        if "..." in query_content and "fragment" not in query_content:
            query_content = self._resolve_fragments(query_content)

        # Cache it
        self._query_cache[cache_key] = query_content
        logger.debug(f"Loaded query '{query_name}' for {version}")

        return query_content

    def _resolve_fragments(self, query_content: str) -> str:
        """Resolve fragment imports in a query."""
        # Load fragments if not cached
        if self._fragments_cache is None:
            fragments_path = self.base_path / "common" / "fragments.graphql"
            if fragments_path.exists():
                self._fragments_cache = fragments_path.read_text().strip()
            else:
                self._fragments_cache = ""

        # Remove import statement and prepend fragments
        if "#import" in query_content:
            lines = query_content.split("\n")
            lines = [line for line in lines if not line.strip().startswith("#import")]
            query_content = "\n".join(lines)

        # Prepend fragments if we have any
        if self._fragments_cache:
            query_content = self._fragments_cache + "\n\n" + query_content

        return query_content

    def _list_available_queries(self, version: str) -> Set[str]:
        """List available queries for a version."""
        queries = set()

        # Check version-specific
        version_path = self.base_path / version
        if version_path.exists():
            queries.update(f.stem for f in version_path.glob("*.graphql"))

        # Check common
        common_path = self.base_path / "common"
        if common_path.exists():
            queries.update(
                f.stem for f in common_path.glob("*.graphql") if f.stem != "fragments"
            )

        return queries
