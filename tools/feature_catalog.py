"""Ordered fix registry and dependency resolution; never enumerate combinations."""
import re

from fixes.fall_attack import FIX as FALL_ATTACK
from fixes.screen_edges import FIX as SCREEN_EDGES
from fixes.shield_fix import FIX as SHIELD_FIX
from fixes.stairs import FIX as STAIRS
from fixes.trap_contact import FIX as TRAP_CONTACT
from fixes.trap_attack import FIX as TRAP_ATTACK
from fixes.patrol_timer import FIX as PATROL_TIMER
from fixes.mummy_start import FIX as MUMMY_START
from fixes.reform_hp import FIX as REFORM_HP
from fixes.stun_hp import FIX as STUN_HP
from fixes.hourglass import FIX as HOURGLASS
from fixes.actor_alloc import FIX as ACTOR_ALLOC
from fixes.projectile_alloc import FIX as PROJECTILE_ALLOC
from fixes.empty_projectile import FIX as EMPTY_PROJECTILE
from fixes.projectile_box import FIX as PROJECTILE_BOX
from fixes.crouch_fall import FIX as CROUCH_FALL
from fixes.platform_land import FIX as PLATFORM_LAND
from fixes.platform_turn import FIX as PLATFORM_TURN
from fixes.shop_input import FIX as SHOP_INPUT
from fixes.boss_spawn import FIX as BOSS_SPAWN
from fixes.weapon_owner import FIX as WEAPON_OWNER
from fixes.axe_wall import FIX as AXE_WALL
from fixes.hurt_clip import FIX as HURT_CLIP
from fixes.water_edge import FIX as WATER_EDGE
from fixes.bat_y import FIX as BAT_Y
from fixes.jumper_land import FIX as JUMPER_LAND
from fixes.water_pending import FIX as WATER_PENDING
from fixes.actor_order import FIX as ACTOR_ORDER
from fixes.phantom_gate import FIX as PHANTOM_GATE
from fixes.pause_visibility import FIX as PAUSE_VISIBILITY
from fixes.item_priority import FIX as ITEM_PRIORITY
from fixes.weapon_graphics import FIX as WEAPON_GRAPHICS

# Add a fix module above and register it here. Order is stable for ROM layout.
ADDITIONAL_FIXES = (STAIRS, TRAP_CONTACT, TRAP_ATTACK, PATROL_TIMER, MUMMY_START, REFORM_HP, STUN_HP, HOURGLASS,
                    ACTOR_ALLOC, PROJECTILE_ALLOC, EMPTY_PROJECTILE, PROJECTILE_BOX, CROUCH_FALL, PLATFORM_LAND,
                    PLATFORM_TURN, SHOP_INPUT, BOSS_SPAWN, WEAPON_OWNER, AXE_WALL, HURT_CLIP,
                    WATER_EDGE, BAT_Y, JUMPER_LAND, WATER_PENDING, ACTOR_ORDER, PHANTOM_GATE,
                    PAUSE_VISIBILITY, ITEM_PRIORITY, WEAPON_GRAPHICS)
CATALOG = (FALL_ATTACK, SCREEN_EDGES, SHIELD_FIX, *ADDITIONAL_FIXES)


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
