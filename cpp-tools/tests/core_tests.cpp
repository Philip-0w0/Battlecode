#include "../../bots/my-bot-cpp/src/core.h"
#include "../vendor/json.hpp"
#include <fstream>
#include <iostream>
#include <functional>
#include <stdexcept>
using Json=nlohmann::json;
using namespace strategy;
int checks=0,scenarios=0;
void require(bool condition,const std::string& message){++checks;if(!condition)throw std::runtime_error(message);}
void scenario(const std::string& name,const std::function<void()>& test){++scenarios;try{test();}catch(const std::exception& e){throw std::runtime_error(name+": "+e.what());}}
void unit_tests(){
    for(int slot=0;slot<6;++slot)scenario("independent claim slot "+std::to_string(slot),[=]{Memory m;m.report(50,80,254,true);m.claim(slot,62);for(int other=0;other<6;++other)require(m.claims()[other]==(other==slot?63:0),"claim overlap");auto a=m.alert(2);require(a.age==4&&a.position==Position(50,80),"claim changed alert");m.claim(slot,-1);require(m.claims()[slot]==0,"claim release");});
    for(int slot=0;slot<6;++slot)scenario("exact gem slot "+std::to_string(slot),[=]{Memory m;m.claim(0,40);m.publish(slot,999);require(m.banking(),"mode missing");for(int other=0;other<6;++other)require(m.gems()[other]==(other==slot?999:0),"gem overlap");auto saved=m.bytes;m.claim(2,6);m.report(2,3,4,true);require(m.bytes==saved,"normal protocol writes in banking mode");m.publish(slot,5000);require(m.gems()[slot]==1023,"upper gem clamp");m.publish(slot,-1);require(m.gems()[slot]==0,"lower gem clamp");});
    scenario("six gem counts skip marker",[]{Memory m;for(int i=0;i<6;++i)m.publish(i,100+i*33);for(int i=0;i<6;++i)require(m.gems()[i]==100+i*33,"marker shifted a count");require(m.claims()==std::array<int,6>{},"bank claims not empty");});
    scenario("uninitialized alert",[]{Memory m;require(!m.alert(100).position,"false alert");});
    scenario("alert round wrap and danger",[]{Memory m;m.report(127,126,255,true);auto a=m.alert(3);require(a.age==4&&a.position==Position(127,126)&&(a.token&(1<<23)),"bad wrap");});
    scenario("invalid slots ignored",[]{Memory m;auto saved=m.bytes;m.claim(6,30);m.claim(-1,30);m.publish(7,100);require(m.bytes==saved,"invalid slot mutated memory");});
    scenario("claim representability",[]{Memory m;m.claim(0,63);require(m.claims()[0]==0,"invalid group wrapped");m.claim(0,0);require(m.claims()[0]==1,"zero group missing");});
    scenario("rows protocol preserves alert",[]{Memory m;m.report(12,14,22,true,true);m.claim(5,12,true);require(m.alert(22,true).position==Position(12,14),"rows alert overlap");});
    scenario("two-tile loop becomes idle",[]{Progress p;bool detected=false;for(int r=0;r<10;++r)detected|=p.observe(r,1,{0,r%2},10,{0,8,0,100});require(detected,"loop not detected");});
    scenario("combat and capture remain productive",[]{Progress p;for(int r=0;r<40;++r)require(!p.observe(r,1,{0,0},0,{r/10,0,0,100-r}),"false combat stall");});
    scenario("movement toward goal",[]{Progress p;for(int r=0;r<40;++r)require(!p.observe(r,1,{r,0},80-r,{0,0,0,100}),"false route stall");});
    scenario("goal churn does not hide idle",[]{Progress p;bool detected=false;for(int r=0;r<30;++r)detected|=p.observe(r,r%2,{0,0},10,{0,0,0,100.+r%2});require(detected,"churn masks stall");});
    scenario("channel gap resets progress",[]{Progress p;for(int r=0;r<5;++r)p.observe(r,1,{0,0},10,{0,0,0,100});require(!p.observe(90,1,{0,0},10,{0,0,0,100})&&p.idle==0,"gap did not reset");});
    scenario("Varg gets grouped camp first",[]{auto owners=assign_home_camps({{0,false},{1,true},{2,false},{3,false}},{{0,10,false},{1,12,true},{2,20,true},{3,30,true}});require(owners==std::map<int,int>{{0,0},{1,1},{2,2},{3,3}},"assignment mismatch");});
    scenario("assignment independent of execution order",[]{auto a=assign_home_camps({{2,false},{0,false},{1,true}},{{0,10,false},{1,12,true}}),b=assign_home_camps({{1,true},{2,false},{0,false}},{{1,12,true},{0,10,false}});require(a==b,"ordering changed ownership");});
    scenario("burst health comparison",[]{require(lethal_recent_loss(1000,4,400,5),"missed burst");require(!lethal_recent_loss(1000,3,400,5),"stale sample");require(!lethal_recent_loss({},4,400,5),"empty sample");require(!lethal_recent_loss(1000,4,0,5),"dead sample");});
    scenario("winning carried totals",[]{require(winning_load(900,{10,20,30,40,0,0}),"winning load missed");require(!winning_load(899,{10,20,30,40,0,0}),"early winning load");});
    scenario("favorable fight margin",[]{require(favorable_fight(1000,100,500,100),"good fight missed");require(!favorable_fight(500,100,1000,100),"bad fight accepted");});
    scenario("all Jungle emblem variants",[]{require(has_jungle(true,false,false)&&has_jungle(false,true,false)&&has_jungle(false,false,true)&&!has_jungle(false,false,false),"missing Jungle passive");});
    scenario("map role classification",[]{auto p=classify({{100,200,200,1,true,false},{80,0,20,1,false,true}});require(p.boss_only&&p.golems&&!p.zero_gold,"map role mismatch");});
    scenario("ordinary gem group breaks boss-only",[]{auto p=classify({{0,200,200,1,true,false},{0,10,0,1,false,false}});require(!p.boss_only&&p.zero_gold,"reward classification mismatch");});
    scenario("empty map is not boss-only",[]{require(!classify({}).boss_only,"empty map classified boss-only");});
    scenario("weak cleared boss collector",[]{require(!boss_gate(true,true,30),"cleared boss blocked");});
    scenario("live weak boss safeguard",[]{require(boss_gate(true,false,30),"live boss allowed");});
    scenario("unknown weak boss safeguard",[]{require(boss_gate(true,false,30),"unknown boss assumed clear");});
    scenario("no cleared boss discount",[]{require(boss_discount(true,true)==1&&boss_discount(true,false)==.15,"boss discount mismatch");});
    scenario("Heart burst movement horizon",[]{require(heart_emergency(850,1000,6,2,1,1),"missed Heart threat");require(!heart_emergency(850,1000,7,2,1,1),"excess Heart reach");require(!heart_emergency(700,1000,3,2,1,1),"low damage emergency");});
    scenario("Heart unsafe landing",[]{require(!safe_heart_landing(400,1000)&&safe_heart_landing(100,1000),"Heart landing mismatch");});
    scenario("Heart incremental risk",[]{std::vector<std::pair<double,bool>> hits={{100,false}};require(heart_dash_score(hits,150,100,100)==300,"existing pressure penalized twice");require(heart_dash_score(hits,150,150,100)==150,"new pressure ignored");});
    scenario("grouped map detection",[]{auto p=classify({{80,20,20,3,false,false}});require(p.has_groups&&p.clustered==1,"group classification mismatch");});
    scenario("fixed PRNG modulo",[]{Random a(123),b(123);for(int i=0;i<100;++i)require(a.below(17)==b.below(17),"nondeterministic PRNG");});
    scenario("native fuel reserve fraction",[]{require(native_fuel(250000)==10000&&native_fuel(900000)==36000&&native_fuel(1100000)==44000&&native_fuel(650000)==26000,"interpreter fuel thresholds copied literally");});
    scenario("priority observes each candidate once",[]{int calls=0;require(best_max(std::vector<int>{3,8,4},[&](int x){++calls;return x;})==8&&calls==3,"candidate queried more than once");});
    scenario("priority retains first equal target",[]{std::vector<std::pair<int,int>> values={{1,9},{2,9},{3,9}};require(best_max(values,[](auto p){return p.second;}).first==1&&best_min(values,[](auto p){return p.second;}).first==1,"tie order differs from Python");});
    scenario("sort observes live keys once and preserves first ties",[]{
        struct Enemy{int identity;double health;};
        std::vector<Enemy> values={{1,9},{2,3},{3,3},{4,8}};int calls=0;
        stable_sort_by_key(values,[&](const Enemy& enemy){++calls;return enemy.health;});
        require(calls==4,"sort repeatedly queried a live health key");
        require(values[0].identity==2&&values[1].identity==3&&values[2].identity==4&&values[3].identity==1,"sort order or first-tie order differs from Python");
    });
    scenario("cached sort handles empty and singleton ranges",[]{
        std::vector<int> values;int calls=0;
        stable_sort_by_key(values,[&](int value){++calls;return value;});
        require(calls==0&&values.empty(),"empty sort observed a nonexistent key");
        values={7};stable_sort_by_key(values,[&](int value){++calls;return value;});
        require(calls==1&&values==std::vector<int>{7},"singleton key was not observed exactly once");
    });
}
void differential_tests(const Json& fixtures){
    Memory memory;
    for(auto& f:fixtures["memory"]){auto& a=f["action"];std::string kind=a["kind"];bool rows=a["rows"];if(kind=="claim")memory.claim(a["slot"],a["index"],rows);else if(kind=="report")memory.report(a["x"],a["y"],a["round"],a["danger"],rows);else memory.publish(a["slot"],a["gems"]);
        require(Json(memory.bytes)==f["bytes"],"Python memory bytes diverged");require(Json(memory.claims())==f["claims"],"Python claims diverged");require(Json(memory.claims(true))==f["rows_claims"],"Python Rows claims diverged");require(Json(memory.gems())==f["gems"],"Python gem counts diverged");auto alert=memory.alert(a["round"],rows);require(alert.token==f["token"]&&alert.age==f["age"],"Python alert metadata diverged");require((alert.position?Json::array({alert.position->first,alert.position->second}):Json())==f["position"],"Python alert position diverged");}
    Progress progress;
    for(auto& f:fixtures["progress"]){auto& r=f["resources"];Resources resource{r[0],r[1],r[2],{}};if(!r[3].is_null())resource.hp=r[3].get<double>();bool triggered=progress.observe(f["round"],f["goal"],{f["position"][0],f["position"][1]},f["distance"],resource);require(triggered==f["triggered"]&&progress.idle==f["idle"],"Python progress diverged");}
    for(auto& f:fixtures["assignments"]){std::vector<std::pair<int,bool>> champions;std::vector<CampAssignment> camps;for(auto c:f["champions"])champions.push_back({c[0],c[1]});for(auto c:f["camps"])camps.push_back({c[0],c[1],c[2]});auto owners=assign_home_camps(champions,camps);Json actual=Json::object();for(auto [k,v]:owners)actual[std::to_string(k)]=v;require(actual==f["owners"],"Python ownership diverged");}
    for(auto& f:fixtures["profiles"]){std::vector<GroupProfile> groups;for(auto g:f["groups"])groups.push_back({g["gold"],g["gems"],g["incoming"],g["size"],g["boss"],g["golem"]});auto p=classify(groups);Json actual={{"gold",p.gold},{"gems",p.gems},{"zero_gold",p.zero_gold},{"boss_only",p.boss_only},{"clustered",p.clustered},{"has_groups",p.has_groups},{"golems",p.golems}};require(actual==f["expected"],"Python map roles diverged");}
    auto seed=std::uint64_t(10)*73856093^std::uint64_t(22)*19349663^std::uint64_t(10)*83492791^std::uint64_t(23)*2654435761ULL;Random random(seed);
    for(auto& f:fixtures["random"])require(random.below(f["limit"].get<std::uint64_t>())==f["value"],"Python randomness diverged");
}
int main(int argc,char** argv){try{if(argc!=2)throw std::runtime_error("usage: core-tests.exe python-parity.json");std::ifstream input(argv[1]);if(!input)throw std::runtime_error("cannot read Python parity fixture");Json fixtures;input>>fixtures;unit_tests();differential_tests(fixtures);std::cout<<"PASS "<<scenarios<<" named scenarios, 1280 Python differential fixtures, "<<checks<<" assertions\n";return 0;}catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
