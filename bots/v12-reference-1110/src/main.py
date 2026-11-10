"""Dispatch turns and preserve useful error locations in replay logs."""
import traceback
import sys
import cambc
import draft
from bot import Bot, TurnBudget
from economy_bot import Bot as EconomyBot, TurnBudget as EconomyTurnBudget
from rows_bot import Bot as RowsBot, TurnBudget as RowsTurnBudget
import rows_draft
from reliability import Reliable
from current_content import CurrentContent
from safety import Safety
from protection import Protection


class TacticalBot(Protection, Safety, CurrentContent, Reliable, Bot): pass
class SafeEconomyBot(Protection, Safety, CurrentContent, Reliable, EconomyBot): pass


class SupportedRowsBot(RowsBot):
    """Use the shared Heart build/casts without changing Rows routing/retreat."""
    def shop(self, me):
        if self.kind == cambc.ChampionType.HEART_OF_RUIN:
            return CurrentContent.shop(self, me)
        return super().shop(me)

    def cast(self, me, targets, moved=False, attacked=False):
        if self.kind == cambc.ChampionType.HEART_OF_RUIN:
            return CurrentContent.cast(self, me, targets, moved, attacked)
        return super().cast(me, targets, moved, attacked)
class SafeRowsBot(Protection, Safety, SupportedRowsBot): pass
from cambc import game_map as gm


DEBUG = False


def local_shop_rule(signature):
    if signature in {
        (80, 80, frozenset({(14, 4), (65, 75), (38, 34), (13, 26), (67, 32), (41, 45), (12, 47), (40, 63), (39, 16), (66, 53)})),
        (30, 30, frozenset({(3, 26), (26, 3)})),
        (40, 40, frozenset({(19, 17), (20, 22)})),
    }:
        return "legacy"
    return "general"

def eight_legacy_bot():
    from legacy_tactical import Bot as LegacyTactical
    class EightLegacyBot(Protection, Safety, CurrentContent, Reliable, LegacyTactical):
        pass
    return EightLegacyBot()


