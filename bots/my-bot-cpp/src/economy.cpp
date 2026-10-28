#include "controller.h"
int Bot::choose_group(Champion me){
    auto visible=bc::vision::visible_tiles();bool advanced=tactical()&&!corners;
    if(tactical()&&target>=0&&bc::round_number()%4!=slot%4&&!stats[target].boss&&failed_until[target]<=bc::round_number()){
        if((masks[target]&visible).is_empty())return target;
        auto state=groups[target].state();if(!std::holds_alternative<bc::map::camp_group_respawning>(state))return target;
        sleep_until[target]=bc::round_number()+std::get<bc::map::camp_group_respawning>(state).timer+1;
    }
    auto claims=memory().claims(specialist());auto counts=me.item_count();bool jungle=strategy::has_jungle(counts[I::jungle_emblem_of_strength],counts[I::jungle_emblem_of_focus],counts[I::jungle_emblem_of_health]);
    // No action occurs during camp scoring. Observe our origin once.
    const auto origin=me.position();
    std::vector<int> shortlist(groups.size());std::iota(shortlist.begin(),shortlist.end(),0);
    strategy::stable_sort_by_key(shortlist,[&](int index){return dist(origin,centers[index]);});if(shortlist.size()>10)shortlist.resize(10);
    if(target>=0&&std::find(shortlist.begin(),shortlist.end(),target)==shortlist.end())shortlist.push_back(target);
    std::optional<std::pair<double,int>> best;
    double strength=me.strength(),health=me.health();
    for(int index:shortlist){
        if(bc::fuel_remaining()<strategy::native_fuel(advanced?1100000:900000)&&best)break;check_budget();auto& group=groups[index];bool borrowed=false;
        if(specialist()){
            auto owner=rows_owners.find(index);
            if(owner!=rows_owners.end()&&owner->second!=slot&&allies_by_slot[owner->second].is_alive()){
                if(bc::round_number()<40||claims[owner->second]!=0){
                    if(target!=index||!masks[index].is_set(me.position()))continue;
                    if(!std::holds_alternative<bc::map::camp_group_reward_available>(group.state()))continue;
                }borrowed=true;
            }
            bool claimed=false;if(!rows_home.empty())for(std::size_t s=0;s<allies_by_slot.size()&&s<6;++s)if(int(s)!=slot&&claims[s]==index+1&&allies_by_slot[s].is_alive())claimed=true;
            if(claimed)continue;
        }
        if(failed_until[index]>bc::round_number())continue;
        std::optional<bc::map::camp_group_state> state;
        if(!(masks[index]&visible).is_empty()){
            state=group.state();if(auto respawn=std::get_if<bc::map::camp_group_respawning>(&*state))sleep_until[index]=bc::round_number()+respawn->timer+1;else sleep_until.erase(index);
        }
        if(sleep_until[index]>bc::round_number())continue;
        auto position=centers[index];double travel=path_fields[index].get(origin);if(travel>10000)continue;
        auto [hp,incoming,boss]=stats[index];if(index==target&&group.camps().size()<=4)hp=sum(group.camps(),[](auto c){return c.is_visible()?c.health():c.base_stats().base_health;});
        bool reward=state&&std::holds_alternative<bc::map::camp_group_reward_available>(*state);
        std::vector<Champion> partners;
        if(advanced){
            if(boss&&!reward)partners=filtered(allies(),[&](auto a){return id(a)!=id(me)&&a.health()>=.65*a.max_health()&&dist(a.position(),position)<=7;});
            if(boss&&!reward&&rows){if(kind!=C::vendetta&&kind!=C::tavi)continue;partners=filtered(partners,[](auto a){return a.champion_name()==C::vendetta||a.champion_name()==C::tavi;});}
            if(boss&&!reward&&(partners.empty()||health<.65*me.max_health()))continue;
        }else if(strategy::boss_gate(boss,reward,strength))continue;
        double damage=std::max(1.,strength*(kind==C::varg&&group.camps().size()>1?1.6:1.15));
        double clear=reward?0:hp/damage;
        if(advanced&&boss&&!reward){damage+=sum(partners,[](auto a){return a.strength()*1.3;});clear=hp/damage;if(incoming*clear*.55>health+sum(partners,[](auto a){return a.health();}))continue;}
        double value=(advanced?group_rewards[index]:group.gem_value()+.18*group.gold_value())/(travel+clear+7);
        if(advanced){
            value*=home_groups[index]?1.35:.65;
            if(bc::round_number()<90&&crates[index])value*=1.8;
            if(altar_groups[index])value*=1.15;
            if(rows){if(kind==C::varg||kind==C::ryth||kind==C::willow){if(incoming&&home_groups[index])value*=2;else if(crates[index])value*=.65;}else if((kind==C::vendetta||kind==C::tavi)&&crates[index])value*=2;}
        }
        if(specialist()){if(borrowed)value*=.6;if(!rows_home.empty()&&!rows_home.contains(index))value*=.25;}
        if(jungle)incoming*=.7;if(!reward&&incoming*clear*.55>health*.75)value*=.15;
        value*=strategy::boss_discount(boss,reward);
        if(alert&&dist(position,*alert)<=6)value*=.45;
        if(reward){value*=2;if(index==target&&masks[index].is_set(me.position()))value*=20;}
        if(index==target)value*=advanced?1.8:1.35;
        if(kind==C::cassi&&incoming==0)value*=1.5;
        bool claimed=false;for(std::size_t s=0;s<allies_by_slot.size()&&s<6;++s)if(int(s)!=slot&&claims[s]==index+1&&allies_by_slot[s].is_alive())claimed=true;
        if(claimed)value*=advanced&&boss?.8:.25;
        if(!best||std::pair(value,index)>*best)best={{value,index}};
    }return best?best->second:-1;
}
void Bot::farm(Champion me){
    if(!specialist()){
        check_budget();std::optional<double> hp;
        if(target>=0)hp=sum(groups[target].camps(),[](auto c){return c.is_visible()?c.health():c.base_stats().base_health;});
        auto p=me.position();progress.observe(bc::round_number(),target,{p.x,p.y},target>=0?path_fields[target].get(p):0,{int(me.gold_count()),int(me.gem_count()),int(bc::global_submitted_gems(T::ally)),hp});
        if(progress.idle>=60){if(target>=0)failed_until[target]=bc::round_number()+30;claim(-1);progress.reset();if(me.gem_count()){bank(me);return;}}
    }
    int index=choose_group(me);claim(index);if(index<0)return;auto& group=groups[index];
    if(tactical()){
        auto p=me.position();if(last_position&&*last_position==p&&last_target==index)++stalled;else stalled=0;last_position=p;last_target=index;
        if(stalled>=8&&!masks[index].is_set(p)){failed_until[index]=bc::round_number()+12;claim(-1);stalled=0;return;}
    }
    auto remaining=[&](){std::vector<Unit> out;for(auto c:group)if(c.is_visible()&&c.health()>0)out.emplace_back(c);return out;};
    auto camps=remaining();auto es=enemies();
    if(!camps.empty()){
        std::vector<Unit> all;for(auto e:es)all.emplace_back(e);all.insert(all.end(),camps.begin(),camps.end());combat(me,all);
        if(!me.is_alive()||!me.can_move())return;camps=remaining();
    }
    Board goals;if(!camps.empty())for(auto c:camps)goals|=disk(c.position(),me.attack_range());else goals|=masks[index];
    auto before=me.position();if(!move(me,goals)){failed_until[index]=bc::round_number()+8;claim(-1);return;}
    if(me.position()!=before){auto ts=remaining();if(tactical()){std::vector<Unit> all;for(auto e:enemies())all.emplace_back(e);all.insert(all.end(),ts.begin(),ts.end());ts=std::move(all);}combat(me,ts,true);}
}
bool Bot::crystal_delivery(Champion me){
    auto p=me.position();int y=home_bottom?p.y:40-p.y;
    if(y>=8&&y<=32&&p.x>=37){return_from_inner=true;return false;}
    auto crystal=me.consumables()[bc::consumable_type::tp_crystal];if(!crystal.count()||p.x<29||y>7||me.gem_count()<36)return false;
    V takeoff{36,home_bottom?5:35},landing{33,home_bottom?8:32};if(alert&&dist(*alert,landing)<7)return false;
    if(p!=takeoff)return move(me,disk(takeoff,0));if(blockers(me).is_set(landing)||pressure(p)*3+60>=me.health())return false;
    check_budget();if(crystal.use(landing)){return_from_inner=true;return true;}return false;
}
bool Bot::bank(Champion me){
    if(tactical()&&engage(me,true))return true;if(collision&&crystal_delivery(me))return true;
    std::vector<V> choices=altars;
    if(tactical()){
        auto es=enemies();std::optional<std::pair<double,int>> best;
        for(std::size_t i=0;i<altars.size();++i){double distance=altar_fields[i].get(me.position());if(distance>10000)continue;double risk=0;for(auto e:es)if(dist(e.position(),altars[i])<=6)risk+=30;if(alert&&dist(*alert,altars[i])<=5)risk+=15;
            auto score=std::pair(distance+risk+.12*altar_home[i]-(int(i)==bank_target?3:0),int(i));if(!best||score<*best)best=score;}
        if(!best)return false;bank_target=best->second;auto altar=altars[bank_target];choices={altar};
        std::vector<Unit> guards;for(auto c:visible_camps())if(c.strength()>0&&c.health()<c.max_health()&&dist(c.position(),altar)<=c.attack_range()+1)guards.emplace_back(c);
        if(!guards.empty()&&es.empty()&&dist(me.position(),altar)<=5){double damage=sum(guards,[](auto c){return c.strength();}),rounds=sum(guards,[](auto c){return c.health();})/std::max(me.strength()*1.5,1.);
            if(rounds<=8&&damage*rounds<me.health()*.45){combat(me,guards);if(me.is_alive()){Board goals;for(auto c:guards)if(c.visible()&&c.health()>0)goals|=disk(c.position(),me.attack_range());if(!goals.is_empty())move(me,goals);}return true;}}
    }else {const auto origin=me.position();strategy::stable_sort_by_key(choices,[&](auto altar){return dist(origin,altar);});}
    for(auto altar:choices)if(dist(me.position(),altar)<=bc::constants::submit_gems_range){
        auto locks=bc::vision::altar_lock_tiles(T::enemy);
        if(locks.is_set(altar)){check_budget();if(me.can_attack()&&attack_mask(me).is_set(altar)){
                auto all=bc::vision::altar_locks(T::enemy);auto lock=std::find_if(all.begin(),all.end(),[&](auto l){return l.position()==altar;});check_budget();if(lock!=all.end())me.attack(*lock);}
            return true;}
        auto lock=me.consumables()[bc::consumable_type::altar_lock];if(lock.count()&&!enemies().empty()&&!bc::vision::altar_lock_tiles().is_set(altar))lock.use(altar);
        check_budget();me.submit_gems(altar);return true;
    }
    Board goals;for(auto altar:choices)goals|=disk(altar,bc::constants::submit_gems_range);return move(me,goals);
}
bool Bot::finish_camp(Champion me){
    if(target<0||!enemies().empty())return false;auto& group=groups[target];if((masks[target]&bc::vision::visible_tiles()).is_empty())return false;
    if(std::holds_alternative<bc::map::camp_group_reward_available>(group.state()))return masks[target].is_set(me.position());
    std::vector<bc::camp> remaining;bool all_visible=true;for(auto c:group){all_visible&=c.is_visible();if(c.is_visible()&&c.health()>0)remaining.push_back(c);}
    return !remaining.empty()&&all_visible&&sum(remaining,[](auto c){return c.health();})<=me.strength()*3&&me.health()>4*sum(remaining,[](auto c){return c.strength();})+100;
}
void Bot::play_turn(){
    action_round=bc::round_number();auto me=bc::self();if(!specialist()&&ready&&!me.is_alive()){progress.reset();route_progress.reset();}
    if(!ready)setup(me);action_round=bc::round_number();++turns;shop(me);
    if(tactical()&&(memory().banking()||bc::global_submitted_gems(T::ally)>=800||(me.is_alive()&&bc::global_submitted_gems(T::ally)+me.gem_count()>=900))){auto m=memory();m.publish(slot,me.is_alive()?me.gem_count():0);write_memory(m,0,8);}
    if(!me.is_alive()){if(!specialist())previous_health.reset();claim(-1);recovering=true;return;}
    bool burst=false;if(!specialist()){burst=strategy::lethal_recent_loss(previous_health,previous_round,me.health(),bc::round_number());previous_health=me.health();previous_round=bc::round_number();}
    if(me.is_recalling()||me.is_submitting_gems()||me.is_teleporting())return;
    if(!me.can_move()&&!me.can_attack()&&!me.can_cast())return;
    if(spawn.is_set(me.position())){if(me.health()<me.max_health())return;recovering=false;}
    auto es=enemies();threats.clear();for(auto c:visible_camps())if(c.base_stats().base_strength>0)threats.push_back({c.spawn_position(),c.base_stats().base_strength,c.attack_range()});
    for(auto e:es)threats.push_back({e.position(),e.strength()+.3*e.focus(),4});communicate(me);double risk=pressure(me.position());
    if(burst||me.health()<std::max(me.max_health()*.14,risk*2.5+30))recovering=true;
    if(return_from_inner&&!spawn.is_set(me.position())&&!me.gem_count())recovering=true;if(spawn.is_set(me.position()))return_from_inner=false;
    if(recovering){if(tactical()&&(!es.empty()||risk))report(me.position(),true);claim(-1);if(me.can_cast())cast(me,targets());retreat(me);return;}
    if(turns%8==slot&&me.ward_cooldown()==0){auto placements=me.ward_placement_tiles()&~blockers(me)&~bc::vision::ward_tiles(T::ally)&bc::vision::visible_tiles();if(!placements.is_empty()){
            auto toward=target>=0?centers[target]:altars.front();check_budget();me.place_ward(best_min(placements.positions(),[&](auto p){return dist(p,toward);}));}}
    int gems=me.gem_count(),near=dist(me.position(),best_min(altars,[&](auto p){return dist(me.position(),p);}));int needed=bc::constants::winning_gems-bc::global_submitted_gems(T::ally);bool team_finish=false;
    if(tactical()&&gems){auto carried=memory().gems();for(std::size_t s=0;s<allies_by_slot.size()&&s<6;++s){auto a=allies_by_slot[s];if(!a.is_alive())carried[s]=0;else if(a.is_visible())carried[s]=a.gem_count();}team_finish=strategy::winning_load(bc::global_submitted_gems(T::ally),carried,bc::constants::winning_gems);}
    if(gems&&(team_finish||gems>=40||near<=4||gems>=needed||bc::round_number()>1900)&&(!tactical()||team_finish||!finish_camp(me))){claim(-1);bank(me);return;}
    if(tactical()&&engage(me))return;
    if(kind!=C::tavi&&me.gold_count()>=150&&!gems){claim(-1);recovering=true;retreat(me);return;}
    if(support(me))return;farm(me);
}
