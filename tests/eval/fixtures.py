"""Deterministic stub service + per-scenario builders for the MCP eval harness.

ARCHITECTURE NOTE (respx -> stub deviation)
-------------------------------------------
The plan text says to intercept upstream HTTP with respx. That cannot work here:
the real gnomAD client uses ``gql`` + ``AIOHTTPTransport`` (aiohttp), and respx
only patches ``httpx`` -- so respx would never see the client's requests. Instead
we inject a canned stub *service* via ``create_gnomad_mcp(service_factory=...)``.

This is fully deterministic, needs no network, and adds NO new dependency, while
still exercising the real MCP shaping / envelope / next_commands / headline code
(exactly the layers later phases change). The stub matches the small async call
surface that the five eval scenarios actually touch on ``FrequencyService``.

Canned response shapes are copied from the unit suite and adapted:
  * gene carrier  <- tests/unit/mcp/test_gene_carrier_tool.py (renamed CFTR->HFE)
  * compare       <- tests/unit/mcp/test_compare_variant.py (r2_1 liftover case)
  * mito          <- tests/unit/mcp/test_mt_heteroplasmy_trim.py
  * clinvar       <- tests/unit/mcp/test_clinvar_summary.py
  * resolve       <- tests/unit/mcp/test_resolve_enrichment.py
  * carrier (XL)  <- tests/unit/mcp/test_carrier_tool.py
  * gene variants <- tests/unit/mcp/test_gene_variants_population_trim.py
"""

from __future__ import annotations

from typing import Any

from gnomad_link.models import (
    ClinVarSubmission,
    ClinVarVariant,
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)


class EvalStubService:
    """Canned, no-network ``FrequencyService`` stand-in.

    Each method records its call on ``self.calls`` so the harness can read the
    actual service-call trajectory, and returns the seeded canned shape. A seeded
    ``BaseException`` value (for ``freq_by_dataset``) is raised to exercise the
    error path; otherwise the value is returned verbatim.
    """

    def __init__(
        self,
        *,
        gene_carrier: dict[str, Any] | None = None,
        freq_by_dataset: dict[str, VariantFrequencyResponse | BaseException] | None = None,
        liftover_result: list[dict[str, Any]] | None = None,
        mito_by_id: dict[str, dict[str, Any]] | None = None,
        clinvar_by_id: dict[str, ClinVarVariant] | None = None,
        search_ids: list[str] | None = None,
        gene_variants_by_id: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.client = None
        self._gene_carrier = gene_carrier or {}
        self._freq = freq_by_dataset or {}
        self._liftover = liftover_result or []
        self._mito = mito_by_id or {}
        self._clinvar = clinvar_by_id or {}
        self._search_ids = search_ids or []
        self._gene_variants = gene_variants_by_id or {}
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def get_gene_carrier_frequency(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_gene_carrier_frequency", (), kwargs))
        return self._gene_carrier

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        self.calls.append(("get_variant_frequencies", (variant_id, dataset), {}))
        out = self._freq[dataset]
        if isinstance(out, BaseException):
            raise out
        return out

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, Any]]:
        self.calls.append(("liftover_variant", (source_variant_id, reference_genome), {}))
        return list(self._liftover)

    async def get_mitochondrial_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        self.calls.append(("get_mitochondrial_variant", (variant_id, dataset), {}))
        return {"mitochondrial_variant": self._mito[variant_id]}

    async def get_clinvar_variant(self, variant_id: str, reference_genome: str) -> ClinVarVariant:
        self.calls.append(("get_clinvar_variant", (variant_id, reference_genome), {}))
        return self._clinvar[variant_id]

    async def search_variants(self, query: str, dataset: str) -> list[str]:
        self.calls.append(("search_variants", (query, dataset), {}))
        return list(self._search_ids)

    async def get_gene_variants(self, gene_id: str, dataset: str) -> list[dict[str, Any]]:
        self.calls.append(("get_gene_variants", (gene_id, dataset), {}))
        return self._gene_variants[gene_id]


