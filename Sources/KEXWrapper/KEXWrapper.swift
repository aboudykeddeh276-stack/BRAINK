import Foundation

/// Subscription lineage anchor shared by all kin nodes in a cascaded BRAINK tree.
public struct SubscriptionGenesisAnchor: Hashable, Codable, Sendable {
    public let id: String

    public init(id: String) {
        self.id = id
    }
}

/// Active-state corridor, ordered by topological adjacency.
/// `1 feeds, 2 runs, -2/+2 bound, 2.97 warns, 3 transitions, 0 symbolises`
/// The `2.97 warns` threshold is advisory metadata and not a live active weight.
/// `0` is intentionally excluded from live active weights and represented only via typed-zero projections.
public enum ActiveWeight: Int, CaseIterable, Codable, Sendable {
    case negativeThree = -3
    case negativeTwo = -2
    case one = 1
    case positiveTwo = 2
    case positiveThree = 3

    /// Rank in the active corridor from 1...5.
    public var rank: Int {
        switch self {
        case .negativeThree: return 1
        case .negativeTwo: return 2
        case .one: return 3
        case .positiveTwo: return 4
        case .positiveThree: return 5
        }
    }

    fileprivate static let corridorOrder: [ActiveWeight] = [.negativeThree, .negativeTwo, .one, .positiveTwo, .positiveThree]
}

/// Typed zero values derived from the BRAINK zero classifier doctrine.
public enum TypedZero: String, CaseIterable, Codable, Sendable {
    case absence = "Absence"
    case cancellation = "Cancellation"
    case boundary = "Boundary"
    case externalLabel = "ExternalLabel"
    case symbolicResult = "SymbolicResult"
    case invalidWeight = "InvalidWeight"
}

/// Advisory threshold retained from corridor doctrine; not an active-state value.
public let activeStateWarningThreshold = 2.97

/// Non-erasing balanced representation of cancellation that keeps source operands recoverable.
public struct BalancedProjection: Equatable, Sendable {
    public let leftOperand: Int
    public let rightOperand: Int
    public let typedProjection: TypedZero

    public init(leftOperand: Int, rightOperand: Int, typedProjection: TypedZero) {
        self.leftOperand = leftOperand
        self.rightOperand = rightOperand
        self.typedProjection = typedProjection
    }

    public var recoveredOperands: (Int, Int) {
        (leftOperand, rightOperand)
    }
}

/// Sum output preserving active values or typed balanced cancellation.
public enum WeightedResult: Equatable, Sendable {
    case active(ActiveWeight)
    case balanced(BalancedProjection)
}

/// Scripted memory substrate carried by each BRAINK node without host adaptation.
public struct ScriptedMemorySubstrate: Equatable, Sendable {
    private var store: [String: String]

    public init(store: [String: String] = [:]) {
        self.store = store
    }

    public mutating func write(_ key: String, value: String) {
        store[key] = value
    }

    public func read(_ key: String) -> String? {
        store[key]
    }
}

/// Seed is already state input; no warm boot or hydration stage exists.
public struct Seed: Sendable {
    public let genesisAnchor: SubscriptionGenesisAnchor
    public let activeWeight: ActiveWeight
    public let scriptedMemory: ScriptedMemorySubstrate

    public init(genesisAnchor: SubscriptionGenesisAnchor, activeWeight: ActiveWeight, scriptedMemory: ScriptedMemorySubstrate = .init()) {
        self.genesisAnchor = genesisAnchor
        self.activeWeight = activeWeight
        self.scriptedMemory = scriptedMemory
    }
}

/// Live state materialized directly from a seed.
public struct KEXState: Sendable {
    public let genesisAnchor: SubscriptionGenesisAnchor
    public var activeWeight: ActiveWeight
    public var scriptedMemory: ScriptedMemorySubstrate

    public init(genesisAnchor: SubscriptionGenesisAnchor, activeWeight: ActiveWeight, scriptedMemory: ScriptedMemorySubstrate) {
        self.genesisAnchor = genesisAnchor
        self.activeWeight = activeWeight
        self.scriptedMemory = scriptedMemory
    }
}

/// Boot a seed directly into live state.
/// Do not reintroduce a warm-boot/hydration phase.
public func bootSeed(_ seed: Seed) -> KEXState {
    KEXState(genesisAnchor: seed.genesisAnchor, activeWeight: seed.activeWeight, scriptedMemory: seed.scriptedMemory)
}

/// Topological distance measured on corridor adjacency, not scalar arithmetic.
public func topologicalDistance(_ lhs: ActiveWeight, _ rhs: ActiveWeight) -> Int {
    guard
        let l = ActiveWeight.corridorOrder.firstIndex(of: lhs),
        let r = ActiveWeight.corridorOrder.firstIndex(of: rhs)
    else {
        return 0
    }
    return abs(l - r)
}

/// Scalar absolute delta using weight integer values.
public func scalarDelta(_ lhs: ActiveWeight, _ rhs: ActiveWeight) -> Int {
    abs(lhs.rawValue - rhs.rawValue)
}