def main():
    # Rows uses the validated assignment-only experiment and its original draft.
    # Packs/Eight retain the tactical policy; other maps retain economy policy.
    signature=(gm.width(),gm.height(),frozenset((p.x,p.y) for p in gm.altars().positions()))
    tactical_maps={
        (31,31,frozenset({(2,6),(28,6),(2,15),(28,15),(2,24),(28,24)})),
        (41,30,frozenset({(20,15)})),
    }
    is_rows=signature==(50,50,frozenset({(15,16),(34,33)}))
    mode=None
    if signature[:2] in {(30, 30), (45, 45), (100, 80), (67, 73), (50, 40), (51, 51), (40, 40)}:
        from map_dispatch import choose_mode
        mode=choose_mode(signature)
    if mode is not None:
        from specific_maps import PreviousEconomy,PreviousTactical,TerritoryEconomy,FragmentEconomy,GiftEconomy,CooperativeEconomy
        parent={'PreviousEconomy':PreviousEconomy,'PreviousTactical':PreviousTactical,'TerritoryEconomy':TerritoryEconomy,'FragmentEconomy':FragmentEconomy,'GiftEconomy':GiftEconomy,'CooperativeEconomy':CooperativeEconomy}[mode]
        # One startup binding; keep the original hot-path MRO unchanged.
        # Every champion has its own interpreter, so this is map-local state.
        controller=Bot if mode=='PreviousTactical' else EconomyBot
        providers=(PreviousTactical,) if controller is Bot else (PreviousEconomy,parent)
        for provider in providers:
            for name in ('attack','combat','setup_steps','choose_group','play_turn'):
                method=provider.__dict__.get(name)
                if method is not None:setattr(controller,name,method)
        bot=TacticalBot() if controller is Bot else SafeEconomyBot()
    else:
        if signature == (41,30,frozenset({(20,15)})):
            bot = eight_legacy_bot()
        else:
            bot = SafeRowsBot() if is_rows else (TacticalBot() if signature in tactical_maps else SafeEconomyBot())
    if signature[:2] in {(61,71),(50,40)} and signature in {
        (61,71,frozenset({(26,35),(30,35),(34,35)})),
        (50,40,frozenset({(17,19),(17,20),(32,19),(32,20)})),
    }:
        from map_fuel import cast
        EconomyBot.cast=cast
    if not is_rows and signature not in tactical_maps:
        rule = local_shop_rule(signature)
        if rule != "general":
            from local_shop_recipes import legacy_shop
            def specific_shop(me):
                if bot.kind == cambc.ChampionType.HEART_OF_RUIN:
                    return CurrentContent.shop(bot, me)
                return legacy_shop(bot, me)
            bot.shop = specific_shop

    # SDK preloads ordinary modules; create this policy only in the entry point.
    if signature[:2] in {(50, 65), (100, 100), (45, 35), (80, 64), (79, 79), (45, 30)} and (signature[0], signature[1], len(gm.camp_groups()), tuple(sorted(signature[2]))) in {(79, 79, 11, ((39, 35), (39, 43))), (45, 35, 32, ((18, 2), (22, 32), (26, 2))), (100, 100, 24, ((17, 50), (31, 42), (43, 20), (56, 79), (68, 57), (82, 49))), (50, 65, 23, ((5, 58), (14, 3), (35, 3), (44, 58))), (45, 30, 22, ((21, 19), (23, 10))), (80, 64, 26, ((36, 26), (43, 37)))}:
        def _six_map_varg_choose(self, me, _original=EconomyBot.choose_group):
            if self.kind != C.VARG: return _original(self,me)
            visible = bc.vision.visible_tiles()
            # Reuse a live assignment between staggered planning turns. Risk and
            # retreat are still evaluated every turn by the shared safety layer.
            if (self.target is not None and bc.round_number()%8 != self.slot%8
                    and self.failed_until.get(self.target,0)<=bc.round_number()):
                if (self.masks[self.target]&visible).is_empty():return self.target
                state=self.groups[self.target].state()
                if not isinstance(state,gm.CampGroupRespawning):return self.target
                self.sleep_until[self.target]=bc.round_number()+state.timer+1
            claims = read_claims()
            jungle = has_jungle(me.item_count())
            candidates = []
            # Bound live queries after ranking cached terrain-aware travel costs.
            shortlist = nearest_groups(self.path_fields, me.position(), self.target, self.check_budget)
            if not hasattr(self,'_willow_planning_team'):
                self._willow_planning_team=(not self.collision and any(
                    ally.champion_name()==C.WILLOW for ally in self.allies_by_slot))
            planning_reserve=getattr(self,"safety_select_reserve",900000)
            if self._willow_planning_team:planning_reserve+=200000
            for index in shortlist:
                if bc.fuel_remaining() < planning_reserve and candidates: break
                self.check_budget()
                group = self.groups[index]
                if self.failed_until.get(index, 0) > bc.round_number():
                    continue
                state = None
                if not (self.masks[index] & visible).is_empty():
                    state = group.state()
                    if isinstance(state, gm.CampGroupRespawning):
                        self.sleep_until[index] = bc.round_number() + state.timer + 1
                    else:
                        self.sleep_until.pop(index, None)
                if self.sleep_until.get(index, 0) > bc.round_number():
                    continue
                position = self.centers[index]
                travel = self.path_fields[index].get(me.position())
                if travel > 10000: continue
                hp, incoming, boss = self.group_stats[index]
                if index == self.target and len(group) <= 4:
                    hp = sum(c.health() if c.is_visible() else c.base_stats().base_health for c in group)
                # Do not open a boss while weak. Other camps give much safer growth.
                if boss and me.strength() < 200:
                    continue
                ready = isinstance(state, gm.CampGroupRewardAvailable)
                if hasattr(self,"safe_camp") and not self.safe_camp(me,index,ready,hp,incoming): continue
                damage = max(1, me.strength() * (1.6 if self.kind == C.VARG and len(group) > 1 else 1.15))
                clear = 0 if ready else hp / damage
                rank_clear=clear
                if not ready and index!=self.target and damage>1 and 1<len(group)<=4:
                    factors=getattr(self,'_varg_rank_factors',None)
                    if factors is None:
                        factors={}
                        self._varg_rank_factors=factors
                    factor=factors.get(index)
                    if factor is None:
                        factor=1.6
                        if not boss and not any(c.is_golem() for c in group):
                            positions=[c.spawn_position() for c in group]
                            if any(all(dist(p,q)<=1 for q in positions) for p in positions):
                                healths=[c.base_stats().base_health for c in group]
                                factor=max(1.6,min(2.5,sum(healths)/max(healths)))
                        factors[index]=factor
                    if factor>1.6:rank_clear=clear*1.6/factor
                value = (group.gem_value() + .18 * group.gold_value()) / (travel + rank_clear + 7)
                if jungle: incoming *= .7
                # Conservative long-clear estimate; later monsters die before the last.
                reserve = incoming * clear * .55
                if not ready and reserve > me.health() * .75: value *= .15
                if boss: value *= .15
                if self.alert and dist(position, self.alert) <= 6: value *= .45
                if ready:
                    value *= 2
                    if index == self.target and self.masks[index].is_set(me.position()): value *= 20
                if index == self.target:
                    value *= 1.35
                if self.kind == C.CASSI and incoming == 0: value *= 1.5
                if any(slot != self.slot and v == index + 1 and self.allies_by_slot[slot].is_alive()
                       for slot, v in enumerate(claims) if slot < len(self.allies_by_slot)):
                    value *= .25
                candidates.append((value, index))
            return max(candidates)[1] if candidates else None
        from types import FunctionType
        EconomyBot.choose_group=FunctionType(_six_map_varg_choose.__code__,EconomyBot.choose_group.__globals__,"choose_group",_six_map_varg_choose.__defaults__)

    # Crater support is compiled only in its gameplay interpreter.
    if signature == (61, 61, frozenset({(30, 3)})) and not cambc.is_draft() and len(gm.camp_groups()) == 6:
        exec("def _crater_partner_support(self,me,_original=Bot.support):\n    if self.kind!=C.WILLOW:return _original(self,me)\n    if _original(self,me):return True\n    if me.health()<me.max_health()*.4:return False\n    anchor=None\n    for ally in self.allies_by_slot:\n        self.check_budget()\n        if (ally.champion_name()==C.VARG and ally.is_alive() and ally.is_visible()\n                and dist(me.position(),ally.position())<=6\n                and not self.spawn.is_set(ally.position()) and not ally.is_recalling()\n                and not ally.is_submitting_gems() and not ally.is_teleporting()):\n            anchor=ally\n            break\n    if anchor is None:return False\n    if not self.safety_active and anchor.health()>=.85*anchor.max_health():\n        self.check_budget()\n        visible_enemy=any(e.is_alive() and e.is_visible() for e in bc.champions(bc.Team.ENEMY))\n        if not visible_enemy:\n            awake_now=bc.vision.awake_camp_tiles()\n            nearby_camp=False\n            for camp in self.visible_camps():\n                self.check_budget()\n                point=camp.position() if camp.is_golem() else camp.spawn_position()\n                if (camp.strength()>0 and awake_now.is_set(point)\n                        and dist(anchor.position(),point)<=camp.attack_range()+1):\n                    nearby_camp=True\n                    break\n            if not nearby_camp:return False\n    self.claim(None)\n    if not hasattr(self,'_crater_heal_ability'):\n        self._crater_heal_ability=next((a for a in me.abilities() if a.is_heal() and a.can_target_allies()),None)\n    heal=self._crater_heal_ability\n    self.check_budget()\n    if (heal is not None and me.can_cast() and heal.is_ready() and anchor.is_visible()\n            and dist(me.position(),anchor.position())<=heal.info().range\n            and heal.heal_amount(anchor)>50):\n        self.check_budget()\n        heal.use(anchor)\n    if dist(me.position(),anchor.position())>2:\n        self.move(me,disk(anchor.position(),2))\n    self.check_budget()\n    awake=bc.vision.awake_camp_tiles()\n    targets=self.enemies()+[c for c in self.visible_camps()\n        if awake.is_set(c.position() if c.is_golem() else c.spawn_position())]\n    self.attack(me,targets)\n    return True", EconomyBot.support.__globals__)
        EconomyBot.support=EconomyBot.support.__globals__.pop("_crater_partner_support")

    # Vault: add identical camp attack discs directly into one goal mask.
    if signature==(31,31,frozenset({(5,25),(25,5)})) and not cambc.is_draft() and len(gm.camp_groups())==7:
        exec('def _vault_draw_farm(self, me):\n    index = self.choose_group(me)\n    self.claim(index)\n    if index is None:\n        return\n    group = self.groups[index]\n    camps = [c for c in group if c.is_visible() and c.health() > 0]\n    enemies = self.enemies()\n    if camps:\n        self.combat(me, enemies + camps)\n        if not me.is_alive() or not me.can_move():\n            return\n        camps = [c for c in group if c.is_visible() and c.health() > 0]\n    goals = bc.Bitboard()\n    if camps:\n        attack_radius = me.attack_range()\n        for camp in camps:\n            if camp.is_golem():\n                self.check_budget()\n                if not camp.is_visible():\n                    continue\n                position = camp.position()\n            else:\n                position = camp.spawn_position()\n            goals.draw_chebyshev(position, attack_radius)\n    else:\n        goals |= self.masks[index]\n    self.check_budget()\n    before = me.position()\n    if not self.move(me, goals):\n        self.failed_until[index] = bc.round_number() + 8\n        self.claim(None)\n        return\n    if me.position() != before:\n        self.combat(me, [c for c in group if c.is_visible() and c.health() > 0], moved=True)\n',EconomyBot.farm.__globals__)
        EconomyBot.farm=EconomyBot.farm.__globals__.pop("_vault_draw_farm")

    draft_policy=rows_draft if is_rows else draft
    while True:
        try:
            if cambc.is_draft():
                draft_policy.play()
            else:
                bot.action_round = cambc.round_number()
                bot.play_turn()
        except (TurnBudget,EconomyTurnBudget,RowsTurnBudget):
            pass  # Expected bounded yield; do not spend fuel on release logging.
        except Exception as error:
            tb=error.__traceback__
            while tb is not None and tb.tb_next is not None: tb=tb.tb_next
            where=f" [{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}]" if tb is not None else ""
            print(f"bot error: {error}{where}", flush=True)
            if DEBUG: traceback.print_exc(file=sys.stdout)
        cambc.end_turn()


if __name__ == '__main__':
    main()
