"""Emblem passives apply to every stat variant of their item family."""
import cambc as bc


def has_jungle(counts):
    return any(counts[getattr(bc.ItemType, 'JUNGLE_EMBLEM_OF_' + stat)]
               for stat in ('STRENGTH', 'FOCUS', 'HEALTH'))
