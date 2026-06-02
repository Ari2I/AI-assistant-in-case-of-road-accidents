cmake_minimum_required(VERSION 3.22.1)
project(dtpassist_llama)

add_library(dtpassist_llama SHARED llama_jni.cpp)

target_compile_features(dtpassist_llama PRIVATE cxx_std_17)
target_link_libraries(dtpassist_llama android log)

if(DEFINED LLAMA_CPP_DIR AND NOT "${LLAMA_CPP_DIR}" STREQUAL "" AND EXISTS "${LLAMA_CPP_DIR}/CMakeLists.txt")
    message(STATUS "DtpAssist: building with llama.cpp from ${LLAMA_CPP_DIR}")

    set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
    set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
    set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
    set(GGML_OPENMP OFF CACHE BOOL "" FORCE)

    add_subdirectory("${LLAMA_CPP_DIR}" llama_cpp_build)
    target_compile_definitions(dtpassist_llama PRIVATE DTP_USE_LLAMA_CPP=1)
    target_include_directories(dtpassist_llama PRIVATE
        "${LLAMA_CPP_DIR}/include"
        "${LLAMA_CPP_DIR}/src"
        "${LLAMA_CPP_DIR}/ggml/include"
        "${LLAMA_CPP_DIR}/ggml/src"
    )
    target_link_libraries(dtpassist_llama llama)
else()
    message(STATUS "DtpAssist: LLAMA_CPP_DIR is empty. Building JNI stub.")
    target_compile_definitions(dtpassist_llama PRIVATE DTP_USE_LLAMA_CPP=0)
endif()
