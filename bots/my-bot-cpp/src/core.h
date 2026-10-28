#pragma once
// SDK-independent equivalents of coordination, assignments, progress and tactics.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <map>
#include <iterator>
#include <optional>
#include <set>
#include <tuple>
#include <type_traits>
#include <vector>

namespace strategy {
// Like Python sorted(key=...), observe each key once before comparing.
// Comparators never query live engine state or mutate their sort keys.
template<class T,class F> void stable_sort_by_key(std::vector<T>& items,F key){
    using Key=std::decay_t<decltype(key(items.front()))>;
    struct Entry{Key key;std::size_t index;};
    std::vector<Entry> order;order.reserve(items.size());
    for(std::size_t i=0;i<items.size();++i)order.push_back({key(items[i]),i});
    std::stable_sort(order.begin(),order.end(),[](const Entry& a,const Entry& b){return a.key<b.key;});
    std::vector<T> sorted;sorted.reserve(items.size());
    for(const auto& entry:order)sorted.push_back(std::move(items[entry.index]));
    items=std::move(sorted);
}
template<class Range,class F> auto best_max(const Range& items,F f){auto best=items.begin();auto score=f(*best);for(auto it=std::next(items.begin());it!=items.end();++it){auto candidate=f(*it);if(candidate>score){best=it;score=candidate;}}return *best;}
template<class Range,class F> auto best_min(const Range& items,F f){auto best=items.begin();auto score=f(*best);for(auto it=std::next(items.begin());it!=items.end();++it){auto candidate=f(*it);if(candidate<score){best=it;score=candidate;}}return *best;}
// Engine 2.0.0 grants approximately 2,500,000 Python fuel vs 100,000 native fuel.
// Preserve reserve fractions rather than copying interpreter-specific totals.
constexpr std::uint64_t native_fuel(std::uint64_t python_fuel){return python_fuel/25;}
using Position=std::pair<int,int>;
struct Memory {
    std::array<std::uint8_t,8> bytes{};
    std::uint64_t read(int start,int count) const { std::uint64_t v=0;for(int i=0;i<count;++i)v|=std::uint64_t(bytes[start+i])<<(i*8);return v; }
    void write(int start,int count,std::uint64_t v){for(int i=0;i<count;++i)bytes[start+i]=std::uint8_t(v>>(i*8));}
    bool banking() const {return (bytes[4]&128)!=0;}
    std::array<int,6> claims(bool rows=false) const {
        std::array<int,6> result{};if(!rows&&banking())return result;
        auto v=read(0,5);for(int i=0;i<6;++i)result[i]=(v>>(i*6))&63;return result;
    }
    void claim(int slot,int index,bool rows=false){
        if(slot<0||slot>=6||(!rows&&banking()))return;
        auto v=read(0,5);auto encoded=index>=0&&index<63?index+1:0;
        write(0,5,(v&~(std::uint64_t(63)<<(slot*6)))|(std::uint64_t(encoded)<<(slot*6)));
    }
    void publish(int slot,int gems){
        if(slot<0||slot>=6)return;
        constexpr auto low=(std::uint64_t(1)<<39)-1;
        auto p=read(0,8);auto logical=banking()?((p&low)|((p>>40)<<39)):0;
        logical=(logical&~(std::uint64_t(1023)<<(slot*10)))|(std::uint64_t(std::clamp(gems,0,1023))<<(slot*10));
        write(0,8,(logical&low)|((logical>>39)<<40)|(std::uint64_t(1)<<39));
    }
    std::array<int,6> gems() const {
        std::array<int,6> result{};if(!banking())return result;
        auto p=read(0,8);auto logical=(p&((std::uint64_t(1)<<39)-1))|((p>>40)<<39);
        for(int i=0;i<6;++i)result[i]=(logical>>(i*10))&1023;return result;
    }
    void report(int x,int y,int round,bool danger,bool rows=false){
        if(!rows&&banking())return;
        write(5,3,x|(y<<7)|((round&255)<<14)|(1<<22)|(int(danger)<<23));
    }
    struct Alert{std::uint32_t token;std::optional<Position> position;int age;};
    Alert alert(int round,bool rows=false) const {
        if(!rows&&banking())return {0,{},255};auto v=std::uint32_t(read(5,3));
        return {v,(v&(1<<22))?std::optional<Position>{{v&127,(v>>7)&127}}:std::nullopt,(round-int((v>>14)&255))&255};
    }
};

struct CampAssignment{int index,distance;bool grouped;};
inline std::map<int,int> assign_home_camps(std::vector<std::pair<int,bool>> champions,std::vector<CampAssignment> camps){
    std::sort(champions.begin(),champions.end(),[](auto a,auto b){return std::pair(!a.second,a.first)<std::pair(!b.second,b.first);});
    std::map<int,int> owners;
    for(auto [slot,varg]:champions){
        if(camps.empty())break;bool grouped=varg&&std::any_of(camps.begin(),camps.end(),[](auto c){return c.grouped;});
        auto best=camps.end();
        for(auto it=camps.begin();it!=camps.end();++it)if(!grouped||it->grouped)
            if(best==camps.end()||std::pair(it->distance,it->index)<std::pair(best->distance,best->index))best=it;
        owners[best->index]=slot;camps.erase(best);
    }return owners;
}
struct Resources{int gold=0,gems=0,submitted=0;std::optional<double> hp;};
class Progress {
public:
    std::optional<int> goal;std::optional<double> best;std::optional<Resources> previous;
    int last_round=-1,idle=0;std::vector<Position> positions;
    void reset(){goal.reset();best.reset();previous.reset();last_round=-1;idle=0;positions.clear();}
    bool observe(int round,int next,Position position,double distance,Resources resources){
        if(last_round!=-1&&round!=last_round+1)reset();
        bool changed=!previous||std::tie(resources.gold,resources.gems,resources.submitted)!=std::tie(previous->gold,previous->gems,previous->submitted)
            ||(goal&&next==*goal&&resources.hp&&previous->hp&&*resources.hp<*previous->hp);
        if(!goal||next!=*goal)best=distance;
        bool closer=!best||distance<*best;idle=changed||closer?0:idle+1;
        goal=next;previous=resources;last_round=round;best=best?std::min(*best,distance):distance;
        positions.push_back(position);if(positions.size()>6)positions.erase(positions.begin());
        return idle>=18||(positions.size()==6&&std::set<Position>(positions.begin(),positions.end()).size()<=2&&idle>=6);
    }
};
inline bool lethal_recent_loss(std::optional<double> previous,int previous_round,double health,int round){return previous&&previous_round==round-1&&*previous-health>=health&&health>0;}
inline bool winning_load(int submitted,const std::array<int,6>& carried,int target=1000){int total=submitted;for(auto n:carried)total+=n;return total>=target;}
inline bool favorable_fight(double hp,double power,double enemy_hp,double enemy_power){return hp/std::max(enemy_power,1.0)>1.35*enemy_hp/std::max(power,1.0);}
inline bool has_jungle(bool strength,bool focus,bool health){return strength||focus||health;}
struct GroupProfile{double gold,gems,incoming;int size;bool boss,golem;};
struct MapProfile{double gold=0,gems=0;bool zero_gold=true,boss_only=false,has_groups=false,golems=false;int clustered=0;};
inline MapProfile classify(const std::vector<GroupProfile>& groups){
    MapProfile p;bool has_gems=false,all_boss=true;
    for(auto g:groups){p.gold+=g.gold;p.gems+=g.gems;p.has_groups|=g.size>1;p.golems|=g.golem;p.clustered+=g.size>=3&&g.incoming>0;if(g.gems>0){has_gems=true;all_boss&=g.boss;}}
    p.zero_gold=p.gold==0;p.boss_only=has_gems&&all_boss;return p;
}
// A cleared, observed reward is not a live boss fight.
inline bool boss_gate(bool boss,bool ready,double strength){return boss&&!ready&&strength<200;}
inline double boss_discount(bool boss,bool ready){return boss&&!ready?.15:1;}
inline bool heart_emergency(double damage,double health,int distance,double range,double radius,double speed){return damage>=.75*health&&distance<=int(range+radius+3*speed);}
inline bool safe_heart_landing(double risk,double health){return risk*3+50<health;}
inline double heart_dash_score(const std::vector<std::pair<double,bool>>& hits,double damage,double risk,double current_risk){double value=0;for(auto [hp,enemy]:hits)value+=std::min(hp,damage)*(enemy?1.3:1)+(hp<=damage?200:0);return value-3*std::max(0.0,risk-current_risk);}
class Random{std::uint64_t state;public:explicit Random(std::uint64_t seed):state(seed){} std::uint64_t below(std::uint64_t limit){state=state*6364136223846793005ULL+1442695040888963407ULL;return(state>>33)%limit;}};
}
