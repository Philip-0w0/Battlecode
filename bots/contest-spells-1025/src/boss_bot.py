"""Contest: gold first, then range-four spells against range-three Monoliths."""
import cambc as bc
from cambc import game_map as gm
from economy_bot import Bot as EconomyBot, disk, dist


class BossBot(EconomyBot):
    def setup(self,me):
        super().setup(me)
        self.bosses=[i for i,stats in enumerate(self.group_stats) if stats[2]]
        opaque=gm.walls()|gm.bushes()
        self.firing={}
        for index in self.bosses:
            center=self.centers[index]
            self.firing[index]=(opaque.shadow_cast(center,4)&disk(center,4)&~disk(center,3)&~self.terrain)

    def shop(self,me):
        if me.gold_count()<30: return
        counts=me.item_count()
        for family in ['MONSTER','POWER']:
            shard=getattr(bc.ItemType,family+'_SHARD_OF_FOCUS')
            emblem=getattr(bc.ItemType,family+'_EMBLEM_OF_FOCUS')
            if family=='MONSTER' and counts[emblem]: continue
            count=me.gold_count()//30
            if family=='MONSTER': count=min(count,5-counts[shard])
            if count and me.can_buy(shard,count): me.buy(shard,count)
            else: break

    def choose_group(self,me):
        if me.focus()>=200:
            visible=bc.vision.visible_tiles()
            for i in sorted(self.bosses,key=lambda j:self.path_fields[j].get(me.position())):
                if not (visible&self.masks[i]).is_empty():
                    state=self.groups[i].state()
                    if isinstance(state,gm.CampGroupRespawning):
                        self.sleep_until[i]=bc.round_number()+state.timer+1
                    else: self.sleep_until.pop(i,None)
                if self.sleep_until.get(i,0)<=bc.round_number() and self.path_fields[i].get(me.position())<10000:
                    return i
        return super().choose_group(me)

    def farm(self,me):
        index=self.choose_group(me)
        self.claim(index)
        if index is None: return
        if index not in self.bosses:
            # Original neutral-camp combat, movement and capture logic.
            return super().farm(me)
        group=self.groups[index]
        live=[c for c in group if c.is_visible() and c.health()>0]
        if live:
            goals=self.firing[index]
            if goals.is_set(me.position()):
                self.check_budget()
                self.cast(me,live)
            else:
                self.move(me,goals)
            return
        if not (self.masks[index]&bc.vision.visible_tiles()).is_empty():
            state=group.state()
            if isinstance(state,gm.CampGroupRewardAvailable):
                self.move(me,self.masks[index])
                return
        # Reveal the boss from outside its attack range before selecting spells.
        self.move(me,self.firing[index])
