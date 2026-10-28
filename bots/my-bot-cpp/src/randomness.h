#pragma once
#include "controller.h"
inline std::uint64_t below(std::uint64_t limit){
    static std::optional<strategy::Random> random;
    if(!random){auto p=bc::map::spawn_region(T::ally).positions().front();std::uint64_t seed=std::uint64_t(p.x)*73856093^std::uint64_t(p.y)*19349663;
        if(!bc::is_draft()){auto start=bc::self().position();seed^=std::uint64_t(start.x)*83492791^std::uint64_t(start.y)*2654435761ULL;}random.emplace(seed);}
    return random->below(limit);
}
