#include "kernel_types.hpp"

using keddeh::kernel::ErrorCode;
using keddeh::kernel::Expected;
using keddeh::kernel::SpinlockStorage;
using keddeh::kernel::u64;

namespace {

constexpr Expected<u64> successful_value() noexcept {
    return Expected<u64>::success(0x1234ULL);
}

constexpr Expected<u64> failed_value() noexcept {
    return Expected<u64>::failure(ErrorCode::invalid_state);
}

constexpr auto good = successful_value();
constexpr auto bad = failed_value();

static_assert(good.has_value());
static_assert(good.value() == 0x1234ULL);
static_assert(!bad.has_value());
static_assert(bad.error() == ErrorCode::invalid_state);
static_assert(sizeof(SpinlockStorage) == 64U);

}  // namespace

extern "C" void kernel_types_compile_anchor() noexcept {
    SpinlockStorage lock{1U, {}};
    (void)lock;
}
