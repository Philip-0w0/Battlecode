#pragma once
#include <cambc.h>
#include "core.h"
#include <functional>
#include <limits>
#include <numeric>
#include <iostream>
#include <unordered_map>
namespace bc=cambc;
using C=bc::champion_type;using D=bc::champion_draft;using T=bc::team;using I=bc::item_type;
using V=bc::vec2;using Board=bc::bitboard;using Champion=bc::champion;
inline int dist(V a,V b){return a.chebyshev_distance(b);}
inline int id(const Champion& c){return static_cast<int>(static_cast<bc::handle_champion_t>(c));}
inline int id(const bc::camp& c){return static_cast<int>(static_cast<bc::handle_camp_t>(c));}
inline Board disk(V p,int radius){Board b;b.draw_chebyshev(p,radius);return b;}
template<class Range,class F> double sum(const Range& items,F f){double value=0;for(const auto& x:items)value+=f(x);return value;}
template<class Range,class F> auto filtered(const Range& items,F f){std::vector<typename Range::value_type> result;for(const auto& x:items)if(f(x))result.push_back(x);return result;}
using strategy::best_max;using strategy::best_min;
struct Unit {
    std::variant<Champion,bc::camp> value;
    Unit(Champion c):value(c){} Unit(bc::camp c):value(c){}
    const Champion* champion() const{return std::get_if<Champion>(&value);}
    const bc::camp* camp() const{return std::get_if<bc::camp>(&value);}
    template<class F> auto query(F f)const{return std::visit(f,value);}
    V position()const{return query([](auto& c){return c.position();});}
    float health()const{return query([](auto& c){return c.health();});}
    float max_health()const{return query([](auto& c){return c.max_health();});}
    float strength()const{return query([](auto& c){return c.strength();});}
    int attack_range()const{return query([](auto& c){return c.attack_range();});}
    bool visible()const{return query([](auto& c){return c.is_visible();});}
    bool use(const bc::ability& a)const{return query([&](auto& c){return a.use(c);});}
    void attack(Champion me)const{query([&](auto& c){me.attack(c);});}
};
struct AbilityInfo {double range=0,modifier=0,radius=0;bool exclusive=false;};
inline AbilityInfo ability_info(const bc::ability& a){return std::visit([](const auto& p){AbilityInfo out;out.exclusive=p.exclusive_with_movement;if constexpr(requires{p.range;})out.range=p.range;if constexpr(requires{p.modifier;})out.modifier=p.modifier;if constexpr(requires{p.radius;})out.radius=p.radius;return out;},a.info().value());}
enum class Mode {economy,tactical,rows};
struct TurnBudget{};
struct GroupStats{double hp,incoming;bool boss;};
struct Threat{V position;double damage;int radius;};
struct RetreatThreat{V position;int radius;};
class Bot {
    Mode mode=Mode::economy;
    bool ready=false,recovering=false,collision=false,home_bottom=false,rows=false,corners=false,return_from_inner=false,help_request=false;
    int target=-1,slot=0,turns=0,action_round=0,report_seen=-100,bank_target=-1,stalled=0,last_target=-1;
    std::optional<std::uint32_t> report_token;
    std::optional<V> last_position,alert;
    std::optional<double> previous_health;
    int previous_round=-1;
    C kind=C::varg;
    std::vector<bc::map::camp_group> groups;
    std::map<std::pair<int,int>,bc::camp> camp_by_tile;
    std::map<int,int> camp_group_by_id;
    std::vector<GroupStats> stats;
    std::vector<Board> masks;
    std::vector<V> centers,altars;
    Board spawn,terrain;
    std::vector<Champion> allies_by_slot,enemy_roster;
    std::vector<bc::distance_field> path_fields,altar_fields;
    bc::distance_field home_field;
    V home_center{},enemy_center{};
    std::vector<double> home_distances,group_rewards,altar_home;
    std::vector<bool> home_groups,crates,altar_groups;
    std::set<int> boss_camps,rows_home;
    std::map<int,int> rows_owners,sleep_until,failed_until;
    std::vector<Threat> threats;
    strategy::Progress progress,route_progress;
    int detour_until=-1;
    std::vector<V> detour_tiles;
    std::vector<Champion> enemy_hearts;
    bool heart_alert=false;
    std::optional<RetreatThreat> heart_threat;
    strategy::MapProfile map_info;
    bool tactical()const{return mode==Mode::tactical;}
    bool specialist()const{return mode==Mode::rows;}
    bool heart()const{return !specialist()&&kind==C::heart_of_ruin;}
    void check_budget();void setup(Champion);void claim(int);
    std::vector<Champion> enemies();std::vector<Champion> allies();
    std::vector<bc::camp> visible_camps();std::vector<Unit> targets();
    Board blockers(Champion);bool move(Champion,Board);Board attack_mask(Champion);
    void shop(Champion);bool attack(Champion,const std::vector<Unit>&);
    bool cast(Champion,std::vector<Unit>,bool moved=false,bool attacked=false);
    bool cast_heart(Champion,const std::vector<Unit>&,bool);
    void combat(Champion,const std::vector<Unit>&,bool moved=false);
    double pressure(V)const;void communicate(Champion);void observe_heart(Champion);
    int choose_group(Champion);void farm(Champion);bool bank(Champion);bool crystal_delivery(Champion);
    bool support(Champion);bool escape_dash(Champion,const std::vector<RetreatThreat>&);void retreat(Champion);
    bool finish_camp(Champion);bool boss_allowed(Champion,const Unit&);bool engage(Champion,bool defend_only=false);
    strategy::Memory memory()const;void write_memory(const strategy::Memory&,int offset,int count)const;void report(V,bool);
public:Bot();void play_turn();
};
strategy::MapProfile profile();void play_draft();
