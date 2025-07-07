"""Centralized GraphQL query loader."""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class QueryLoader:
    """Load and cache GraphQL queries from files."""

    def __init__(self):
        """Initialize the GraphQL query loader with empty cache."""
        self.base_path = Path(__file__).parent / "queries"
        self._query_cache: dict[str, str] = {}
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

        # Resolve fragments if needed (check for import or fragment usage)
        if "#import" in query_content or (
            "..." in query_content and "fragment" not in query_content
        ):
            query_content = self._resolve_fragments(query_content)

        # Cache it
        self._query_cache[cache_key] = query_content
        logger.debug(f"Loaded query '{query_name}' for {version}")

        return query_content

    def _resolve_fragments(self, query_content: str) -> str:
        """Resolve fragment imports in a query."""
        # Remove import statement
        if "#import" in query_content:
            lines = query_content.split("\n")
            lines = [line for line in lines if not line.strip().startswith("#import")]
            query_content = "\n".join(lines)

        # Load fragments if not cached
        if self._fragments_cache is None:
            fragments_path = self.base_path / "common" / "fragments.graphql"
            if fragments_path.exists():
                self._fragments_cache = fragments_path.read_text().strip()
            else:
                self._fragments_cache = ""

        # Find which fragments are used in the query
        used_fragments = set()

        # Extract fragment usage patterns
        fragment_usage_pattern = r"\.\.\.(\w+)"
        for match in re.finditer(fragment_usage_pattern, query_content):
            fragment_name = match.group(1)
            used_fragments.add(fragment_name)

        # Now find and include only the used fragments and their dependencies
        if used_fragments and self._fragments_cache:
            needed_fragments = []
            all_fragments = self._fragments_cache.split("\n\n")

            # Keep track of processed fragments to handle dependencies
            processed = set()
            to_process = list(used_fragments)

            while to_process:
                current_fragment = to_process.pop(0)
                if current_fragment in processed:
                    continue
                processed.add(current_fragment)

                # Find this fragment in the cache
                for fragment in all_fragments:
                    fragment_lines = fragment.strip().split("\n")
                    if not fragment_lines:
                        continue

                    # Check if this is the fragment we're looking for
                    for line in fragment_lines:
                        if line.startswith("fragment "):
                            fragment_match = re.match(r"fragment (\w+)", line)
                            if (
                                fragment_match
                                and fragment_match.group(1) == current_fragment
                            ):
                                needed_fragments.append(fragment)
                                # Check for nested fragment usage
                                for nested_match in re.finditer(
                                    fragment_usage_pattern, fragment
                                ):
                                    nested_name = nested_match.group(1)
                                    if nested_name not in processed:
                                        to_process.append(nested_name)
                                break

            if needed_fragments:
                query_content = "\n\n".join(needed_fragments) + "\n\n" + query_content

        return query_content

    def _list_available_queries(self, version: str) -> set[str]:
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