/// Non-erasing addition over active corridor values.
public func add(_ lhs: Int, _ rhs: Int) -> WeightedResult {
    if lhs == -rhs {
        return .balanced(.init(leftOperand: lhs, rightOperand: rhs, typedProjection: .cancellation))
    }
    let sum = lhs + rhs
    if let active = ActiveWeight(rawValue: sum) {
        return .active(active)
    }
    return .balanced(.init(leftOperand: lhs, rightOperand: rhs, typedProjection: .invalidWeight))
}

/// AUTHOR-NATIVE — TO SUPPLY.
/// Protocol seam for owner-provided native lineage translation/compression style.
/// Implementations define how kin nodes encode lineage frames and how style identity is asserted.
public protocol CompressionStyle {
    var styleIdentifier: String { get }
    func encodeLineage(genesis: SubscriptionGenesisAnchor, lineage: [LineageHop]) throws -> String
}

/// Structural non-comprehension for absent/foreign kin translation style.
public enum StructuralNonComprehension: Error, Equatable, Sendable {
    case absentStyle
    case absentExpectedStyleIdentifier
    case foreignStyle(expected: String, received: String)
    case lineageEncodingFailed
    case foreignGenesis
}

/// Traversable lineage hop entry.
public struct LineageHop: Hashable, Codable, Sendable {
    public let nodeID: UUID
    public let depth: Int

    public init(nodeID: UUID, depth: Int) {
        self.nodeID = nodeID
        self.depth = depth
    }
}

/// HEX lineage frame (the lineage-compression term in the doctrine): carries lineage only (no readable payload).
public struct LineageFrame: Equatable, Sendable {
    public let genesisAnchor: SubscriptionGenesisAnchor
    public let styleIdentifier: String
    public let compressedLineage: String
    public let lineage: [LineageHop]

    public init(genesisAnchor: SubscriptionGenesisAnchor, styleIdentifier: String, compressedLineage: String, lineage: [LineageHop]) {
        self.genesisAnchor = genesisAnchor
        self.styleIdentifier = styleIdentifier
        self.compressedLineage = compressedLineage
        self.lineage = lineage
    }
}

/// Outbound P2P packet containing lineage frame only.
public struct KEXPacket: Equatable, Sendable {
    public let frame: LineageFrame

    public init(frame: LineageFrame) {
        self.frame = frame
    }
}

/// Shared distributed lineage log (not a single SHA chained authority).
public final class P2PLineageLedger {
    private var frames: [LineageFrame] = []

    public init() {}

    public func append(_ frame: LineageFrame) {
        frames.append(frame)
    }

    public func allFrames() -> [LineageFrame] {
        frames
    }
}

/// Shared kin resolved ledger where deterministic values are resolved once then reused by lookup.
public final class SharedResolvedLedger {
    private var values: [String: String] = [:]
    private var computationCounts: [String: Int] = [:]

    public init() {}

    public func resolve(_ key: String, compute: () -> String) -> String {
        if let value = values[key] {
            return value
        }
        computationCounts[key, default: 0] += 1
        let value = compute()
        values[key] = value
        return value
    }

    public func computationCount(for key: String) -> Int {
        computationCounts[key, default: 0]
    }
}

/// Self-hosting BRAINK node: seed + host + resolver.
public final class BRAINKNode {
    /// Sentinel used to force structural non-comprehension for foreign/mutated children.
    private static let foreignStyleSentinel = "__foreign__"

    public let nodeID: UUID
    public let state: KEXState
    public let isComprehended: Bool

    private let compressionStyle: CompressionStyle?
    private let expectedStyleIdentifier: String?
    private let sharedLedger: SharedResolvedLedger
    private let lineageLedger: P2PLineageLedger
    private let lineage: [LineageHop]
    private var children: [BRAINKNode] = []

    public init(seed: Seed,
                compressionStyle: CompressionStyle?,
                expectedStyleIdentifier: String? = nil,
                sharedLedger: SharedResolvedLedger? = nil,
                lineageLedger: P2PLineageLedger? = nil,
                lineage: [LineageHop]? = nil,
                nodeID: UUID = UUID()) {
        self.nodeID = nodeID
        self.state = bootSeed(seed)
        self.compressionStyle = compressionStyle
        self.expectedStyleIdentifier = expectedStyleIdentifier ?? compressionStyle?.styleIdentifier
        self.sharedLedger = sharedLedger ?? SharedResolvedLedger()
        self.lineageLedger = lineageLedger ?? P2PLineageLedger()

        if let lineage {
            self.lineage = lineage
        } else {
            self.lineage = [LineageHop(nodeID: nodeID, depth: 0)]
        }

        if let expected = self.expectedStyleIdentifier, let style = compressionStyle {
            self.isComprehended = (expected == style.styleIdentifier)
        } else {
            self.isComprehended = false
        }
    }

