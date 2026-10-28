#include "controller.h"
Bot::Bot(){
    std::set<std::pair<int,int>> a;for(auto p:bc::map::altars().positions())a.insert({p.x,p.y});
    auto w=bc::map::width(),h=bc::map::height();
    rows=w==50&&h==50&&a==std::set<std::pair<int,int>>{{15,16},{34,33}};
    bool packs=w==31&&h==31&&a==std::set<std::pair<int,int>>{{2,6},{28,6},{2,15},{28,15},{2,24},{28,24}};
    bool eight=w==41&&h==30&&a==std::set<std::pair<int,int>>{{20,15}};
    mode=rows?Mode::rows:(packs||eight?Mode::tactical:Mode::economy);
}
strategy::Memory Bot::memory()const{strategy::Memory m;bc::shared_memory.read(0,std::as_writable_bytes(std::span(m.bytes)));return m;}
void Bot::write_memory(const strategy::Memory& m,int start,int count)const{bc::shared_memory.write(start,std::as_bytes(std::span(m.bytes).subspan(start,count)));}
void Bot::claim(int index){target=index;auto m=memory();m.claim(slot,index,specialist());write_memory(m,0,5);}
void Bot::report(V p,bool danger){auto m=memory();m.report(p.x,p.y,bc::round_number(),danger,specialist());write_memory(m,5,3);}
void Bot::check_budget(){if(bc::round_number()!=action_round||bc::fuel_remaining()<strategy::native_fuel(250000)||(!specialist()&&!bc::self().is_alive()))throw TurnBudget{};}
void Bot::setup(Champion me){
    progress.reset();route_progress.reset();detour_until=-1;detour_tiles.clear();heart_alert=false;heart_threat.reset();
    enemy_roster=bc::champions(T::enemy);
    if(!specialist())enemy_hearts=filtered(enemy_roster,[](auto c){return c.champion_name()==C::heart_of_ruin;});
    groups=bc::map::camp_groups();camp_by_tile.clear();camp_group_by_id.clear();stats.clear();boss_camps.clear();masks.clear();centers.clear();
    std::vector<strategy::GroupProfile> profile_data;
    path_fields.clear();altar_fields.clear();altar_home.clear();home_distances.clear();home_groups.clear();crates.clear();group_rewards.clear();altar_groups.clear();
    for(auto& group:groups){
        double hp=0,incoming=0;bool boss=false,crate=false,golem=false;
        for(auto c:group){auto p=c.spawn_position();camp_by_tile.insert_or_assign(std::pair(p.x,p.y),c);camp_group_by_id[id(c)]=stats.size();auto base=c.base_stats();hp+=base.base_health;incoming+=base.base_strength;boss|=c.is_monolith();crate|=c.is_gem_cluster();golem|=c.is_golem();}
        profile_data.push_back({double(group.gold_value()),double(group.gem_value()),incoming,int(group.camps().size()),boss,golem});
        stats.push_back({hp,incoming,boss});masks.push_back(group.spawn_tiles());centers.push_back(masks.back().positions().front());
        if(boss)for(auto c:group)boss_camps.insert(id(c));
        crates.push_back(crate);group_rewards.push_back(group.gem_value()+.18*group.gold_value());
    }
    map_info=strategy::classify(profile_data);
    altars=bc::map::altars().positions();spawn=bc::map::spawn_region(T::ally);
    terrain=bc::map::walls()|bc::map::holes()|bc::map::altars()|bc::map::spawn_region(T::enemy);
    allies_by_slot=bc::champions(T::ally);std::sort(allies_by_slot.begin(),allies_by_slot.end(),[](auto a,auto b){return id(a)<id(b);});
    for(std::size_t i=0;i<allies_by_slot.size();++i)if(id(allies_by_slot[i])==id(me))slot=i;
    kind=me.champion_name();std::set<std::pair<int,int>> a;for(auto p:altars)a.insert({p.x,p.y});
    collision=bc::map::width()==41&&bc::map::height()==41&&a==std::set<std::pair<int,int>>{{27,20},{39,20}};
    auto spawn_points=spawn.positions();home_bottom=std::any_of(spawn_points.begin(),spawn_points.end(),[](auto p){return p.y<10;});
    corners=bc::map::width()==71&&bc::map::height()==71&&altars.size()==5;
    home_center=spawn_points.front();enemy_center=bc::map::spawn_region(T::enemy).positions().front();
    if(tactical()){
        Board visited;home_field.compute(terrain,spawn,visited);
        for(std::size_t i=0;i<groups.size();++i){
            auto points=masks[i].positions();home_distances.push_back(dist(best_min(points,[&](auto p){return dist(p,home_center);}),home_center));
            home_groups.push_back(dist(centers[i],home_center)<=dist(centers[i],enemy_center));
            altar_groups.push_back(std::any_of(altars.begin(),altars.end(),[&](auto p){return dist(centers[i],p)<=4;}));
        }
        for(auto p:altars){auto positions=(disk(p,1)&~terrain).positions();double nearest=100000;for(auto q:positions)nearest=std::min(nearest,double(home_field.get(q)));altar_home.push_back(nearest);
            bc::distance_field field;Board visited;field.compute(terrain,disk(p,bc::constants::submit_gems_range)&~terrain,visited);altar_fields.push_back(std::move(field));}
    }
    for(auto& mask:masks){bc::distance_field field;Board visited;field.compute(terrain,mask&~terrain,visited);path_fields.push_back(std::move(field));}
    rows_owners.clear();rows_home.clear();
    if(specialist()&&rows){
        std::vector<strategy::CampAssignment> camps;std::vector<std::pair<int,bool>> champions;
        for(std::size_t i=0;i<centers.size();++i)if(!stats[i].boss&&dist(centers[i],home_center)<dist(centers[i],enemy_center)){
            int distance=path_fields[i].get(home_center);if(distance<10000){rows_home.insert(i);camps.push_back({int(i),distance,stats[i].incoming>0&&groups[i].camps().size()>1});}}
        for(std::size_t i=0;i<allies_by_slot.size();++i)champions.push_back({int(i),allies_by_slot[i].champion_name()==C::varg});
        rows_owners=strategy::assign_home_camps(champions,camps);
    }
    ready=true;me.set_priority(20-slot);
}
std::vector<Champion> Bot::enemies(){return filtered(enemy_roster,[](const auto& e){return e.is_alive()&&e.is_visible();});}
std::vector<Champion> Bot::allies(){return filtered(allies_by_slot,[](const auto& e){return e.is_alive()&&e.is_visible();});}
std::vector<bc::camp> Bot::visible_camps(){
    if(tactical()||heart())check_budget();std::vector<bc::camp> result;int n=0;
    for(auto p:bc::vision::camp_tiles().positions()){
        if((tactical()||heart())&&n++%4==0)check_budget();
        auto found=camp_by_tile.find({p.x,p.y});
        if(found!=camp_by_tile.end()){auto c=found->second;if(c.is_visible()&&c.health()>0)result.push_back(c);}
        else if(heart()){auto c=bc::vision::camp_at(p);if(c.is_visible()&&c.health()>0)result.push_back(c);}
    }return result;
}
std::vector<Unit> Bot::targets(){std::vector<Unit> out;for(auto e:enemies())out.emplace_back(e);for(auto c:visible_camps())out.emplace_back(c);return out;}
Board Bot::blockers(Champion me){
    auto b=terrain|bc::vision::champion_tiles()|bc::vision::camp_tiles()|bc::vision::teleport_tiles();auto origin=me.position();b.set(origin,false);
    if(!specialist()&&bc::round_number()<detour_until)for(auto p:detour_tiles)if(p!=origin)b.set(p,true);return b;
}
bool Bot::move(Champion me,Board goals){
    if(!specialist()){
        check_budget();if(me.can_move()&&!goals.is_set(me.position())){
            auto p=me.position();double distance=target>=0?path_fields[target].get(p):dist(p,best_min(altars,[&](auto a){return dist(p,a);}));
            route_progress.observe(bc::round_number(),(target+1)*2+bool(me.gem_count()),{p.x,p.y},distance,{int(me.gold_count()),int(me.gem_count()),int(bc::global_submitted_gems(T::ally)),{}});
            if(route_progress.idle>=60){detour_tiles.clear();std::set<strategy::Position> unique(route_progress.positions.begin(),route_progress.positions.end());for(auto [x,y]:unique)if(x!=p.x||y!=p.y)detour_tiles.push_back({x,y});detour_until=bc::round_number()+6;route_progress.reset();}
        }
    }
    if(!me.can_move()||goals.is_set(me.position()))return true;
    auto blocked=blockers(me);goals&=~blocked;if(goals.is_empty())return false;
    bc::distance_field field;Board visited;field.compute_to(blocked,goals,disk(me.position(),0),visited);auto step=field.next_move_from(me.position());if(!step)return false;
    check_budget();if(!blockers(me).is_set(me.position()+*step)&&me.can_move()&&me.move(*step))return true;
    blocked=blockers(me);goals&=~blocked;visited.clear();field.compute_to(blocked,goals,disk(me.position(),0),visited);step=field.next_move_from(me.position());check_budget();
    return step&&me.can_move()&&!blockers(me).is_set(me.position()+*step)&&me.move(*step);
}
Board Bot::attack_mask(Champion me){check_budget();auto p=me.position();int radius=me.attack_range();check_budget();return disk({p.x,p.y},radius);}
double Bot::pressure(V p)const{double out=0;for(auto t:threats)if(dist(p,t.position)<=t.radius)out+=t.damage;return out;}
void Bot::communicate(Champion me){
    if(heart()){
        threats.clear();for(auto c:visible_camps()){check_budget();if(c.is_awake()&&c.strength()>0)threats.push_back({c.position(),c.strength(),c.attack_range()});}
        for(auto e:enemies()){check_budget();threats.push_back({e.position(),e.strength()+.3*e.focus(),std::max(4,e.attack_range()+1)});}
    }
    auto old=memory().alert(bc::round_number(),specialist());
    auto es=enemies();if(!es.empty()){auto e=best_min(es,[&](auto c){return dist(me.position(),c.position());});bool danger=pressure(me.position())*3>me.health();if(!tactical()||danger||!(old.token&(1<<23))||old.age>3)report(e.position(),danger);}
    auto info=memory().alert(bc::round_number(),specialist());
    if(!report_token||info.token!=*report_token){report_token=info.token;report_seen=bc::round_number();}
    alert.reset();help_request=false;
    if(info.position&&info.age<=8&&bc::round_number()-report_seen<=8){alert=V{info.position->first,info.position->second};help_request=tactical()&&(info.token&(1<<23))&&info.age<=3;}
    if(!specialist())observe_heart(me);
}
void Bot::observe_heart(Champion me){
    heart_alert=false;heart_threat.reset();
    if(enemy_hearts.empty())return;
    // Ability metadata binds at construction. A handle created while hidden
    // permanently holds a hidden-info sentinel, so rebind visible opponents.
    for(auto e:bc::vision::champions(T::enemy)){check_budget();if(e.champion_name()!=C::heart_of_ruin||!e.is_alive()||!e.is_visible())continue;
        for(auto a:e.abilities()){check_budget();if(!a.is_dash()||a.cooldown()>1)continue;auto info=ability_info(a);double damage=a.damage_amount(me);auto p=e.position();int reach=int(info.range+info.radius+3*e.base_stats().base_move_speed);
            if(strategy::heart_emergency(damage,me.health(),dist(me.position(),p),info.range,info.radius,e.base_stats().base_move_speed)){heart_alert=true;heart_threat=RetreatThreat{{p.x,p.y},reach};threats.push_back({{p.x,p.y},damage,reach});}}
    }
}
