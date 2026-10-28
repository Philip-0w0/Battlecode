#pragma once
#include <array>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace summaries {
inline bool known_kind(const std::string& kind) {
    return kind == "ranked" || kind == "unranked" || kind == "tournament";
}
inline bool has_known_prefix(const std::string& filename) {
    const auto end = filename.find('_');
    return end != std::string::npos && known_kind(filename.substr(0, end));
}
struct Identity {
    std::string kind, match, team_a, team_b;
};
inline Identity parse(const std::string& stem) {
    std::vector<std::string> parts;
    std::stringstream input(stem);
    std::string part;
    while (std::getline(input, part, '_')) parts.push_back(part);
    if (parts.size() != 5 || !known_kind(parts[0]) || parts[3] != "vs" ||
        parts[1].empty() || parts[2].empty() || parts[4].empty())
        throw std::invalid_argument("unexpected match summary filename: " + stem);
    return {parts[0], parts[1], parts[2], parts[4]};
}
}
