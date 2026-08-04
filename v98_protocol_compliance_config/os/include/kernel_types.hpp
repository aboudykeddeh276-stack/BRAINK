#pragma once

#include <stddef.h>
#include <stdint.h>

namespace keddeh::kernel {

using u8 = uint8_t;
using u16 = uint16_t;
using u32 = uint32_t;
using u64 = uint64_t;
using i8 = int8_t;
using i16 = int16_t;
using i32 = int32_t;
using i64 = int64_t;
using usize = size_t;
using uptr = uintptr_t;

inline constexpr usize page_size = 4096U;
inline constexpr usize cache_line_size = 64U;
inline constexpr uptr kernel_virtual_base = 0xFFFFFFFF80000000ULL;
inline constexpr uptr kernel_physical_base = 0x00100000ULL;

static_assert(sizeof(u8) == 1U);
static_assert(sizeof(u16) == 2U);
static_assert(sizeof(u32) == 4U);
static_assert(sizeof(u64) == 8U);
static_assert(sizeof(uptr) == 8U);
static_assert(page_size == 4096U);
static_assert(cache_line_size == 64U);

enum class ErrorCode : u32 {
    none = 0x00000001U,
    invalid_argument = 0x00000002U,
    invalid_state = 0x00000003U,
    unsupported = 0x00000004U,
    out_of_memory = 0x00000005U,
    address_not_canonical = 0x00000006U,
    alignment_violation = 0x00000007U,
    permission_denied = 0x00000008U,
    hardware_fault = 0x00000009U,
    integrity_failure = 0x0000000AU,
};

struct alignas(cache_line_size) SpinlockStorage final {
    volatile u32 state;
    u8 reserved[cache_line_size - sizeof(u32)];
};

static_assert(sizeof(SpinlockStorage) == cache_line_size,
              "L1 Structural Invariant Broken: Spinlock cache geometry contaminated");
static_assert(alignof(SpinlockStorage) == cache_line_size,
              "L1 Structural Invariant Broken: Spinlock alignment contaminated");

template <typename T, typename E = ErrorCode>
class [[nodiscard]] Expected final {
    static_assert(__is_trivially_destructible(T),
                  "Early-kernel Expected<T,E> requires trivially destructible T");
    static_assert(__is_trivially_destructible(E),
                  "Early-kernel Expected<T,E> requires trivially destructible E");

public:
    static constexpr Expected success(const T& value) noexcept {
        return Expected(ValueTag{}, value);
    }

    static constexpr Expected failure(const E error) noexcept {
        return Expected(ErrorTag{}, error);
    }

    [[nodiscard]] constexpr bool has_value() const noexcept {
        return has_value_;
    }

    [[nodiscard]] constexpr explicit operator bool() const noexcept {
        return has_value();
    }

    [[nodiscard]] constexpr const T& value() const noexcept {
        return storage_.value;
    }

    [[nodiscard]] constexpr T& value() noexcept {
        return storage_.value;
    }

    [[nodiscard]] constexpr E error() const noexcept {
        return storage_.error;
    }

private:
    struct ValueTag final {};
    struct ErrorTag final {};

    union Storage {
        T value;
        E error;

        constexpr Storage(const T& input) noexcept : value(input) {}
        constexpr Storage(const E input) noexcept : error(input) {}
    };

    constexpr Expected(ValueTag, const T& value) noexcept
        : storage_(value), has_value_(true) {}

    constexpr Expected(ErrorTag, const E error) noexcept
        : storage_(error), has_value_(false) {}

    Storage storage_;
    bool has_value_;
};

template <typename E>
class [[nodiscard]] Expected<void, E> final {
public:
    static constexpr Expected success() noexcept {
        return Expected(true, E{});
    }

    static constexpr Expected failure(const E error) noexcept {
        return Expected(false, error);
    }

    [[nodiscard]] constexpr bool has_value() const noexcept {
        return has_value_;
    }

    [[nodiscard]] constexpr explicit operator bool() const noexcept {
        return has_value();
    }

    [[nodiscard]] constexpr E error() const noexcept {
        return error_;
    }

private:
    constexpr Expected(const bool has_value, const E error) noexcept
        : has_value_(has_value), error_(error) {}

    bool has_value_;
    E error_;
};

[[nodiscard]] constexpr bool is_page_aligned(const uptr address) noexcept {
    return (address & static_cast<uptr>(page_size - 1U)) == 0U;
}

[[nodiscard]] constexpr bool is_canonical_x86_64(const uptr address) noexcept {
    const uptr upper = address >> 48U;
    const bool sign = ((address >> 47U) & 1U) != 0U;
    return sign ? upper == 0xFFFFU : upper == 0U;
}

static_assert(is_page_aligned(kernel_virtual_base));
static_assert(is_page_aligned(kernel_physical_base));
static_assert(is_canonical_x86_64(kernel_virtual_base));

}  // namespace keddeh::kernel
