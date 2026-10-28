// Native equivalents of benchmark_current.py, smoke_current_maps.py and analyze_camstats.py.
#include "process.h"
#include "summary_names.h"
#include "vendor/json.hpp"
#include <algorithm>
#include <iostream>
#include <regex>
#include <set>
#include <sstream>
using Json=nlohmann::json;
struct Args{
    fs::path root=fs::current_path(),directory,output;
    std::string command,bot="my-bot-cpp",opponent="python-reference",label="cpp-benchmark",team;
    int rounds=30;std::vector<std::string> maps;
};
inline double number(const Json& v){return v.is_string()?std::stod(v.get<std::string>()):v.get<double>();}
Json load(const fs::path& p){return Json::parse(read_text(p));}
void save(const fs::path& p,const Json& j){write_text(p,j.dump(2));}
bool component(const std::string& v){return !v.empty()&&std::regex_match(v,std::regex("[A-Za-z0-9_.-]+"))&&v!="."&&v!="..";}
Args parse(int argc,char** argv){
    Args a;if(argc<2)return a;a.command=argv[1];
    for(int i=2;i<argc;++i){std::string key=argv[i];auto next=[&](){if(++i>=argc)throw std::runtime_error("missing value for "+key);return std::string(argv[i]);};
        if(key=="--root")a.root=fs::absolute(fs::u8path(next()));else if(key=="--bot")a.bot=next();else if(key=="--opponent")a.opponent=next();
        else if(key=="--label")a.label=next();else if(key=="--rounds")a.rounds=std::stoi(next());else if(key=="--team-id")a.team=next();
        else if(key=="--directory"||key=="--map-dir")a.directory=fs::absolute(fs::u8path(next()));else if(key=="--output")a.output=fs::absolute(fs::u8path(next()));
        else if(key=="--maps"){while(i+1<argc&&std::string(argv[i+1]).rfind("--",0)!=0)a.maps.emplace_back(argv[++i]);}
        else throw std::runtime_error("unknown option "+key);
    }
    if(!component(a.bot)||!component(a.opponent)||!component(a.label)||a.rounds<1)throw std::runtime_error("invalid bot, opponent, label or rounds");return a;
}
std::vector<fs::path> maps(const Args& a){
    auto dir=a.directory.empty()?a.root/"maps":a.directory;std::vector<fs::path> out;
    if(!a.maps.empty()){for(auto name:a.maps){if(!component(name))throw std::runtime_error("invalid map name");auto p=dir/name;if(p.extension()!=".map26a")p+=L".map26a";out.push_back(p);}}
    else if(a.directory.empty()&&fs::exists(a.root/".cambc/map-pool.json")){auto manifest=load(a.root/".cambc/map-pool.json");for(auto& m:manifest["maps"]){std::string name=m["file"];if(!component(name))throw std::runtime_error("unsafe manifest filename");out.push_back(dir/name);}}
    else {for(auto p:fs::directory_iterator(dir))if(p.path().extension()==".map26a")out.push_back(p.path());std::sort(out.begin(),out.end());}
    if(out.empty())throw std::runtime_error("no maps selected");for(auto& p:out)if(!fs::is_regular_file(p))throw std::runtime_error("map missing: "+p.string());return out;
}
Json replay_logs(const fs::path& replay,const fs::path& dir){
    auto script=dir/"read-replay.ps1",output=dir/"replay-stdout.json",log=dir/"read-replay.log";
    write_text(script,R"PS(param([string]$Replay,[string]$Output)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive=[IO.Compression.ZipFile]::OpenRead($Replay)
try {
 $result=@{}
 foreach($name in @('team-a.stdout','team-b.stdout')) {
  $entry=$archive.GetEntry($name)
  if($null -eq $entry) {throw "Missing replay stdout: $name"}
  $reader=[IO.StreamReader]::new($entry.Open(),[Text.Encoding]::UTF8)
  try {$result[$name]=$reader.ReadToEnd()} finally {$reader.Dispose()}
 }
 [IO.File]::WriteAllText($Output,($result|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
} finally {$archive.Dispose()}
)PS");
    if(run_process(powershell(),{L"-NoProfile",L"-NonInteractive",L"-ExecutionPolicy",L"Bypass",L"-File",script.wstring(),L"-Replay",replay.wstring(),L"-Output",output.wstring()},dir,log,60))throw std::runtime_error("replay stdout extraction failed: "+log.string());return load(output);
}
int occurrences(const std::string& s,const std::string& needle){int n=0;std::size_t start=0;while((start=s.find(needle,start))!=std::string::npos){++n;start+=needle.size();}return n;}
fs::path replay_path(const std::string& text,const fs::path& root){
    std::regex pattern("replay bundle: ([^\\r\\n]+)",std::regex::icase);std::smatch match;if(!std::regex_search(text,match,pattern))throw std::runtime_error("runner did not report a replay bundle");auto p=fs::u8path(match[1].str());return p.is_absolute()?p:root/p;
}
Json match_metrics(const Json& data,const std::string& key){
    Json out;auto metric=[&](const std::string& name){double n=0;for(auto& c:data["champions"])if(c["team"]==key)n+=number(c["metrics"].at(name));return n;};
    std::map<std::string,std::vector<Json>> entries;for(auto& e:data["events"])if(e.contains("owner")&&e["owner"].is_object()&&e["owner"].value("team","")==key)for(auto& v:e["entries"])entries[e["kind"].get<std::string>()].push_back(v);
    out["win"]=data["match"]["outcome"]==key;out["rounds"]=data["match"]["roundsCompleted"];out["engine"]=data["match"]["engineVersion"];out["gems"]=metric("submittedGems");
    for(auto& t:data["teams"])if(t["team"]!=key)out["opponent_gems"]=number(t["submittedGems"]);
    out["collected"]=metric("collectedGems");out["deaths"]=metric("deaths");double loss=0;for(auto& v:entries["gemLoss"])loss+=number(v["value"]);out["lost"]=loss;
    int camps=0,pvp=0;for(auto& v:entries["death"]){camps+=v["context"]=="camp";pvp+=v["context"]=="champion";}out["camp_deaths"]=camps;out["pvp_deaths"]=pvp;
    out["hard_fuel"]=entries["fuelExhausted"].size();out["faults"]=data["diagnostics"]["botFaults"][key];
    for(auto [kind,field]:{std::pair("gemCollection","first_gem"),std::pair("gemSubmission","first_deposit")}){
        Json first=nullptr;for(auto& v:entries[kind])if(number(v["value"])>0&& (first.is_null()||v["timestamp"]["round"]<first))first=v["timestamp"]["round"];out[field]=first;
    }
    std::string picks;for(auto& d:data["roster"]["draft"])if(d["team"]==key){if(!picks.empty())picks+=';';picks+=d["champion"].get<std::string>();}out["picks"]=picks;return out;
}
void csv(const fs::path& p,const Json& rows){
    const std::vector<std::string> keys={"map","side","win","rounds","engine","gems","opponent_gems","collected","lost","deaths","camp_deaths","pvp_deaths","hard_fuel","faults","errors","first_gem","first_deposit","picks"};
    std::ostringstream text;for(std::size_t i=0;i<keys.size();++i)text<<(i?",":"")<<keys[i];text<<'\n';
    for(auto& r:rows){for(std::size_t i=0;i<keys.size();++i){if(i)text<<',';auto v=r.value(keys[i],Json());if(v.is_string()){auto s=v.get<std::string>();std::string escaped;for(auto c:s){escaped+=c;if(c=='"')escaped+='"';}text<<'"'<<escaped<<'"';}else if(v.is_boolean())text<<(v.get<bool>()?"True":"False");else if(!v.is_null())text<<v.dump();}text<<'\n';}write_text(p,text.str());
}
void benchmark(const Args& a){
    auto out=a.root/"replays"/a.label;fs::create_directories(out);Json rows=Json::array();
    for(auto& map:maps(a))for(int side=0;side<2;++side){
        auto prefix=out/(map.stem().string()+"-"+std::to_string(side));auto stats=prefix;stats+=L".json";auto log=prefix;log+=L".log";
        std::vector<std::wstring> args={L"run",widen(side?a.opponent:a.bot),widen(side?a.bot:a.opponent),L"--map",map.wstring(),L"--release",L"--statistics",stats.wstring(),L"--json",L"--out-dir",out.wstring()};
        if(run_process(a.root/"tools/cambc.exe",args,a.root,log))throw std::runtime_error("match failed or timed out: "+log.string());
        auto row=match_metrics(load(stats),side?"teamB":"teamA");auto logs=replay_logs(replay_path(read_text(log),a.root),out/(map.stem().string()+"-"+std::to_string(side)+"-stdout"));
        row["map"]=map.stem().string();row["side"]=side?"B":"A";row["errors"]=occurrences(logs[side?"team-b.stdout":"team-a.stdout"].get<std::string>(),"bot error:");
        rows.push_back(row);save(out/"results.json",rows);csv(out/"results.csv",rows);std::cout<<row.dump()<<std::endl;
    }int wins=0;for(auto& row:rows)wins+=row["win"].get<bool>();std::cout<<"Wins "<<wins<<" / "<<rows.size()<<std::endl;
}
int smoke(const Args& a){
    auto out=a.root/"replays"/a.label;fs::create_directories(out);Json rows=Json::array();int failures=0;
    for(auto& map:maps(a)){
        auto dir=out/map.stem();fs::create_directories(dir);Json row={{"map",map.stem().string()},{"errors",Json::array()}};
        try{
            auto code=run_process(a.root/"tools/cambc.exe",{L"run",widen(a.bot),widen(a.opponent),L"--map",map.wstring(),L"--rounds",std::to_wstring(a.rounds),L"--release",L"--out-dir",dir.wstring()},a.root,dir/"run.log",240);
            row["returncode"]=code;if(code)throw std::runtime_error(code==124?"timeout":"runner failure");
            auto logs=replay_logs(replay_path(read_text(dir/"run.log"),a.root),dir);
            auto count=occurrences(logs["team-a.stdout"].get<std::string>(),"bot error:");if(count)row["errors"].push_back(std::to_string(count)+" caught bot errors");
            row["profile"]=nullptr;auto other=logs["team-b.stdout"].get<std::string>();other.erase(std::remove(other.begin(),other.end(),'\0'),other.end());auto start=other.find("CATALOGUE ");
            if(start!=std::string::npos){auto end=other.find_first_of("\r\n",start);row["profile"]=Json::parse(other.substr(start+10,end==std::string::npos?end:end-start-10));}
            if(a.opponent=="sdk4-map-probe-cpp"&&(row["profile"].is_null()||occurrences(other,"probe error:")))throw std::runtime_error("map probe did not produce a valid profile");
        }catch(const std::exception& e){row["errors"].push_back(e.what());}
        bool failed=!row["errors"].empty();failures+=failed;rows.push_back(row);save(out/"results.json",rows);std::cout<<(failed?"FAIL ":"PASS ")<<map.stem().string()<<std::endl;
    }std::cout<<"Complete "<<rows.size()<<" failed "<<failures<<std::endl;return failures?1:0;
}
Json summarize(const Json& d,const std::string& name,const std::string& side){
    const auto identity = summaries::parse(name);
    Json champs=Json::array();for(auto c:d["champions"])if(c["team"]==side)champs.push_back(c);
    Json metrics;for(auto key:{"earnedGold","spentGold","collectedGems","submittedGems","gems","deaths","kills","championDamageDone","monsterDamageDone"}){double n=0;for(auto& c:champs)if(c["metrics"].contains(key))n+=number(c["metrics"][key]);metrics[key]=n;}
    double loss=0;int camp_deaths=0,pvp_deaths=0,fuel=0;Json deposits=Json::array(),first_deposit=nullptr,first_gem=nullptr;
    for(auto& e:d["events"])if(e.contains("owner")&&e["owner"].is_object()&&e["owner"].value("team","")==side){
        std::string kind=e["kind"];if(kind=="fuelExhausted")fuel+=e["entries"].size();
        for(auto& v:e["entries"]){
            if(kind=="gemLoss")loss+=number(v["value"]);
            if(kind=="death"){camp_deaths+=v["context"]=="camp";pvp_deaths+=v["context"]=="champion";}
            if((kind=="gemCollection"||kind=="gemSubmission")&&number(v["value"])>0){auto& first=kind=="gemCollection"?first_gem:first_deposit;if(first.is_null()||v["timestamp"]["round"]<first)first=v["timestamp"]["round"];if(kind=="gemSubmission")deposits.push_back(int(number(v["value"])));}
        }
    }
    double deposited=0;for(auto& v:deposits)deposited+=number(v);
    if(loss!=number(metrics["collectedGems"])-number(metrics["submittedGems"])-number(metrics["gems"])||number(metrics["deaths"])!=camp_deaths+pvp_deaths||deposited!=number(metrics["submittedGems"]))throw std::runtime_error("summary conservation check failed: "+name+" "+side);
    return {{"match",identity.match},{"team_id",side=="teamA"?identity.team_a:identity.team_b},{"side",side},{"width",d["match"]["width"]},{"height",d["match"]["height"]},{"map_hash",d["match"]["mapHash"]},{"engine",d["match"]["engineVersion"]},{"rounds",d["match"]["roundsCompleted"]},{"win",d["match"]["outcome"]==side},{"metrics",metrics},{"lost_gems",loss},{"camp_deaths",camp_deaths},{"pvp_deaths",pvp_deaths},{"fuel_exhaustions",fuel},{"first_gem",first_gem},{"first_deposit",first_deposit},{"deposit_sizes",deposits},{"champions",champs}};
}
Json rollup(const Json& rows){
    int wins=0;for(auto& r:rows)wins+=r["win"].get<bool>();Json out={{"team_observations",rows.size()},{"wins",wins}};
    for(auto key:{"earnedGold","spentGold","collectedGems","submittedGems","gems","deaths","kills"}){double n=0;for(auto& r:rows)n+=number(r["metrics"][key]);out[key]=n;}
    for(auto key:{"lost_gems","camp_deaths","pvp_deaths","fuel_exhaustions"}){double n=0;for(auto& r:rows)n+=number(r[key]);out[key]=n;}
    double acquired=number(out["collectedGems"]);out["deposited_fraction"]=acquired?Json(number(out["submittedGems"])/acquired):Json();return out;
}
void analyze(const Args& a){
    if(a.directory.empty()||a.output.empty()||a.team.empty())throw std::runtime_error("analyze requires --directory --team-id --output");
    std::vector<fs::path> files;for(auto p:fs::directory_iterator(a.directory))if(p.path().extension()==".json"&&summaries::has_known_prefix(p.path().filename().string()))files.push_back(p.path());std::sort(files.begin(),files.end());if(files.empty())throw std::runtime_error("no ranked, unranked or tournament JSON summaries found");
    Json rows=Json::array(),own=Json::array(),winners=Json::array(),losers=Json::array();std::set<std::string> teams;
    for(auto& p:files){auto d=load(p);if(!d["diagnostics"]["detailedCaptureComplete"].get<bool>())throw std::runtime_error("incomplete event capture: "+p.string());for(auto side:{"teamA","teamB"}){
        auto r=summarize(d,p.stem().string(),side);rows.push_back(r);teams.insert(r["team_id"]);if(r["team_id"]==a.team)own.push_back(r);else if(r["win"].get<bool>())winners.push_back(r);else losers.push_back(r);}}
    Json out={{"match_count",files.size()},{"unique_teams",teams.size()},{"own",rollup(own)},{"other_winners",rollup(winners)},{"other_losers",rollup(losers)},{"results",rows}};save(a.output,out);out.erase("results");std::cout<<out.dump(2)<<std::endl;
}
int main(int argc,char** argv){try{auto a=parse(argc,argv);if(a.command=="benchmark")benchmark(a);else if(a.command=="smoke")return smoke(a);else if(a.command=="analyze")analyze(a);else{std::cout<<"cam-tools benchmark|smoke|analyze [--root DIR] [--bot NAME] [--opponent NAME] [--maps STEM ...] [--label NAME]\nsmoke: --rounds N; analyze: --directory DIR --team-id UUID --output FILE\n";return a.command.empty()?0:1;}return 0;}catch(const std::exception& e){std::cerr<<"error: "<<e.what()<<std::endl;return 1;}}