# ---------------------------------------------------------------------------
# Canned shape helpers
# ---------------------------------------------------------------------------


def _carrier_metrics(cf: float, sum_af: float) -> dict[str, Any]:
    """Per-population/global metric block (copied from test_gene_carrier_tool)."""
    return {
        "carrier_frequency": cf,
        "sum_af": sum_af,
        "total_ac": 100,
        "max_an": 10000,
        "genetic_prevalence": sum_af * sum_af,
        "bayesian_prevalence": sum_af * sum_af,
        "method": "hom_exclusion",
    }


def _freq_response(
    variant_id: str,
    dataset: str,
    *,
    gene_symbol: str | None,
    major_consequence: str | None,
    populations: list[PopulationFrequency],
    ac: int = 200,
    an: int = 100_000,
    hemizygote_count: int | None = None,
) -> VariantFrequencyResponse:
    return VariantFrequencyResponse(
        variant_id=variant_id,
        dataset=dataset,
        gene_symbol=gene_symbol,
        major_consequence=major_consequence,
        exome=VariantDataSource(
            ac=ac,
            an=an,
            homozygote_count=0,
            hemizygote_count=hemizygote_count,
            populations=populations,
        ),
        genome=None,
    )


def _pop(pop_id: str, ac: int, an: int) -> PopulationFrequency:
    return PopulationFrequency.model_validate(
        {"id": pop_id, "ac": ac, "an": an, "homozygote_count": 0}
    )


def _gene_variant_row(variant_id: str, consequence: str, af: float, ac: int) -> dict[str, Any]:
    """A single get_gene_variants row (copied/adapted from test_gene_variants_population_trim)."""
    pos = int(variant_id.split("-")[1])
    return {
        "variant_id": variant_id,
        "pos": pos,
        "ref": "A",
        "alt": "T",
        "consequence": consequence,
        "af": af,
        "ac": ac,
        "exome": {
            "ac": ac,
            "an": 10_000,
            "af": af,
            "filters": [],
            "populations": [
                {"id": "afr", "ac": ac, "an": 4_000, "homozygote_count": 0},
                {"id": "nfe", "ac": 0, "an": 6_000, "homozygote_count": 0},
            ],
        },
        "genome": None,
    }


# ---------------------------------------------------------------------------
# Per-scenario stub builders
# ---------------------------------------------------------------------------


def build_gene_carrier_stub() -> EvalStubService:
    """Scenario 1: compute_gene_carrier_frequency(gene_symbol='HFE')."""
    gene_carrier = {
        "gene": {"gene_id": "ENSG00000010704", "symbol": "HFE"},
        "dataset": "gnomad_r4",
        "reference_genome": "GRCh38",
        "settings": {"method": "hom_exclusion"},
        "global": _carrier_metrics(0.0568, 0.029157),
        "populations": {
            "afr": _carrier_metrics(0.0228, 0.01127),
            "nfe": _carrier_metrics(0.0631, 0.031837),
            "asj": _carrier_metrics(0.1106, 0.055357),
        },
        "qualifying_variants": [],
        "qualifying_count": 523,
        "sources": {"plof_only": 121, "clinvar_only": 156, "both": 246},
    }
    return EvalStubService(gene_carrier=gene_carrier)


