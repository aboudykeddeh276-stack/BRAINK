#include "prime_tensor_volume.hpp"

using namespace keddeh::kernel;
using namespace keddeh::kernel::volume;

constexpr BackingBases bases() {
    return BackingBases{
        0x0000000040000000ULL,
        0x0000000050000000ULL,
        0x0000000060000000ULL,
        0x0000000070000000ULL,
        0x0000000080000000ULL,
        0x0000000090000000ULL,
        0x00000000A0000000ULL,
        0x00000000B0000000ULL,
        0x00000000C0000000ULL,
    };
}

constexpr bool compile_contract() {
    PrimeTensorVolume volume{0x0000000002000000ULL, bases()};

    const TensorCoordinate coordinate{1U, 2U, 3U};
    const TensorCell cell = volume.describe(coordinate);
    if (cell.canonical_slot != 83U) {
        return false;
    }
    if (!is_page_aligned(cell.route_candidate_address)) {
        return false;
    }

    const auto software_binding = volume.bind(
        cell,
        BackingAvailability{false, false, false, false, false, false, false, false, true});
    if (!software_binding.has_value()) {
        return false;
    }
    if (software_binding.value().path != BackingPath::path_c_software
        || software_binding.value().kind != BackingKind::software_memory
        || software_binding.value().backing_address
            != (0x00000000C0000000ULL + (83U * page_size))) {
        return false;
    }

    const auto workbook_binding = volume.bind(
        cell,
        BackingAvailability{false, false, false, false, true, false, true, true, true});
    if (!workbook_binding.has_value()) {
        return false;
    }
    return workbook_binding.value().path == BackingPath::path_b_persistent
        && workbook_binding.value().kind == BackingKind::workbook_cells
        && workbook_binding.value().cell.canonical_slot == cell.canonical_slot
        && workbook_binding.value().cell.route_residue == cell.route_residue;
}

static_assert(compile_contract());

int main() {
    PrimeTensorVolume volume{0x0000000002000000ULL, bases()};

    const auto allocated = volume.allocate();
    if (!allocated.has_value()) {
        return 1;
    }

    const auto mmio_binding = volume.bind(
        allocated.value(),
        BackingAvailability{false, true, true, true, true, true, true, true, true});
    if (!mmio_binding.has_value()
        || mmio_binding.value().path != BackingPath::path_a_physical
        || mmio_binding.value().kind != BackingKind::device_mmio) {
        return 2;
    }

    const auto file_binding = volume.bind(
        allocated.value(),
        BackingAvailability{false, false, false, true, true, true, true, true, true});
    if (!file_binding.has_value()
        || file_binding.value().path != BackingPath::path_b_persistent
        || file_binding.value().kind != BackingKind::file_backed_storage) {
        return 3;
    }

    const auto vm_binding = volume.bind(
        allocated.value(),
        BackingAvailability{false, false, false, false, false, false, true, true, true});
    if (!vm_binding.has_value()
        || vm_binding.value().path != BackingPath::path_c_software
        || vm_binding.value().kind != BackingKind::vm_memory) {
        return 4;
    }

    if (mmio_binding.value().cell.canonical_slot != file_binding.value().cell.canonical_slot
        || file_binding.value().cell.canonical_slot != vm_binding.value().cell.canonical_slot
        || mmio_binding.value().cell.route_residue != file_binding.value().cell.route_residue
        || file_binding.value().cell.route_residue != vm_binding.value().cell.route_residue) {
        return 5;
    }

    const auto released = volume.release(allocated.value().coordinate);
    return released.has_value() ? 0 : 6;
}
