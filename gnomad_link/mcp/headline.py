"""Plain-English one-line ``headline`` builders for high-value tool payloads.

Anthropic's *Writing tools for agents* guidance: "return only high signal
information… agents grapple with natural language… more successfully than
cryptic identifiers." A single headline string at the top of a payload lets the
LLM answer the user without walking nested numeric structures.

Every builder is null-safe: missing fields degrade gracefully (a clause is
dropped or rendered "unknown") and a builder never raises, so a headline can be
attached unconditionally.
"""

from __future__ import annotations

from typing import Any


def _num(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _fmt_af(value: Any) -> str | None:
    """Compact allele-frequency rendering: 2 significant figures, sci for tiny."""
    v = _num(value)
    if v is None:
        return None
    if v == 0:
        return "0"
    return f"{v:.2g}"


def _fmt_freq(value: Any) -> str | None:
    """Carrier/affected frequency rendering: readable fixed-point, sci for tiny."""
    v = _num(value)
    if v is None:
        return None
    if v == 0:
        return "0"
    if abs(v) >= 0.01:
        return f"{v:.3f}"
    if abs(v) >= 0.0001:
        return f"{v:.4f}"
    return f"{v:.2e}"


def gene_carrier_headline(shaped: dict[str, Any]) -> str:
    """Headline for compute_gene_carrier_frequency (reads the shaped result)."""
    gene = shaped.get("gene") or {}
    symbol = gene.get("symbol") or gene.get("gene_id") or "gene"
    dataset = shaped.get("dataset") or "gnomad"
    global_metrics = shaped.get("global") or {}
    g_one_in = global_metrics.get("carrier_one_in")
    contributing = shaped.get("contributing_variants") or {}
    count = contributing.get("count")

    if isinstance(g_one_in, int) and g_one_in > 0:
        lead = f"carrier frequency 1 in {g_one_in} globally"
    else:
        lead = "carrier frequency unavailable globally"
    parts = [f"{symbol} ({dataset}): {lead}"]

    populations = shaped.get("populations") or []
    top = populations[0] if populations else None
    if isinstance(top, dict):
        top_one_in = top.get("carrier_one_in")
        top_pop = top.get("population")
        if isinstance(top_one_in, int) and top_one_in > 0 and top_pop:
            parts.append(f"highest 1 in {top_one_in} ({top_pop})")

    if isinstance(count, int):
        parts.append(f"{count} qualifying variants")

    return "; ".join(parts) + ". Research use only."


def variant_carrier_headline(result: dict[str, Any]) -> str:
    """Inheritance-aware headline for compute_carrier_frequency."""
    variant_id = result.get("variant_id") or "variant"
    inheritance = result.get("inheritance") or "?"
    dataset = result.get("dataset") or "gnomad"
    method = result.get("method")
    overall = result.get("overall") or {}
    prefix = f"{variant_id} ({inheritance}/{dataset}):"

    if inheritance == "AD":
        freq = _fmt_freq(overall.get("affected_or_carrier_frequency"))
        body = f"affected-or-carrier frequency {freq}" if freq else "frequency unavailable"
    elif inheritance == "XL":
        female = _fmt_freq(overall.get("female_carrier_frequency"))
        male = _fmt_freq(overall.get("affected_male_frequency"))
        bits = []
        if female:
            bits.append(f"female carrier frequency {female}")
        if male:
            bits.append(f"affected male frequency {male}")
        body = ", ".join(bits) if bits else "frequency unavailable"
    else:  # AR (default)
        cf = _fmt_freq(overall.get("carrier_frequency"))
        lo = _fmt_freq(overall.get("ci_low"))
        hi = _fmt_freq(overall.get("ci_high"))
        if cf and lo and hi:
            body = f"carrier frequency {cf} (95% CI {lo}-{hi})"
        elif cf:
            body = f"carrier frequency {cf}"
        else:
            body = "carrier frequency unavailable"

    summary = result.get("summary") or {}
    max_pop = summary.get("max_carrier_frequency_population")
    tail = f"; highest in {max_pop}" if max_pop else ""
    method_tail = f". method={method}" if method else "."
    return f"{prefix} {body}{tail}{method_tail}"


def variant_frequencies_headline(payload: dict[str, Any]) -> str:
    """Headline for get_variant_frequencies (reads the shaped summary block)."""
    variant_id = payload.get("variant_id") or "variant"
    dataset = payload.get("dataset") or "gnomad"
    consequence = payload.get("major_consequence")
    summary = payload.get("summary")

    if not isinstance(summary, dict):
        return f"{variant_id} ({dataset}): no allele-frequency data."

    overall = _fmt_af(summary.get("overall_af"))
    lead = f"{variant_id}"
    if consequence:
        lead += f" {consequence}"
    body = f"AF {overall} in {dataset}" if overall else f"observed in {dataset}"
    parts = [f"{lead}: {body}"]

    max_pop = summary.get("max_pop")
    max_pop_af = _fmt_af(summary.get("max_pop_af"))
    if max_pop and max_pop_af:
        parts.append(f"highest in {max_pop} (AF {max_pop_af})")
    return "; ".join(parts) + "."


def gene_details_headline(result: dict[str, Any], *, reference_genome: str) -> str:
    """Headline for get_gene_details (reads the Gene model dump)."""
    symbol = result.get("symbol") or "gene"
    gene_id = result.get("gene_id") or "?"
    constraint = result.get("gnomad_constraint") or {}
    pli = _num(constraint.get("pli"))
    oe_lof = _num(constraint.get("oe_lof"))

    if pli is not None and oe_lof is not None:
        constraint_clause = f"pLI {pli:.3f}, LoF o/e {oe_lof:.2f}"
    elif pli is not None:
        constraint_clause = f"pLI {pli:.3f}"
    elif oe_lof is not None:
        constraint_clause = f"LoF o/e {oe_lof:.2f}"
    else:
        constraint_clause = "constraint unavailable"

    chrom = result.get("chrom")
    start = result.get("start")
    stop = result.get("stop")
    parts = [f"{symbol} ({gene_id}): {constraint_clause}"]
    if chrom is not None and start is not None and stop is not None:
        parts.append(f"{chrom}:{start}-{stop} ({reference_genome})")
    return "; ".join(parts) + "."