    public func emitKexPacket() throws -> KEXPacket {
        guard let style = compressionStyle else {
            throw StructuralNonComprehension.absentStyle
        }
        guard let expected = expectedStyleIdentifier else {
            throw StructuralNonComprehension.absentExpectedStyleIdentifier
        }
        guard style.styleIdentifier == expected else {
            throw StructuralNonComprehension.foreignStyle(expected: expected, received: style.styleIdentifier)
        }
        guard let compressedLineage = try? style.encodeLineage(genesis: state.genesisAnchor, lineage: lineage) else {
            throw StructuralNonComprehension.lineageEncodingFailed
        }

        let frame = LineageFrame(
            genesisAnchor: state.genesisAnchor,
            styleIdentifier: style.styleIdentifier,
            compressedLineage: compressedLineage,
            lineage: lineage
        )
        lineageLedger.append(frame)
        return KEXPacket(frame: frame)
    }

    @discardableResult
    public func spawnChild(seed: Seed? = nil, compressionStyle: CompressionStyle? = nil) -> BRAINKNode {
        let candidateSeed = seed ?? Seed(genesisAnchor: state.genesisAnchor, activeWeight: state.activeWeight, scriptedMemory: state.scriptedMemory)
        let candidateStyle = compressionStyle ?? self.compressionStyle
        let nextDepth = (lineage.last?.depth ?? 0) + 1
        let childNodeID = UUID()
        let childLineage = lineage + [LineageHop(nodeID: childNodeID, depth: nextDepth)]
        let child = BRAINKNode(
            seed: candidateSeed,
            compressionStyle: candidateStyle,
            expectedStyleIdentifier: expectedStyleIdentifier,
            sharedLedger: sharedLedger,
            lineageLedger: lineageLedger,
            lineage: childLineage,
            nodeID: childNodeID
        )

        guard candidateSeed.genesisAnchor == state.genesisAnchor else {
            return BRAINKNode(
                seed: candidateSeed,
                compressionStyle: candidateStyle,
                expectedStyleIdentifier: Self.foreignStyleSentinel,
                sharedLedger: sharedLedger,
                lineageLedger: lineageLedger,
                lineage: childLineage,
                nodeID: childNodeID
            )
        }

        if child.isComprehended {
            children.append(child)
        }
        return child
    }

    /// Cascades into breadth `fanOut` over `depth`, returning comprehended kin nodes at that depth.
    /// With matching kin style/genesis, this yields exactly `fanOut^depth` nodes (including `1` node for `depth == 0`).
    /// For `depth == 0`, the root node (`self`) is returned as the single node.
    public func cascade(fanOut: Int, depth: Int) -> [BRAINKNode] {
        precondition(fanOut > 0, "fanOut must be positive")
        precondition(depth >= 0, "depth must be non-negative")

        var current: [BRAINKNode] = [self]

        for _ in 0..<depth {
            var next: [BRAINKNode] = []
            for node in current {
                for _ in 0..<fanOut {
                    let child = node.spawnChild()
                    if child.isComprehended {
                        next.append(child)
                    }
                }
            }
            current = next
        }
        return current
    }

    public func kinSet() -> [BRAINKNode] {
        var all: [BRAINKNode] = [self]
        for child in children {
            all.append(contentsOf: child.kinSet())
        }
        return all
    }

    public func lineageToGenesis() -> [LineageHop] {
        lineage
    }

    public func resolve(_ key: String, compute: () -> String) -> String {
        sharedLedger.resolve(key, compute: compute)
    }

    public func computationCount(for key: String) -> Int {
        sharedLedger.computationCount(for: key)
    }
}

/// Cascade execution metrics.
public struct CascadeMetrics: Equatable, Sendable {
    public let spawnedNodes: Int
    public let expectedNodes: Int
    public let computationCount: Int
    public let lookupReuseCount: Int

    public init(spawnedNodes: Int, expectedNodes: Int, computationCount: Int, lookupReuseCount: Int) {
        self.spawnedNodes = spawnedNodes
        self.expectedNodes = expectedNodes
        self.computationCount = computationCount
        self.lookupReuseCount = lookupReuseCount
    }
}

/// Demo: spawn N^d kin nodes and measure shared ledger lookup reuse.
public func cascadeDemo(root: BRAINKNode, fanOut: Int, depth: Int, key: String, compute: () -> String) -> CascadeMetrics {
    let nodes = root.cascade(fanOut: fanOut, depth: depth)
    let expected = integerPower(fanOut, depth)

    _ = root.resolve(key, compute: compute)
    for node in nodes {
        _ = node.resolve(key, compute: compute)
    }

    let computations = root.computationCount(for: key)
    let lookups = (nodes.count + 1) - computations
    return CascadeMetrics(
        spawnedNodes: nodes.count,
        expectedNodes: expected,
        computationCount: computations,
        lookupReuseCount: lookups
    )
}

/// Integer exponentiation utility used for deterministic cascade cardinality math.
public func integerPower(_ base: Int, _ exponent: Int) -> Int {
    precondition(exponent >= 0, "exponent must be non-negative")
    return (0..<exponent).reduce(1) { partial, _ in partial * base }
}
