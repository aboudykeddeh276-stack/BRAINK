#pragma once

#include "kernel_types.hpp"

namespace keddeh::kernel::volume {

inline constexpr u64 tensor_dimension = 8U;
inline constexpr u64 tensor_cell_count = tensor_dimension * tensor_dimension * tensor_dimension;
inline constexpr u64 prime_x = 97U;
inline constexpr u64 prime_y = 199U;
inline constexpr u64 prime_z = 401U;
inline constexpr u64 modulo_space = 823U;
inline constexpr u64 entropy_step = 1667U;

struct TensorCoordinate final {
    u64 x;
    u64 y;
    u64 z;

    [[nodiscard]] constexpr bool valid() const noexcept {
        return x < tensor_dimension && y < tensor_dimension && z < tensor_dimension;
    }
};

struct TensorCell final {
    TensorCoordinate coordinate;
    u64 canonical_slot;
    u64 route_residue;
    uptr route_candidate_address;
};

enum class BackingPath : u8 {
    path_a_physical = 1U,
    path_b_persistent = 2U,
    path_c_software = 3U,
};

enum class BackingKind : u8 {
    physical_frame = 1U,
    device_mmio = 2U,
    persistent_volume = 3U,
    file_backed_storage = 4U,
    workbook_cells = 5U,
    browser_buffer = 6U,
    vm_memory = 7U,
    simulated_memory = 8U,
    software_memory = 9U,
};

struct BackingAvailability final {
    bool physical_frame;
    bool device_mmio;
    bool persistent_volume;
    bool file_backed_storage;
    bool workbook_cells;
    bool browser_buffer;
    bool vm_memory;
    bool simulated_memory;
    bool software_memory;
};

struct BackingBases final {
    uptr physical_frame;
    uptr device_mmio;
    uptr persistent_volume;
    uptr file_backed_storage;
    uptr workbook_cells;
    uptr browser_buffer;
    uptr vm_memory;
    uptr simulated_memory;
    uptr software_memory;
};

struct VolumeBinding final {
    TensorCell cell;
    BackingPath path;
    BackingKind kind;
    uptr backing_address;
};

class PrimeTensorVolume final {
public:
    constexpr explicit PrimeTensorVolume(const uptr route_base,
                                         const BackingBases backing_bases) noexcept
        : occupancy_{}, route_base_(route_base), backing_bases_(backing_bases) {}

    [[nodiscard]] static constexpr u64 canonical_slot(const TensorCoordinate coordinate) noexcept {
        return (coordinate.x * tensor_dimension * tensor_dimension)
             + (coordinate.y * tensor_dimension)
             + coordinate.z;
    }

    [[nodiscard]] static constexpr TensorCoordinate coordinate_from_slot(const u64 slot) noexcept {
        return TensorCoordinate{
            slot / (tensor_dimension * tensor_dimension),
            (slot / tensor_dimension) % tensor_dimension,
            slot % tensor_dimension,
        };
    }

    [[nodiscard]] static constexpr u64 route_residue(const TensorCoordinate coordinate) noexcept {
        return ((coordinate.x * prime_x)
              + (coordinate.y * prime_y)
              + (coordinate.z * prime_z)) % modulo_space;
    }

    [[nodiscard]] constexpr TensorCell describe(const TensorCoordinate coordinate) const noexcept {
        const u64 slot = canonical_slot(coordinate);
        const u64 residue = route_residue(coordinate);
        return TensorCell{
            coordinate,
            slot,
            residue,
            route_base_ + static_cast<uptr>(residue * entropy_step * page_size),
        };
    }

    [[nodiscard]] Expected<TensorCell> allocate() noexcept {
        for (u64 traversal = 0U; traversal < tensor_cell_count; ++traversal) {
            const u64 slot = permuted_slot(traversal);
            if (!occupied(slot)) {
                set_occupied(slot, true);
                return Expected<TensorCell>::success(describe(coordinate_from_slot(slot)));
            }
        }
        return Expected<TensorCell>::failure(ErrorCode::out_of_memory);
    }

    [[nodiscard]] Expected<void> release(const TensorCoordinate coordinate) noexcept {
        if (!coordinate.valid()) {
            return Expected<void>::failure(ErrorCode::invalid_argument);
        }
        const u64 slot = canonical_slot(coordinate);
        if (!occupied(slot)) {
            return Expected<void>::failure(ErrorCode::invalid_state);
        }
        set_occupied(slot, false);
        return Expected<void>::success();
    }

