#pragma once
#define NOMINMAX
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <stdexcept>
namespace fs=std::filesystem;
inline std::wstring quote_argument(const std::wstring& arg){
    std::wstring out=L"\"";unsigned slashes=0;
    for(wchar_t c:arg){if(c==L'\\'){++slashes;continue;}if(c==L'\"'){out.append(slashes*2+1,L'\\');out+=c;}else{out.append(slashes,L'\\');out+=c;}slashes=0;}
    out.append(slashes*2,L'\\');return out+L"\"";
}
inline std::wstring widen(const std::string& text){
    if(text.empty())return {};int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text.data(),text.size(),nullptr,0);if(!n)throw std::runtime_error("invalid UTF-8 argument");std::wstring w(n,L'\0');MultiByteToWideChar(CP_UTF8,0,text.data(),text.size(),w.data(),n);return w;
}
inline int run_process(const fs::path& executable,const std::vector<std::wstring>& args,const fs::path& cwd,const fs::path& log,unsigned seconds=1200){
    fs::create_directories(log.parent_path());SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE};
    HANDLE output=CreateFileW(log.c_str(),GENERIC_WRITE,FILE_SHARE_READ,&security,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(output==INVALID_HANDLE_VALUE)throw std::runtime_error("cannot create process log");
    std::wstring command=quote_argument(executable.wstring());for(auto& a:args)command+=L" "+quote_argument(a);
    STARTUPINFOW startup{};startup.cb=sizeof(startup);startup.dwFlags=STARTF_USESTDHANDLES;startup.hStdOutput=output;startup.hStdError=output;startup.hStdInput=GetStdHandle(STD_INPUT_HANDLE);
    PROCESS_INFORMATION process{};HANDLE job=CreateJobObjectW(nullptr,nullptr);JOBOBJECT_EXTENDED_LIMIT_INFORMATION limit{};limit.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if(!job||!SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limit,sizeof(limit))){CloseHandle(output);if(job)CloseHandle(job);throw std::runtime_error("cannot create child process job");}
    if(!CreateProcessW(executable.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED,nullptr,cwd.c_str(),&startup,&process)){CloseHandle(output);CloseHandle(job);throw std::runtime_error("cannot start child process: "+std::to_string(GetLastError()));}
    if(!AssignProcessToJobObject(job,process.hProcess)){TerminateProcess(process.hProcess,1);CloseHandle(process.hThread);CloseHandle(process.hProcess);CloseHandle(output);CloseHandle(job);throw std::runtime_error("cannot contain child process");}
    ResumeThread(process.hThread);CloseHandle(process.hThread);CloseHandle(output);
    auto wait=WaitForSingleObject(process.hProcess,seconds*1000);DWORD code=0;
    if(wait==WAIT_TIMEOUT){TerminateJobObject(job,124);WaitForSingleObject(process.hProcess,10000);code=124;}else if(wait!=WAIT_OBJECT_0)code=125;else GetExitCodeProcess(process.hProcess,&code);
    CloseHandle(process.hProcess);CloseHandle(job);return int(code);
}
inline std::string read_text(const fs::path& p){std::ifstream file(p,std::ios::binary);if(!file)throw std::runtime_error("cannot read "+p.string());return {std::istreambuf_iterator<char>(file),{}};}
inline void write_text(const fs::path& p,const std::string& text){fs::create_directories(p.parent_path());std::ofstream file(p,std::ios::binary);if(!file)throw std::runtime_error("cannot write "+p.string());file<<text;}
inline fs::path powershell(){wchar_t system[MAX_PATH];GetSystemDirectoryW(system,MAX_PATH);return fs::path(system)/L"WindowsPowerShell/v1.0/powershell.exe";}
