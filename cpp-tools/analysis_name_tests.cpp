#include "summary_names.h"
#include <iostream>

int main() {
    int checks = 0;
    auto check = [&](bool value) {
        ++checks;
        if (!value) throw std::runtime_error("summary filename contract failed");
    };
    for (const auto& kind : {"ranked", "unranked", "tournament"}) {
        const std::string name = std::string(kind) + "_match_teamA_vs_teamB";
        check(summaries::has_known_prefix(name + ".json"));
        auto id = summaries::parse(name);
        check(id.kind == kind && id.match == "match" && id.team_a == "teamA" && id.team_b == "teamB");
    }
    for (const auto& name : {"analysis.json", "results.json", "notes_ranked_match_A_vs_B", "rankedmatch_A_vs_B"})
        check(!summaries::has_known_prefix(name));
    for (const auto& name : {"ranked_match_teamA_to_teamB", "ranked__teamA_vs_teamB", "unranked_match_teamA_vs_", "unknown_match_teamA_vs_teamB"}) {
        bool rejected = false;
        try { summaries::parse(name); } catch (const std::invalid_argument&) { rejected = true; }
        check(rejected);
    }
    std::cout << "PASS " << checks << " summary filename checks\n";
}