    [[nodiscard]] Expected<VolumeBinding> bind(const TensorCell& cell,
                                               const BackingAvailability availability) const noexcept {
        if (!cell.coordinate.valid() || cell.canonical_slot >= tensor_cell_count) {
            return Expected<VolumeBinding>::failure(ErrorCode::invalid_argument);
        }

        // Deterministic path A: physical projections. Physical backing is a consumer,
        // never the definition of the tensor volume.
        if (availability.physical_frame) {
            return success_binding(cell, BackingPath::path_a_physical,
                                   BackingKind::physical_frame,
                                   backing_bases_.physical_frame);
        }
        if (availability.device_mmio) {
            return success_binding(cell, BackingPath::path_a_physical,
                                   BackingKind::device_mmio,
                                   backing_bases_.device_mmio);
        }

        // Deterministic path B: durable or externally projected storage surfaces.
        if (availability.persistent_volume) {
            return success_binding(cell, BackingPath::path_b_persistent,
                                   BackingKind::persistent_volume,
                                   backing_bases_.persistent_volume);
        }
        if (availability.file_backed_storage) {
            return success_binding(cell, BackingPath::path_b_persistent,
                                   BackingKind::file_backed_storage,
                                   backing_bases_.file_backed_storage);
        }
        if (availability.workbook_cells) {
            return success_binding(cell, BackingPath::path_b_persistent,
                                   BackingKind::workbook_cells,
                                   backing_bases_.workbook_cells);
        }
        if (availability.browser_buffer) {
            return success_binding(cell, BackingPath::path_b_persistent,
                                   BackingKind::browser_buffer,
                                   backing_bases_.browser_buffer);
        }

        // Deterministic path C: volatile software execution surfaces.
        if (availability.vm_memory) {
            return success_binding(cell, BackingPath::path_c_software,
                                   BackingKind::vm_memory,
                                   backing_bases_.vm_memory);
        }
        if (availability.simulated_memory) {
            return success_binding(cell, BackingPath::path_c_software,
                                   BackingKind::simulated_memory,
                                   backing_bases_.simulated_memory);
        }
        if (availability.software_memory) {
            return success_binding(cell, BackingPath::path_c_software,
                                   BackingKind::software_memory,
                                   backing_bases_.software_memory);
        }

        return Expected<VolumeBinding>::failure(ErrorCode::invalid_state);
    }

    [[nodiscard]] constexpr bool occupied(const u64 slot) const noexcept {
        if (slot >= tensor_cell_count) {
            return false;
        }
        const u64 word = slot / 64U;
        const u64 bit = slot % 64U;
        return (occupancy_[word] & (1ULL << bit)) != 0U;
    }

private:
    [[nodiscard]] static constexpr u64 permuted_slot(const u64 traversal) noexcept {
        const TensorCoordinate source = coordinate_from_slot(traversal);
        const TensorCoordinate permuted{
            (source.x * prime_x) % tensor_dimension,
            (source.y * prime_y) % tensor_dimension,
            (source.z * prime_z) % tensor_dimension,
        };
        return canonical_slot(permuted);
    }

    constexpr void set_occupied(const u64 slot, const bool value) noexcept {
        const u64 word = slot / 64U;
        const u64 bit = slot % 64U;
        const u64 mask = 1ULL << bit;
        if (value) {
            occupancy_[word] |= mask;
        } else {
            occupancy_[word] &= ~mask;
        }
    }

    [[nodiscard]] static constexpr VolumeBinding binding_for(const TensorCell& cell,
                                                              const BackingPath path,
                                                              const BackingKind kind,
                                                              const uptr base) noexcept {
        return VolumeBinding{
            cell,
            path,
            kind,
            base + static_cast<uptr>(cell.canonical_slot * page_size),
        };
    }

    [[nodiscard]] static constexpr Expected<VolumeBinding> success_binding(
        const TensorCell& cell,
        const BackingPath path,
        const BackingKind kind,
        const uptr base) noexcept {
        return Expected<VolumeBinding>::success(binding_for(cell, path, kind, base));
    }

    u64 occupancy_[tensor_cell_count / 64U];
    uptr route_base_;
    BackingBases backing_bases_;
};

static_assert(tensor_cell_count == 512U);
static_assert(sizeof(TensorCoordinate) == 24U);
static_assert(sizeof(TensorCell) == 48U);
static_assert(PrimeTensorVolume::canonical_slot(TensorCoordinate{7U, 7U, 7U}) == 511U);
static_assert(PrimeTensorVolume::coordinate_from_slot(511U).x == 7U);
static_assert(PrimeTensorVolume::coordinate_from_slot(511U).y == 7U);
static_assert(PrimeTensorVolume::coordinate_from_slot(511U).z == 7U);

}  // namespace keddeh::kernel::volume
