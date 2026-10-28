#include "controller.h"
int main(){Bot bot;while(true){try{if(bc::is_draft())play_draft();else bot.play_turn();}catch(const TurnBudget&){}catch(const std::exception& e){std::cout<<"bot error: "<<e.what()<<std::endl;}catch(...){std::cout<<"bot error: unknown exception"<<std::endl;}bc::end_turn();}}
