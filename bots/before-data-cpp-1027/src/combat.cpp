#include "controller.h"
void Bot::shop(Champion me){
    if(!heart()&&me.gold_count()<30)return;
    bool focus=heart()||kind==C::stellar||kind==C::cassi||kind==C::prism||kind==C::willow;
    if(!heart()){
        auto crystal=bc::consumable_type::tp_crystal,lock=bc::consumable_type::altar_lock;
        if(collision&&(kind==C::varg||kind==C::tavi)&&me.gold_count()>=160&&me.can_buy(crystal))me.buy(crystal);
        if(me.gold_count()>=310&&me.can_buy(lock))me.buy(lock);
    }
    auto counts=me.item_count();
    std::array<I,4> shards=focus?std::array<I,4>{I::jungle_shard_of_focus,I::monster_shard_of_focus,I::bruiser_shard_of_health,I::power_shard_of_focus}:
        std::array<I,4>{I::jungle_shard_of_strength,I::monster_shard_of_strength,I::bruiser_shard_of_health,I::power_shard_of_strength};
    std::array<I,4> emblems=focus?std::array<I,4>{I::jungle_emblem_of_focus,I::monster_emblem_of_focus,I::bruiser_emblem_of_health,I::power_emblem_of_focus}:
        std::array<I,4>{I::jungle_emblem_of_strength,I::monster_emblem_of_strength,I::bruiser_emblem_of_health,I::power_emblem_of_strength};
    for(int i=0;i<4;++i){if(i!=3&&counts[emblems[i]])continue;int count=me.gold_count()/30;if(i!=3)count=std::min(count,5-int(counts[shards[i]]));if(count>0&&me.can_buy(shards[i],count))me.buy(shards[i],count);else break;}
}
bool Bot::boss_allowed(Champion me,const Unit& t){
    auto c=t.camp();if(!c||!boss_camps.contains(id(*c)))return true;
    if(target<0||!stats[target].boss)return false;
    auto friends=filtered(allies(),[&](auto a){return a.health()>=.65*a.max_health()&&dist(a.position(),c->spawn_position())<=7;});
    if(friends.size()<2)return false;
    if(rows){bool tavi=false,vendetta=false;for(auto a:friends){tavi|=a.champion_name()==C::tavi;vendetta|=a.champion_name()==C::vendetta;}return tavi&&vendetta;}return true;
}
bool Bot::attack(Champion me,const std::vector<Unit>& ts){
    if(!me.can_attack())return false;auto mask=attack_mask(me);
    auto valid=filtered(ts,[&](const Unit& x){return x.visible()&&x.health()>0&&mask.is_set(x.position())&&(!tactical()||!rows||boss_allowed(me,x));});
    if(valid.empty())return false;
    auto value=[&](const Unit& x){
        check_budget();double score=x.health()<=me.strength()?1000:0;
        if(auto c=x.champion()){
            bool contested=false;if(tactical())for(std::size_t i=0;i<crates.size();++i)if(crates[i]&&dist(c->position(),centers[i])<=3)contested=true;
            score+=(contested?1200:150)+std::min(int(c->gem_count()),100);
            if(c->is_submitting_gems())score+=200;if(c->champion_name()==C::willow||c->champion_name()==C::cassi)score+=60;
        }
        if(kind==C::varg)for(auto& y:valid)if(dist(x.position(),y.position())<=1)score+=60;
        return score-x.health()/40.;
    };
    // Python max keeps the first target on equal values.
    auto chosen=best_max(valid,value);
    if(auto c=chosen.champion())if(c->champion_name()==C::ren&&me.health()<=.2*c->focus()+20)return false;
    check_budget();chosen.attack(me);if(!me.is_alive()){if(!tactical())previous_health.reset();return false;}
    return chosen.visible()&&chosen.health()>0;
}
bool Bot::cast(Champion me,std::vector<Unit> ts,bool moved,bool attacked){
    if(heart())return cast_heart(me,ts,moved);
    if(!tactical())check_budget();if(!me.can_cast())return false;
    if(tactical()&&rows)ts=filtered(ts,[&](auto t){return boss_allowed(me,t);});
    struct Option{double value;bc::ability ability;std::optional<Unit> target;std::optional<V> destination;};
    std::vector<Option> options;
    for(auto a:me.abilities()){
        if(!tactical())check_budget();if(!a.is_ready())continue;auto info=ability_info(a);if(moved&&info.exclusive)continue;
        if(a.is_attack_reset()){
            auto mask=attack_mask(me);bool in_range=std::any_of(ts.begin(),ts.end(),[&](auto t){return t.visible()&&t.health()>0&&mask.is_set(t.position());});
            if(attacked&&!me.can_attack()&&in_range)options.push_back({me.strength()*(kind==C::varg?2:1),a,{},{}});
        }else if(a.is_shield()){
            auto threats=filtered(ts,[&](auto t){return t.visible()&&t.strength()>0&&dist(me.position(),t.position())<=t.attack_range();});
            if(!threats.empty()&&!me.buffs().has_shield())options.push_back({std::min(double(a.shield_amount()),sum(threats,[](auto t){return t.strength();})*5),a,{},{}});
        }else if(a.is_heal()){
            for(auto ally:allies())if(id(ally)!=id(me)&&dist(me.position(),ally.position())<=info.range){auto heal=a.heal_amount(ally);if(heal>50){auto danger=pressure(ally.position());options.push_back({heal*(ally.health()<danger*2+60?3:1),a,Unit(ally),{}});}}
        }else if(a.is_damage()||a.is_cc()||a.is_aoe_damage()){
            auto valid=filtered(ts,[&](auto t){return t.visible()&&t.health()>0&&dist(me.position(),t.position())<=info.range;});
            for(auto& t:valid){
                check_budget();if(t.camp()&&!a.can_target_camps())continue;if(t.champion()&&!a.can_target_enemies())continue;
                auto c=t.champion();bool immune=c&&c->champion_name()==C::marcella;if(a.is_cc()&&immune&&info.modifier==0)continue;
                double value=0;std::optional<Unit> target;std::optional<V> destination;
                if(a.is_aoe_damage()){
                    for(auto& other:ts)if(other.visible()&&other.health()>0&&dist(other.position(),t.position())<=info.radius)value+=std::min(double(other.health()),me.focus()*info.modifier);
                    destination=t.position();
                }else{value=std::min(double(t.health()),me.focus()*info.modifier);target=t;}
                if(c)value*=1.5;if(!immune&&a.is_cc())value+=c&&c->is_submitting_gems()?250:30;
                options.push_back({value,a,target,destination});
            }
        }
    }
    if(options.empty())return false;auto o=best_max(options,[](auto x){return x.value;});
    try{check_budget();return o.destination?o.ability.use(*o.destination):(o.target?o.target->use(o.ability):o.ability.use());}
    catch(const bc::error& e){if(o.ability.is_attack_reset()&&std::string(e.what())=="An available attack cannot be reset."){std::cout<<"guarded reset: already available"<<std::endl;return false;}throw;}
}
bool Bot::cast_heart(Champion me,const std::vector<Unit>& ts,bool moved){
    check_budget();if(!me.can_cast())return false;
    struct Hit{V p;double hp;bool champion;};std::vector<Hit> units;std::vector<V> forbidden;double incoming=0;
    for(auto& t:ts){check_budget();if(!t.visible()||t.health()<=0)continue;auto p=t.position();bool awake=t.champion()||t.camp()->is_awake();
        if(awake&&dist(p,me.position())<=t.attack_range()+1)incoming+=t.strength();
        if(auto camp=t.camp()){
            auto group=camp_group_by_id.find(id(*camp));bool selected=target>=0&&(group!=camp_group_by_id.end()?group->second==target:camp->camp_group()==groups[target]);
            if(!selected){forbidden.push_back(p);continue;}
        }
        units.push_back({p,t.health(),bool(t.champion())});
    }
    std::optional<bc::ability> shield,dash;
    for(auto a:me.abilities()){if(a.is_shield()&&a.is_ready()&&!shield)shield=a;if(a.is_dash()&&a.is_ready()&&!dash)dash=a;}
    if(shield&&incoming&&!me.buffs().has_shield()){check_budget();return shield->use();}
    if(recovering||target<0||!dash||units.empty())return false;
    auto info=ability_info(*dash);if(moved&&info.exclusive)return false;
    auto blocked=blockers(me);auto candidates=(blocked.reachable_tiles(me.position(),int(info.range))&dash->valid_tiles()&bc::vision::visible_tiles()).positions();
    auto nearest=[&](V p){int d=100000;for(auto h:units)d=std::min(d,dist(p,h.p));return d;};
    std::stable_sort(candidates.begin(),candidates.end(),[&](auto a,auto b){return nearest(a)<nearest(b);});if(candidates.size()>9)candidates.resize(9);
    auto damage=dash->damage_amount();auto current_risk=pressure(me.position());std::optional<V> best;double best_score=0;
    for(auto p:candidates){
        check_budget();if(bc::fuel_remaining()<strategy::native_fuel(650000))break;
        if(p==me.position()||std::any_of(forbidden.begin(),forbidden.end(),[&](auto q){return dist(p,q)<=info.radius;}))continue;
        std::vector<std::pair<double,bool>> hits;for(auto h:units)if(dist(p,h.p)<=info.radius)hits.push_back({h.hp,h.champion});if(hits.empty())continue;
        double risk=pressure(p);if(!strategy::safe_heart_landing(risk,me.health()))continue;
        double score=strategy::heart_dash_score(hits,damage,risk,current_risk);if(score>best_score){best_score=score;best=p;}
    }
    if(!best)return false;check_budget();if(blockers(me).is_set(*best))return false;return dash->use(*best);
}
void Bot::combat(Champion me,const std::vector<Unit>& ts,bool moved){
    if(tactical())check_budget();bool attacked=attack(me,ts);if(!me.is_alive())return;if(!tactical())check_budget();cast(me,ts,moved,attacked);if(!me.is_alive())return;if(tactical())check_budget();attack(me,targets());
}
bool Bot::escape_dash(Champion me,const std::vector<RetreatThreat>& threats){
    if(!specialist())check_budget();if(!me.can_cast())return false;
    std::optional<bc::ability> a;for(auto item:me.abilities())if(item.is_dash()&&item.is_ready()){a=item;break;}if(!a)return false;
    auto positions=blockers(me).reachable_tiles(me.position(),2).positions();if(positions.empty())return false;
    auto score=[&](V p){int s=100000;for(auto t:threats)s=std::min(s,dist(p,t.position)-t.radius);return s;};auto destination=best_max(positions,score);check_budget();return score(destination)>score(me.position())&&a->use(destination);
}
void Bot::retreat(Champion me){
    if(!specialist())check_budget();std::vector<RetreatThreat> danger;auto origin=me.position();bool current=heart()||heart_alert;
    if(current&&heart_alert&&heart_threat)danger.push_back(*heart_threat);
    for(auto e:enemies()){if(!specialist())check_budget();int radius=e.attack_range();if(current&&e.champion_name()==C::heart_of_ruin)radius=std::max(radius,3);if(dist(origin,e.position())<=radius+1)danger.push_back({e.position(),radius});}
    for(auto c:visible_camps()){if(!specialist())check_budget();if((!current||c.is_awake())&&c.strength()>0&&dist(origin,c.position())<=c.attack_range())danger.push_back({c.position(),c.attack_range()});}
    if(!danger.empty()&&(me.can_move()||current)){
        if(!me.can_move())return;if(escape_dash(me,danger))return;
        auto candidates=blockers(me).reachable_tiles(origin,1).positions();
        if(!candidates.empty()){
            auto points=spawn.positions();auto score=[&](V p){int safe=100000,home=100000;for(auto t:danger)safe=std::min(safe,dist(p,t.position)-t.radius);
                if(current)home=dist(p,points.front());else for(auto s:points)home=std::min(home,dist(p,s));return std::pair(safe,-home);};
            auto best=best_max(candidates,score);check_budget();if(best!=origin&&!blockers(me).is_set(best))me.move_absolute(best);
        }return;
    }check_budget();me.recall();
}
bool Bot::support(Champion me){
    if(kind!=C::willow)return false;auto as=filtered(allies(),[&](auto a){return id(a)!=id(me);});if(as.empty())return false;
    auto ally=best_max(as,[&](auto a){return a.max_health()-a.health()+pressure(a.position())*2;});
    if(ally.health()<ally.max_health()*.85||pressure(ally.position())>30){claim(-1);cast(me,targets());if(dist(me.position(),ally.position())>3)move(me,disk(ally.position(),3));attack(me,targets());return true;}return false;
}
bool Bot::engage(Champion me,bool defend_only){
    auto es=enemies();std::stable_sort(es.begin(),es.end(),[](auto a,auto b){return a.health()<b.health();});
    for(auto e:es){check_budget();auto p=e.position();if(dist(me.position(),p)>7)continue;if(defend_only&&dist(me.position(),p)>me.attack_range()+1)continue;
        bool contest=false;for(std::size_t i=0;i<crates.size();++i)if(crates[i]&&dist(p,centers[i])<=3)contest=true;
        if(corners&&!contest&&!defend_only)continue;bool home=dist(p,home_center)<=dist(p,enemy_center);
        auto friends=filtered(allies(),[&](auto a){return dist(a.position(),p)<=6&&a.health()>=a.max_health()*.65;});auto foes=filtered(es,[&](auto a){return dist(a.position(),p)<=6;});
        if(!contest&&friends.size()<2)continue;
        bool good=strategy::favorable_fight(sum(friends,[](auto a){return a.health();}),sum(friends,[](auto a){return a.strength()+.25*a.focus();}),sum(foes,[](auto a){return a.health();}),sum(foes,[](auto a){return a.strength()+.25*a.focus();}));
        if(!(home||contest||friends.size()>foes.size()))continue;if(!good){if(contest)report(p,true);continue;}
        claim(-1);combat(me,{Unit(e)});
        if(me.is_alive()&&e.is_visible()&&e.health()>0&&dist(me.position(),e.position())>me.attack_range()){move(me,disk(e.position(),me.attack_range()));if(me.is_alive()){std::vector<Unit> ts;for(auto c:enemies())ts.emplace_back(c);combat(me,ts,true);}}return true;
    }
    if(!defend_only&&help_request&&alert&&me.health()>=.8*me.max_health()&&me.gem_count()<40&&dist(me.position(),*alert)<=10&&dist(me.position(),*alert)>3){claim(-1);return move(me,disk(*alert,3));}return false;
}
