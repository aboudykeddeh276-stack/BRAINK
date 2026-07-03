import Foundation

// MARK: - SpectrumIndex
//
// Enforces the KEX zero-less principle: every spectrum index ∈ [1, 2, 3, ...]
//
// Zero is the observer boundary — frame-dependent and external to the spectrum.
// It is never a discrete index. Negative values represent Cartesian traversal
// through zero (the Cartesian problem), which KEX resolves via instantaneous
// boundary reflection (ObserverBoundaryInversionTheorem).
//
// Theorems: NoDimensionalCollapseTheorem, ObserverStateEquivalenceTheorem

enum SpectrumIndex: Comparable, Hashable, CustomStringConvertible {
    case slot(Int)

    /// Returns true when the given integer is a legal spectrum member (≥ 1).
    /// Rejects 0 (observer boundary) and negatives (Cartesian domain).
    static func isValid(_ raw: Int) -> Bool {
        return raw >= 1
    }

    /// Returns a valid SpectrumIndex for the given raw integer, or nil if the
    /// value is zero or negative (observer boundary / Cartesian domain).
    static func make(_ raw: Int) -> SpectrumIndex? {
        guard isValid(raw) else { return nil }
        return .slot(raw)
    }

    var value: Int {
        switch self {
        case .slot(let v): return v
        }
    }

    var description: String { "SpectrumIndex(\(value))" }

    static func < (lhs: SpectrumIndex, rhs: SpectrumIndex) -> Bool {
        lhs.value < rhs.value
    }
}

// MARK: - ZeroLessSpectrum
//
// Represents the finite runtime spectrum [1, 2, 3, 4, 5] used for slot allocation.
//
// Design principles:
//   • All slot indices are positive integers ≥ 1 (zero-less).
//   • Arithmetic operations preserve spectrum membership: (a + b) ∈ [1, 2, 3, ...]
//   • No slot can collapse to determinant = 0 (NoDimensionalCollapseTheorem).
//   • The observer boundary (zero) is never stored as an integer constant.

struct ZeroLessSpectrum {
    /// The canonical runtime slot set: [1, 2, 3, 4, 5].
    static let runtimeSlots: [SpectrumIndex] = [
        .slot(1), .slot(2), .slot(3), .slot(4), .slot(5)
    ]

    /// The minimum spectrum index. Always 1 — never 0.
    static var minimum: SpectrumIndex { .slot(1) }

    /// Returns the next slot in the spectrum. Wraps to slot(1) after the last slot.
    static func next(after index: SpectrumIndex) -> SpectrumIndex {
        let current = index.value
        let next = current + 1
        if let found = runtimeSlots.first(where: { $0.value == next }) {
            return found
        }
        return minimum
    }

    /// Addition: result is always ≥ 1, preserving spectrum membership.
    static func add(_ a: SpectrumIndex, _ b: SpectrumIndex) -> SpectrumIndex {
        return .slot(a.value + b.value)
    }

    /// Validates that the given integer is a legal spectrum member (≥ 1).
    /// Delegates to SpectrumIndex.isValid to maintain a single source of truth.
    static func isValid(_ index: Int) -> Bool {
        return SpectrumIndex.isValid(index)
    }

    /// Proof gate: asserts that no slot in the provided list collapses to
    /// determinant = 0 (NoDimensionalCollapseTheorem).
    /// Returns true when all slots have value ≥ 1.
    @discardableResult
    static func assertNoDimensionalCollapse(slots: [SpectrumIndex]) -> Bool {
        return slots.allSatisfy { $0.value >= 1 }
    }
}
