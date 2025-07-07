"""FastAPI route modules."""

from .clinvar import router as clinvar_router
from .gene import router as gene_router
from .mitochondrial import router as mitochondrial_router
from .region import router as region_router
from .search import router as search_router
from .structural_variant import router as structural_variant_router
from .transcript import router as transcript_router
from .variant import router as variant_router

__all__ = [
    "variant_router",
    "gene_router",
    "clinvar_router",
    "structural_variant_router",
    "mitochondrial_router",
    "region_router",
    "transcript_router",
    "search_router",
]
