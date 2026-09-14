from __future__ import annotations

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables


def iter_langsys(script: otTables.Script):
    if script.DefaultLangSys is not None:
        yield script.DefaultLangSys
    for record in script.LangSysRecord or []:
        yield record.LangSys


def _adjust_feature_indices_for_insert(gsub: otTables.GSUB, insert_at: int) -> None:
    for script_record in gsub.ScriptList.ScriptRecord:
        for langsys in iter_langsys(script_record.Script):
            if langsys.ReqFeatureIndex != 0xFFFF and langsys.ReqFeatureIndex >= insert_at:
                langsys.ReqFeatureIndex += 1
            langsys.FeatureIndex = [
                i + 1 if i >= insert_at else i
                for i in (langsys.FeatureIndex or [])
            ]
            langsys.FeatureCount = len(langsys.FeatureIndex)


def _default_langsys(gsub: otTables.GSUB, script_tag: str) -> otTables.LangSys:
    record = next((r for r in gsub.ScriptList.ScriptRecord if r.ScriptTag == script_tag), None)
    if record is None or record.Script.DefaultLangSys is None:
        raise RuntimeError(f"GSUB has no {script_tag}/dflt LangSys")
    return record.Script.DefaultLangSys


def add_dflt_liga_route(font: TTFont) -> dict[str, int]:
    """Expose D2Coding's programming-ligature lookups through DFLT/liga.

    D2Coding 1.3.3 exposes the programming substitutions through `calt`.
    Older HarfBuzz Hangul shaping suppresses `calt` for the whole Hangul run.
    Hangul has no dedicated GSUB script in D2Coding, so it falls back to DFLT.
    Adding a DFLT `liga` route keeps the same lookups available without adding
    a `hang` ScriptRecord and therefore without shadowing DFLT fallback.
    """
    if "GSUB" not in font:
        raise RuntimeError("Font has no GSUB table")

    gsub = font["GSUB"].table
    records = gsub.FeatureList.FeatureRecord

    liga_indices = [i for i, r in enumerate(records) if r.FeatureTag == "liga"]
    if liga_indices:
        raise RuntimeError(
            "Target already contains a liga feature; refusing an ambiguous patch."
        )

    calt_records = [r for r in records if r.FeatureTag == "calt"]
    if not calt_records:
        raise RuntimeError("No calt feature found; expected D2Coding ligature build")

    lookup_indices: list[int] = []
    seen: set[int] = set()
    for record in calt_records:
        for i in record.Feature.LookupListIndex or []:
            if i not in seen:
                seen.add(i)
                lookup_indices.append(i)
    if not lookup_indices:
        raise RuntimeError("calt feature contains no lookups")

    # OpenType FeatureRecords are ordered by tag. 1.3.3 only has tags before
    # `liga`, but this also handles future tags by fixing every LangSys index.
    insert_at = next(
        (i for i, r in enumerate(records) if r.FeatureTag > "liga"),
        len(records),
    )
    _adjust_feature_indices_for_insert(gsub, insert_at)

    feature = otTables.Feature()
    feature.FeatureParams = None
    feature.LookupListIndex = lookup_indices
    feature.LookupCount = len(lookup_indices)

    feature_record = otTables.FeatureRecord()
    feature_record.FeatureTag = "liga"
    feature_record.Feature = feature
    records.insert(insert_at, feature_record)
    gsub.FeatureList.FeatureCount = len(records)

    dflt = _default_langsys(gsub, "DFLT")
    if insert_at not in dflt.FeatureIndex:
        dflt.FeatureIndex.append(insert_at)
        dflt.FeatureIndex.sort()
        dflt.FeatureCount = len(dflt.FeatureIndex)

    # Intentionally DO NOT create a `hang` script. Hangul must keep using the
    # DFLT script, where `liga` remains enabled on older HarfBuzz versions.
    if any(r.ScriptTag == "hang" for r in gsub.ScriptList.ScriptRecord):
        raise RuntimeError("Unexpected pre-existing hang GSUB script")

    return {
        "calt_feature_records": len(calt_records),
        "calt_lookup_count": len(lookup_indices),
        "liga_feature_index": insert_at,
    }


def inspect_route(font: TTFont) -> dict[str, object]:
    gsub = font["GSUB"].table
    records = gsub.FeatureList.FeatureRecord
    liga_indices = [i for i, r in enumerate(records) if r.FeatureTag == "liga"]
    dflt = _default_langsys(gsub, "DFLT")
    linked = [i for i in liga_indices if i in (dflt.FeatureIndex or [])]
    lookups: list[int] = []
    for i in linked:
        lookups.extend(records[i].Feature.LookupListIndex or [])
    return {
        "liga_indices": liga_indices,
        "dflt_liga_indices": linked,
        "dflt_liga_lookup_count": len(dict.fromkeys(lookups)),
        "has_hang_script": any(r.ScriptTag == "hang" for r in gsub.ScriptList.ScriptRecord),
    }
