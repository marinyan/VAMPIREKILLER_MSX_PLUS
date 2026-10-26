"""Keep ground-item updates in slot order and compose only their final images."""
from fixes import Explanation, Fix


def emit(c):
    c.label("item_priority_update")
    c.emit("01 00 08", "original eight-record loop initialization")
    c.call(0x8A50)
    c.emit("F5 C5 D5 E5 DD E5 FD E5 0E 00", "preserve the original update result / first display class")
    c.label("item_priority_class")
    c.emit("DD 21 00 C5 06 08", "visit the original eight records without moving them")
    c.label("item_priority_record")
    c.emit("C5 DD 7E 00 E6 7F FE 04", "save loop / only settled, visible bitmap records")
    c.jr("item_priority_skip", "nz")
    c.emit("DD 7E 04 FE 19", "class0: closed chest")
    c.jr("item_priority_chest", "z")
    c.emit("FE 02", "class2: large heart")
    c.jr("item_priority_large", "z")
    c.emit("FE 01", "class3: small heart")
    c.jr("item_priority_small", "z")
    c.emit("3E 01", "class1: other items")
    c.jr("item_priority_test")
    c.label("item_priority_chest")
    c.emit("AF", "ld a,0")
    c.jr("item_priority_test")
    c.label("item_priority_large")
    c.emit("3E 02", "ld a,2")
    c.jr("item_priority_test")
    c.label("item_priority_small")
    c.emit("3E 03", "ld a,3")
    c.label("item_priority_test")
    c.emit("B9", "cp c ; requested display class")
    c.jr("item_priority_skip", "nz")
    c.emit("DD 5E 01 DD 56 02 DD 7E 04 3D", "original y, x and item image index")
    c.call(0x8CC1)
    c.label("item_priority_skip")
    c.emit("C1 11 10 00 DD 19", "restore class/slot counters / next original record")
    c.branch(0x10, "item_priority_record", "djnz", True)
    c.emit("0C 79 FE 04", "next display class")
    c.jr("item_priority_class", "c")
    c.emit("FD E1 DD E1 E1 D1 C1 F1 C9", "restore the original update result / ret")


def apply(edit, hook, c):
    hook(0x4A4D, "01 00 08", "item_priority_update", "Compose ground items after preserving their original slot-order updates", 0xC3)
    edit(0x4B8B, "CD C1 8C", "00 00 00", "Defer the newly landed item's bitmap until the composition pass")
    edit(0x4BB1, "CD C1 8C", "00 00 00", "Defer the settled item's bitmap until the composition pass")


FIX = Fix(
    "item_priority", "重なったアイテムの表示順", "Overlapping ground-item priority",
    "重なった宝箱やアイテムを、種類に応じた一定の順番で描きます。",
    "Give overlapping chests and drops a consistent display order.",
    emit_helpers=emit, apply=apply, extended_helpers=True, behavior_change=True,
    explanation=Explanation(
        symptom_ja="同じ場所へ地上アイテムが重なると、内部の空き枠へ入った順によって宝箱やハートが隠れ、何が残っているか分かりにくくなります。",
        symptom_en="When ground items overlap, allocation order can let a chest or another drop hide a heart, making the remaining items difficult to distinguish.",
        trigger_ja="宝箱・通常アイテム・大小のハートが同じ場所や近い場所へ重なって着地したときです。",
        trigger_en="A chest, ordinary drop, or heart settles over or near another ground item.",
        correction_ja="状態更新と取得判定は従来の8枠順のまま実行し、最後の画像だけを宝箱、その他のアイテム、大ハート、小ハートの順に重ねます。上側を取る・消える場面でも、残っているものを描き直します。枠の入れ替え、寿命や効果の変更は行いません。",
        correction_en="Keep all eight records' updates and pickup checks in their original order, then compose chests, other drops, large hearts, and small hearts in that order. Redraw survivors after removal without rearranging records or changing lifetimes and effects.",
        notes_ja="表示の改善項目です。同じ種類が重なった場合の表示順は、従来の枠順を維持します。",
        notes_en="This is a display improvement. Items within the same class retain their original slot order."))
