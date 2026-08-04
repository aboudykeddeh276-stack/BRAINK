#include "prime_tensor_volume.hpp"

using namespace keddeh::kernel;
using namespace keddeh::kernel::volume;

constexpr bool compile_contract() {
    PrimeTensorVolume volume{
        0x0000000002000000ULL,
        0x0000000040000000ULL,
        0x0000000080000000ULL,
        0x00000000C0000000ULL,
    };

    const TensorCoordinate coordinate{1U, 2U, 3U};
    const TensorCell cell = volume.describe(coordinate);
    if (cell.canonical_slot != 83U) {
        return false;
    }
    if (!is_page_aligned(cell.route_candidate_address)) {
        return false;
    }

    const auto binding = volume.bind(cell, BackingAvailability{false, false, true});
    if (!binding.has_value()) {
        return false;
    }
    return binding.value().path == BackingPath::path_c_software
        && binding.value().backing_address == (0x00000000C0000000ULL + (83U * page_size));
}

static_assert(compile_contract());

int main() {
    PrimeTensorVolume volume{
        0x0000000002000000ULL,
        0x0000000040000000ULL,
        0x0000000080000000ULL,
        0x00000000C0000000ULL,
    };

    const auto allocated = volume.allocate();
    if (!allocated.has_value()) {
        return 1;
    }
    const auto binding = volume.bind(
        allocated.value(),
        BackingAvailability{false, true, true});
    if (!binding.has_value() || binding.value().path != BackingPath::path_b_persistent) {
        return 2;
    }
    const auto released = volume.release(allocated.value().coordinate);
    return released.has_value() ? 0 : 3;
}
