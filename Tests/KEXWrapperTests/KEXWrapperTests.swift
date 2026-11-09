import XCTest
@testable import KEXWrapper

private struct KinCompressionStyle: CompressionStyle {
    let styleIdentifier = "author-native-style"

    func encodeLineage(genesis: SubscriptionGenesisAnchor, lineage: [LineageHop]) throws -> String {
        "\(genesis.id):\(lineage.count)"
    }
}

private struct ForeignCompressionStyle: CompressionStyle {
    let styleIdentifier = "foreign-style"

    func encodeLineage(genesis: SubscriptionGenesisAnchor, lineage: [LineageHop]) throws -> String {
        "foreign"
    }
}

final class KEXWrapperTests: XCTestCase {
    func testBootSeedReturnsLiveStateWithoutWarmBoot() {
        let seed = Seed(genesisAnchor: .init(id: "genesis"), activeWeight: .one)
        let state = bootSeed(seed)
        XCTAssertEqual(state.genesisAnchor.id, "genesis")
        XCTAssertEqual(state.activeWeight, .one)
    }

    func testZeroIsNeverAValidActiveState() {
        XCTAssertNil(ActiveWeight(rawValue: 0))
    }

    func testTopologicalDistanceDiffersFromScalarDelta() {
        XCTAssertEqual(topologicalDistance(.negativeTwo, .one), 1)
        XCTAssertEqual(scalarDelta(.negativeTwo, .one), 3)
    }

    func testCancellationIsBalancedAndRecoverable() {
        let result = add(1, -1)
        guard case let .balanced(balance) = result else {
            return XCTFail("Expected balanced projection")
        }
        XCTAssertEqual(balance.typedProjection, .cancellation)
        XCTAssertEqual(balance.recoveredOperands.0, 1)
        XCTAssertEqual(balance.recoveredOperands.1, -1)
    }

    func testLineageFrameHasNoReadablePayload() throws {
        let node = BRAINKNode(seed: .init(genesisAnchor: .init(id: "g"), activeWeight: .one), compressionStyle: KinCompressionStyle())
        let packet = try node.emitKexPacket()
        XCTAssertEqual(packet.frame.genesisAnchor.id, "g")
        XCTAssertFalse(packet.frame.compressedLineage.isEmpty)
    }

    func testAbsentOrForeignCompressionStyleIsNonComprehended() {
        let seed = Seed(genesisAnchor: .init(id: "genesis"), activeWeight: .one)
        let absentNode = BRAINKNode(seed: seed, compressionStyle: nil)
        XCTAssertFalse(absentNode.isComprehended)
        XCTAssertThrowsError(try absentNode.emitKexPacket())

        let root = BRAINKNode(seed: seed, compressionStyle: KinCompressionStyle())
        let foreign = root.spawnChild(compressionStyle: ForeignCompressionStyle())
        XCTAssertFalse(foreign.isComprehended)
    }

    func testLineageTracesToSubscriptionGenesis() {
        let root = BRAINKNode(seed: .init(genesisAnchor: .init(id: "anchor"), activeWeight: .one), compressionStyle: KinCompressionStyle())
        let child = root.spawnChild()
        XCTAssertEqual(child.state.genesisAnchor.id, "anchor")
        XCTAssertEqual(child.lineageToGenesis().first?.depth, 0)
    }

    func testCascadeProducesPowerNodesSharingGenesis() {
        let root = BRAINKNode(seed: .init(genesisAnchor: .init(id: "g0"), activeWeight: .one), compressionStyle: KinCompressionStyle())
        let fanOut = 3
        let depth = 2
        let nodes = root.cascade(fanOut: fanOut, depth: depth)
        XCTAssertEqual(nodes.count, integerPower(fanOut, depth))
        XCTAssertTrue(nodes.allSatisfy { $0.state.genesisAnchor.id == "g0" })
    }

    func testResolvedResultPropagatesByLookupAcrossKin() {
        let root = BRAINKNode(seed: .init(genesisAnchor: .init(id: "g"), activeWeight: .one), compressionStyle: KinCompressionStyle())
        let metrics = cascadeDemo(root: root, fanOut: 2, depth: 3, key: "resolve-key") {
            "deterministic"
        }
        XCTAssertEqual(metrics.computationCount, 1)
        XCTAssertEqual(metrics.lookupReuseCount, metrics.spawnedNodes)
    }

    func testMutatedOrForeignChildIsPrunedFromKinSet() {
        let root = BRAINKNode(seed: .init(genesisAnchor: .init(id: "g"), activeWeight: .one), compressionStyle: KinCompressionStyle())
        let foreignGenesis = Seed(genesisAnchor: .init(id: "other"), activeWeight: .one)
        let mutatedChild = root.spawnChild(seed: foreignGenesis)
        XCTAssertFalse(mutatedChild.isComprehended)

        let foreignStyleChild = root.spawnChild(compressionStyle: ForeignCompressionStyle())
        XCTAssertFalse(foreignStyleChild.isComprehended)

        let kin = root.kinSet()
        XCTAssertFalse(kin.contains { $0.nodeID == mutatedChild.nodeID })
        XCTAssertFalse(kin.contains { $0.nodeID == foreignStyleChild.nodeID })
    }
}
