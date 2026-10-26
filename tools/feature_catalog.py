"""Ordered fix registry and dependency resolution; never enumerate combinations."""
import re

from fixes.fall_attack import FIX as FALL_ATTACK
from fixes.screen_edges import FIX as SCREEN_EDGES
from fixes.shield_fix import FIX as SHIELD_FIX

# Add a fix module above and register it here. Order is stable for ROM layout.
CATALOG = (FALL_ATTACK, SCREEN_EDGES, SHIELD_FIX)


def resolve_selection(feature_ids, catalog=CATALOG):
    """Return a stable dependency-first selection, rejecting invalid choices."""
    registry = {}
    for fix in catalog:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", fix.id) or fix.id in registry:
            raise ValueError(f"Invalid or duplicate fix ID: {fix.id}")
        registry[fix.id] = fix
    for fix in catalog:
        for reference in (*fix.requires, *fix.conflicts):
            if reference not in registry:
                raise ValueError(f"Unknown reference in {fix.id}: {reference}")
    if isinstance(feature_ids, str):
        raise ValueError("Expected a list of fix IDs")
    requested = set(feature_ids)
    unknown = requested - registry.keys()
    if unknown:
        raise ValueError("Unknown fix ID(s): " + ", ".join(sorted(unknown)))
    if not requested:
        raise ValueError("Select at least one fix")
    chosen, visiting = set(), set()

    def include(fix_id):
        if fix_id in visiting:
            raise ValueError(f"Dependency cycle at: {fix_id}")
        if fix_id in chosen:
            return
        visiting.add(fix_id)
        for dependency in registry[fix_id].requires:
            include(dependency)
        visiting.remove(fix_id)
        chosen.add(fix_id)

    for fix in catalog:
        if fix.id in requested:
            include(fix.id)
    for fix_id in sorted(chosen):
        for conflict in registry[fix_id].conflicts:
            if conflict in chosen:
                raise ValueError(f"Conflicting fixes: {fix_id} / {conflict}")
    ordered, visited = [], set()

    def append(fix_id):
        if fix_id in visited:
            return
        for dependency in registry[fix_id].requires:
            append(dependency)
        visited.add(fix_id)
        ordered.append(registry[fix_id])

    for fix in catalog:
        if fix.id in chosen:
            append(fix.id)
    return tuple(ordered)


def legacy_selection(fall, edges, shield=False):
    """Keep old named releases and diagnostics independent of future fixes."""
    return [name for name, enabled in (("fall_attack", fall), ("screen_edges", edges),
                                      ("shield_fix", shield)) if enabled]
