#include <jni.h>
#include <string>
#include <vector>
#include <android/log.h>

#define LOG_TAG "DtpAssistLlama"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

#if DTP_USE_LLAMA_CPP
#include "llama.h"

struct DtpLlamaHandle {
    llama_model * model = nullptr;
    llama_context * ctx = nullptr;
    llama_sampler * sampler = nullptr;
};

static std::string jstring_to_utf8(JNIEnv * env, jstring value) {
    const char * raw = env->GetStringUTFChars(value, nullptr);
    std::string out(raw == nullptr ? "" : raw);
    env->ReleaseStringUTFChars(value, raw);
    return out;
}

static jstring utf8_to_jstring(JNIEnv * env, const std::string & value) {
    return env->NewStringUTF(value.c_str());
}

extern "C" JNIEXPORT jlong JNICALL
Java_com_dtp_dtpassist_llm_LlamaNative_loadModel(
        JNIEnv * env,
        jobject,
        jstring model_path,
        jint context_size,
        jint threads) {
    llama_backend_init();

    auto * handle = new DtpLlamaHandle();
    const std::string path = jstring_to_utf8(env, model_path);

    llama_model_params model_params = llama_model_default_params();
    model_params.n_gpu_layers = 0;
    model_params.use_mmap = true;

    handle->model = llama_model_load_from_file(path.c_str(), model_params);
    if (handle->model == nullptr) {
        delete handle;
        LOGE("Failed to load model: %s", path.c_str());
        return 0;
    }

    llama_context_params ctx_params = llama_context_default_params();
    ctx_params.n_ctx = (uint32_t) context_size;
    ctx_params.n_batch = 512;
    ctx_params.n_threads = threads;
    ctx_params.n_threads_batch = threads;

    handle->ctx = llama_init_from_model(handle->model, ctx_params);
    if (handle->ctx == nullptr) {
        llama_model_free(handle->model);
        delete handle;
        LOGE("Failed to create llama context");
        return 0;
    }

    handle->sampler = llama_sampler_chain_init(llama_sampler_chain_default_params());
    llama_sampler_chain_add(handle->sampler, llama_sampler_init_top_k(40));
    llama_sampler_chain_add(handle->sampler, llama_sampler_init_top_p(0.90f, 1));
    llama_sampler_chain_add(handle->sampler, llama_sampler_init_temp(0.25f));
    llama_sampler_chain_add(handle->sampler, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));

    return reinterpret_cast<jlong>(handle);
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_dtp_dtpassist_llm_LlamaNative_generate(
        JNIEnv * env,
        jobject,
        jlong ptr,
        jstring prompt_text,
        jint max_tokens) {
    auto * handle = reinterpret_cast<DtpLlamaHandle *>(ptr);
    if (handle == nullptr || handle->ctx == nullptr || handle->model == nullptr) {
        return utf8_to_jstring(env, "");
    }

    const std::string prompt = jstring_to_utf8(env, prompt_text);
    const llama_vocab * vocab = llama_model_get_vocab(handle->model);

    llama_memory_clear(llama_get_memory(handle->ctx), true);
    llama_sampler_reset(handle->sampler);

    int n_prompt = -llama_tokenize(vocab, prompt.c_str(), (int32_t) prompt.size(), nullptr, 0, true, true);
    if (n_prompt <= 0) return utf8_to_jstring(env, "");

    std::vector<llama_token> tokens(n_prompt);
    llama_tokenize(vocab, prompt.c_str(), (int32_t) prompt.size(), tokens.data(), (int32_t) tokens.size(), true, true);

    llama_batch batch = llama_batch_get_one(tokens.data(), (int32_t) tokens.size());
    if (llama_decode(handle->ctx, batch) != 0) {
        return utf8_to_jstring(env, "");
    }

    std::string result;
    for (int i = 0; i < max_tokens; ++i) {
        llama_token token = llama_sampler_sample(handle->sampler, handle->ctx, -1);
        if (llama_vocab_is_eog(vocab, token)) break;

        char piece[256];
        int n = llama_token_to_piece(vocab, token, piece, sizeof(piece), 0, true);
        if (n > 0) result.append(piece, n);
        if (result.find("<|im_end|>") != std::string::npos ||
            result.find("<|endoftext|>") != std::string::npos ||
            result.find("\nUSER:") != std::string::npos ||
            result.find("\nSYSTEM:") != std::string::npos ||
            result.find("\nRETRIEVED_PDD_CONTEXT:") != std::string::npos) {
            break;
        }

        llama_batch next = llama_batch_get_one(&token, 1);
        if (llama_decode(handle->ctx, next) != 0) break;
    }

    return utf8_to_jstring(env, result);
}

extern "C" JNIEXPORT void JNICALL
Java_com_dtp_dtpassist_llm_LlamaNative_release(JNIEnv *, jobject, jlong ptr) {
    auto * handle = reinterpret_cast<DtpLlamaHandle *>(ptr);
    if (handle == nullptr) return;
    if (handle->sampler != nullptr) llama_sampler_free(handle->sampler);
    if (handle->ctx != nullptr) llama_free(handle->ctx);
    if (handle->model != nullptr) llama_model_free(handle->model);
    delete handle;
    llama_backend_free();
}

#else

extern "C" JNIEXPORT jlong JNICALL
Java_com_dtp_dtpassist_llm_LlamaNative_loadModel(JNIEnv *, jobject, jstring, jint, jint) {
    return 0;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_dtp_dtpassist_llm_LlamaNative_generate(JNIEnv * env, jobject, jlong, jstring, jint) {
    return env->NewStringUTF("");
}

extern "C" JNIEXPORT void JNICALL
Java_com_dtp_dtpassist_llm_LlamaNative_release(JNIEnv *, jobject, jlong) {
}

#endif
