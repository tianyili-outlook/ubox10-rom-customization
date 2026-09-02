#include <cassert>
#include <cstdint>

enum class Result { OK, NOT_SUPPORTED };
struct Port { int id; };
using Callback = int (*)(Port*);

struct Device {
    uint32_t version;
    Callback legacy;
    Callback v7;
};

static int legacy_calls;
static int v7_calls;
static int legacy_ok(Port*) { ++legacy_calls; return 0; }
static int v7_ok(Port*) { ++v7_calls; return 0; }

static Result get_audio_port(Device* device, Port* port) {
    if (device->version >= 0x0302) {
        if (device->v7 == nullptr) return Result::NOT_SUPPORTED;
        return device->v7(port) == 0 ? Result::OK : Result::NOT_SUPPORTED;
    }
    if (device->legacy == nullptr) return Result::NOT_SUPPORTED;
    return device->legacy(port) == 0 ? Result::OK : Result::NOT_SUPPORTED;
}

int main() {
    Port original{73};
    Device malformed{0x0700, legacy_ok, nullptr};
    assert(get_audio_port(&malformed, &original) == Result::NOT_SUPPORTED);
    assert(original.id == 73);
    assert(legacy_calls == 0 && v7_calls == 0);

    Device valid{0x0700, legacy_ok, v7_ok};
    assert(get_audio_port(&valid, &original) == Result::OK);
    assert(legacy_calls == 0 && v7_calls == 1);

    Device old{0x0301, legacy_ok, nullptr};
    assert(get_audio_port(&old, &original) == Result::OK);
    assert(legacy_calls == 1 && v7_calls == 1);
}
