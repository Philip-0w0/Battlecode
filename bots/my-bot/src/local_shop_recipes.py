import cambc as bc
C,I=bc.ChampionType,bc.ItemType

def legacy_shop(self, me):
        if me.gold_count() < 30:
            return
        # Complete each family before moving on. No repeated nonstacking passive.
        focus = self.kind in (C.STELLAR, C.CASSI, C.PRISM, C.WILLOW)
        stat = "FOCUS" if focus else "STRENGTH"
        build = [("JUNGLE", stat), ("MONSTER", stat),
                 ("BRUISER", "HEALTH"), ("POWER", stat)]
        # A delivery crystal is a planned purchase, not a universal tax on income.
        crystal = bc.ConsumableType.TP_CRYSTAL
        if self.collision and self.kind in (C.VARG, C.TAVI) and me.gold_count() >= 160 and me.can_buy(crystal):
            me.buy(crystal)
        lock = bc.ConsumableType.ALTAR_LOCK
        if me.gold_count() >= 310 and me.can_buy(lock):
            me.buy(lock)
        counts = me.item_count()
        for family, s in build:
            shard = getattr(I, family + "_SHARD_OF_" + s)
            emblem = getattr(I, family + "_EMBLEM_OF_" + s)
            if counts[emblem] and family != "POWER":
                continue
            count = me.gold_count() // 30
            if family != "POWER":
                count = min(count, 5 - counts[shard])
            if count > 0 and me.can_buy(shard, count):
                me.buy(shard, count)
            else:
                break
