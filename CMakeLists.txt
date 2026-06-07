cmake_minimum_required(VERSION 3.10)
project(langtons_ant_sequential LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(langton src/main.cpp)
