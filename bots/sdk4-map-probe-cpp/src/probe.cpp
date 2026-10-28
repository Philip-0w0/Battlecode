#include <cambc.h>
#include <iostream>
#include <algorithm>
namespace bc=cambc;
int main(){bool printed=false;while(true){
    if(!printed){
        std::cout<<"CATALOGUE {\"width\":"<<bc::map::width()<<",\"height\":"<<bc::map::height()<<",\"team_size\":"<<bc::draft::team_size()<<",\"altars\":"<<bc::map::altars().positions().size()<<",\"groups\":[";
        bool comma=false;for(auto g:bc::map::camp_groups()){
            bool boss=false,golem=false;double hp=0,incoming=0;int range=0;
            for(auto c:g){boss|=c.is_monolith();golem|=c.is_golem();hp+=c.base_stats().base_health;incoming+=c.base_stats().base_strength;range=std::max(range,c.attack_range());}
            if(comma)std::cout<<',';comma=true;std::cout<<"{\"gems\":"<<g.gem_value()<<",\"gold\":"<<g.gold_value()<<",\"size\":"<<g.camps().size()<<",\"hp\":"<<hp<<",\"attack_range\":"<<range<<",\"incoming\":"<<incoming<<",\"golem\":"<<(golem?"true":"false")<<",\"boss\":"<<(boss?"true":"false")<<'}';
        }std::cout<<"]}"<<std::endl;printed=true;
    }
    if(bc::is_draft()){auto chosen=bc::draft::current_draft(bc::team::ally);for(int i=0;i<12;++i){auto pick=static_cast<bc::champion_draft>(i);if(std::find(chosen.begin(),chosen.end(),pick)==chosen.end()){bc::draft::pick(pick);break;}}}
bc::end_turn();}}
