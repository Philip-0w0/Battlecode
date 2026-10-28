#include "controller.h"
strategy::MapProfile profile(){
    std::vector<strategy::GroupProfile> data;
    for(auto& g:bc::map::camp_groups()){
        bool boss=false,golem=false;double incoming=0;
        for(auto& c:g){boss|=c.is_monolith();golem|=c.is_golem();incoming+=c.base_stats().base_strength;}
        data.push_back({double(g.gold_value()),double(g.gem_value()),incoming,int(g.camps().size()),boss,golem});
    }return strategy::classify(data);
}
void play_draft(){
    auto chosen=bc::draft::current_draft(T::ally),enemy=bc::draft::current_draft(T::enemy);
    std::set<std::pair<int,int>> altars;for(auto p:bc::map::altars().positions())altars.insert({p.x,p.y});
    bool rows=bc::map::width()==50&&bc::map::height()==50&&altars==std::set<std::pair<int,int>>{{15,16},{34,33}};
    bool collision=bc::map::width()==41&&bc::map::height()==41&&altars==std::set<std::pair<int,int>>{{27,20},{39,20}};
    auto info=profile();std::vector<D> order;
    if(rows)order={D::varg,D::tavi,D::vendetta,D::ryth,D::vesper_vale};
    else if(collision)order={D::varg,D::willow,D::cassi_and_issac,D::tavi,D::marcella,D::heart_of_ruin};
    else if(info.has_groups)order={D::varg,D::tavi,D::vendetta,D::ryth,D::vesper_vale,D::heart_of_ruin};
    else order={D::vendetta,D::tavi,D::vesper_vale,D::ryth,D::varg,D::heart_of_ruin};
    if(!collision){int control=0;for(auto e:enemy)if(e==D::tavi||e==D::prism||e==D::ren||e==D::ryth||e==D::cassi_and_issac||(!rows&&e==D::heart_of_ruin))++control;
        if(chosen.size()>=2&&control>=2)order.insert(order.begin(),D::marcella);}
    if(!rows)for(auto e:{D::varg,D::tavi,D::vendetta,D::ryth,D::willow,D::prism,D::marcella,D::heart_of_ruin,D::stellar,D::vesper_vale,D::ren,D::cassi_and_issac})order.push_back(e);
    for(auto pick:order)if(std::find(chosen.begin(),chosen.end(),pick)==chosen.end()){bc::draft::pick(pick);return;}
    throw std::runtime_error("draft has no legal pick");
}