def build_compare_stub() -> EvalStubService:
    """Scenario 2: compare_variant_across_datasets across r4 + r2_1 with liftover."""
    pops = [_pop("nfe", 10, 50_000), _pop("afr", 100, 10_000)]
    return EvalStubService(
        freq_by_dataset={
            "gnomad_r4": _freq_response(
                "6-26092913-G-A",
                "gnomad_r4",
                gene_symbol="HFE",
                major_consequence="missense_variant",
                populations=pops,
            ),
            "gnomad_r2_1": _freq_response(
                "6-26093141-G-A",
                "gnomad_r2_1",
                gene_symbol="HFE",
                major_consequence="missense_variant",
                populations=pops,
            ),
        },
        # Corrected liftover: GRCh37 source 6-26093141-G-A -> GRCh38 6-26092913-G-A.
        liftover_result=[
            {
                "source": {"variant_id": "6-26093141-G-A", "reference_genome": "GRCh37"},
                "liftover": {"variant_id": "6-26092913-G-A", "reference_genome": "GRCh38"},
                "datasets": ["gnomad_r2_1", "gnomad_r4"],
            }
        ],
    )


def build_evidence_stub() -> EvalStubService:
    """Scenario 3: mitochondrial variant + ClinVar evidence (no verdict)."""
    edges = [round(i * 0.1, 1) for i in range(10)]
    mito_payload: dict[str, Any] = {
        "variant_id": "M-3243-A-G",
        "pos": 3243,
        "ref": "A",
        "alt": "G",
        "ac_het": 5,
        "ac_hom": 0,
        "an": 100,
        # gene_symbol lets the tool attach a next_commands chain to get_gene_details.
        "gene_symbol": "MT-TL1",
        "populations": [],
        "heteroplasmy_distribution": {
            "bin_edges": edges,
            "bin_freq": [0, 5, 0, 0, 3, 0, 0, 2, 0, 0],
        },
    }
    submissions = [
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Likely pathogenic"},
        {"clinical_significance": "Uncertain significance"},
        {"clinical_significance": "Benign"},
        {"clinical_significance": "Likely benign"},
    ]
    clinvar_variant = ClinVarVariant(
        variant_id="1-55051215-G-GA",
        reference_genome="GRCh38",
        chrom="1",
        pos=55051215,
        ref="G",
        alt="GA",
        clinical_significance="Pathogenic",
        clinvar_variation_id="12345",
        gnomad=None,
        gold_stars=2,
        in_gnomad=True,
        last_evaluated=None,
        review_status="criteria provided, multiple submitters, no conflicts",
        rsid=None,
        submissions=[ClinVarSubmission(**s) for s in submissions],
    )
    return EvalStubService(
        mito_by_id={"M-3243-A-G": mito_payload},
        clinvar_by_id={"1-55051215-G-GA": clinvar_variant},
    )


def build_resolve_carrier_stub() -> EvalStubService:
    """Scenario 4: resolve_variant_id then compute_carrier_frequency(inheritance='XL').

    The enrichment second pass and the XL carrier computation both call
    get_variant_frequencies on the same X-chromosome id, so a single seeded XL
    response (with XX/XY + ancestry sex-split rows) serves both calls. The XL
    response also drives the female/male carrier estimates the correctness check
    asserts on.
    """
    xl_response = _freq_response(
        "X-153296777-C-T",
        "gnomad_r4",
        gene_symbol="G6PD",
        major_consequence="missense_variant",
        populations=[
            _pop("XX", 100, 10_000),
            _pop("XY", 200, 10_000),
            _pop("nfe_XX", 60, 6_000),
            _pop("nfe_XY", 120, 6_000),
        ],
        ac=300,
        an=20_000,
        hemizygote_count=100,
    )
    return EvalStubService(
        search_ids=["X-153296777-C-T"],
        freq_by_dataset={"gnomad_r4": xl_response},
    )


def build_gene_variants_stub() -> EvalStubService:
    """Scenario 5: get_gene_variants(consequence='stop_gained')."""
    rows = [
        _gene_variant_row("12-1-A-T", "stop_gained", 0.0005, 5),
        _gene_variant_row("12-2-A-T", "missense_variant", 0.001, 10),
        _gene_variant_row("12-3-A-T", "stop_gained", 0.0002, 2),
        _gene_variant_row("12-4-A-T", "synonymous_variant", 0.002, 20),
    ]
    return EvalStubService(gene_variants_by_id={"ENSG00000273079": rows})
