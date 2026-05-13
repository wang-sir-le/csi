# The following lines of boilerplate have to be in your project's CMakeLists
# in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.10)

if(NOT DEFINED ENV{IDF_PATH})
    set(IDF_POSSIBLE_PATHS
        "C:/esp/v6.0/esp-idf"
        "C:/esp-idf"
        "C:/Espressif/frameworks/esp-idf"
        "$ENV{USERPROFILE}/esp-idf"
        "$ENV{USERPROFILE}/esp/esp-idf"
        "$ENV{USERPROFILE}/.espressif/esp-idf"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../esp-idf"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../../esp-idf"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../../../esp-idf"
    )

    foreach(path IN LISTS IDF_POSSIBLE_PATHS)
        if(EXISTS "${path}/tools/cmake/project.cmake")
            set(ENV{IDF_PATH} "${path}")
            message(STATUS "Auto-detected IDF_PATH: ${path}")
            break()
        endif()
    endforeach()
endif()

if(NOT DEFINED ENV{IDF_PATH})
    message(FATAL_ERROR "IDF_PATH environment variable is not set.")
endif()

if(NOT EXISTS "$ENV{IDF_PATH}/tools/cmake/project.cmake")
    message(FATAL_ERROR "IDF_PATH ($ENV{IDF_PATH}) does not point to a valid ESP-IDF installation.")
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Generate compile_commands.json" FORCE)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(csi_send)

git_describe(PROJECT_VERSION ${CMAKE_CURRENT_SOURCE_DIR})
message("Project: ${PROJECT_NAME}, Commit: ${PROJECT_VERSION}")
