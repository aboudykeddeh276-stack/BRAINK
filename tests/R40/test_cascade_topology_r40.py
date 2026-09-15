from enterprise.cascade_topology_r40 import CascadePlanner

KEY = b"cascade-test-key"


def build():
    return CascadePlanner(
        root_seed="KEX-REHYDRATE::CASCADE",
        secret_key=KEY,
        branching_factor=3,
        depth=3,
    ).build()


def test_ternary_depth3_node_count_and_layers():
    topo = build()
    result = topo.verify()
    assert result["status"] == "VALIDATED"
    assert result["total_nodes"] == 40
    assert result["layer_distribution"] == {0: 1, 1: 3, 2: 9, 3: 27}


def test_link_roles_vs_unique_edges_are_not_conflated():
    topo = build()
    metrics = topo.metrics()
    assert metrics["logical_link_roles"] == 78
    assert metrics["unique_undirected_edges"] == 75
    assert metrics["directed_adjacency_entries"] == 150


def test_layer1_root_and_parent_roles_share_same_edge():
    topo = build()
    layer1 = next(node for node in topo.nodes.values() if node.layer == 1)
    roles = [link for link in topo.link_roles if link.source == layer1.node_id]
    assert {link.role for link in roles} == {"parent", "root_anchor"}
    assert len({link.undirected_key() for link in roles}) == 1


def test_deeper_child_has_two_distinct_physical_edges():
    topo = build()
    layer2 = next(node for node in topo.nodes.values() if node.layer == 2)
    roles = [link for link in topo.link_roles if link.source == layer2.node_id]
    assert len({link.undirected_key() for link in roles}) == 2


def test_identity_is_deterministic():
    assert sorted(build().nodes) == sorted(build().nodes)


def test_different_seed_changes_identity():
    baseline = build()
    other = CascadePlanner(root_seed="OTHER", secret_key=KEY, branching_factor=3, depth=3).build()
    assert sorted(baseline.nodes) != sorted(other.nodes)


def test_activation_batches_are_layer_ordered():
    batches = CascadePlanner.activation_layers(build())
    assert list(map(len, batches)) == [1, 3, 9, 27]


def test_tampered_link_role_fails_verification():
    topo = build()
    child = next(node for node in topo.nodes.values() if node.layer == 2)
    topo.link_roles = [
        link for link in topo.link_roles
        if not (link.source == child.node_id and link.role == "root_anchor")
    ]
    assert topo.verify()["status"].startswith("FAILED:")
