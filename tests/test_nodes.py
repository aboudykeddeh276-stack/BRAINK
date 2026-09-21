import unittest

from observer2_runtime.nodes import (
    AttributeSpec,
    AttributionEdge,
    CapabilityClass,
    IntegrationContract,
    NodeDefinition,
    NodeTemplateRegistry,
    PortSpec,
    TemplateContract,
)


def make_definition(name: str, capability=CapabilityClass.SMART) -> NodeDefinition:
    return NodeDefinition(
        node_type=name,
        version="1.0.0",
        capability_class=capability,
        inputs=(PortSpec("signal_in", "signal"),),
        outputs=(PortSpec("signal_out", "signal"),),
        attributes=(AttributeSpec("label", "str", required=True),),
        attribution_graph=(AttributionEdge(name, "AUTHORED_BY", "a.keddeh"),),
        integration_contracts=(
            IntegrationContract("SIGNAL", "signal_out", "signal_in", ("SMART", "DUMB")),
        ),
        template_contract=TemplateContract(
            template_name=f"{name}.template",
            version="1.0.0",
            parameter_names=("label",),
        ),
        implementation_ref=f"observer2_runtime:{name}",
    )


class NodeContractTests(unittest.TestCase):
    def test_definition_identity_is_stable_and_instance_state_is_not_part_of_it(self):
        a = make_definition("HCI_BUTTON")
        b = make_definition("HCI_BUTTON")
        self.assertEqual(a.definition_id, b.definition_id)
        registry = NodeTemplateRegistry()
        registry.register(a)
        x = registry.instantiate(a.definition_id, parameters={"label": "Start"}, initial_state={"pressed": False})
        y = registry.instantiate(a.definition_id, parameters={"label": "Start"}, initial_state={"pressed": True})
        self.assertEqual(x.definition_id, y.definition_id)
        self.assertEqual(x.template_identity, y.template_identity)
        self.assertNotEqual(x.instance_id, y.instance_id)
        self.assertNotEqual(x.state_hash(), y.state_hash())

    def test_instance_state_and_edges_are_isolated(self):
        source_def = make_definition("SOURCE")
        target_def = make_definition("TARGET", CapabilityClass.DUMB)
        registry = NodeTemplateRegistry()
        registry.register(source_def)
        registry.register(target_def)
        source = registry.instantiate(source_def.definition_id, parameters={"label": "A"}, instance_id="source-1")
        sibling = registry.instantiate(source_def.definition_id, parameters={"label": "B"}, instance_id="source-2")
        target = registry.instantiate(target_def.definition_id, parameters={"label": "C"}, instance_id="target-1")
        registry.connect("source-1", "target-1", edge_type="SIGNAL", source_port="signal_out", destination_port="signal_in")
        self.assertEqual(len(source.integration_edges), 1)
        self.assertEqual(len(target.integration_edges), 1)
        self.assertEqual(len(sibling.integration_edges), 0)

    def test_template_forbids_opaque_fragment_copy(self):
        with self.assertRaises(ValueError):
            TemplateContract("bad", "1", (), opaque_fragment_copy_allowed=True)

    def test_typed_integration_rejects_mismatch(self):
        source = NodeDefinition(
            node_type="SOURCE",
            version="1",
            capability_class=CapabilityClass.SMART,
            inputs=(),
            outputs=(PortSpec("out", "signal"),),
            attributes=(),
            attribution_graph=(),
            integration_contracts=(IntegrationContract("SIGNAL", "out", "in"),),
            template_contract=TemplateContract("source", "1", ()),
            implementation_ref="source",
        )
        target = NodeDefinition(
            node_type="TARGET",
            version="1",
            capability_class=CapabilityClass.DUMB,
            inputs=(PortSpec("in", "bytes"),),
            outputs=(),
            attributes=(),
            attribution_graph=(),
            integration_contracts=(),
            template_contract=TemplateContract("target", "1", ()),
            implementation_ref="target",
        )
        registry = NodeTemplateRegistry()
        registry.register(source)
        registry.register(target)
        registry.instantiate(source.definition_id, instance_id="s")
        registry.instantiate(target.definition_id, instance_id="t")
        with self.assertRaises(TypeError):
            registry.connect("s", "t", edge_type="SIGNAL", source_port="out", destination_port="in")

    def test_lineage_preserved_on_derived_instance(self):
        definition = make_definition("HCI_PANEL")
        registry = NodeTemplateRegistry()
        registry.register(definition)
        parent = registry.instantiate(definition.definition_id, parameters={"label": "Parent"}, instance_id="parent")
        child = registry.instantiate(
            definition.definition_id,
            parameters={"label": "Child"},
            instance_id="child",
            lineage_parent_instance_id=parent.instance_id,
        )
        predicates = {edge.predicate for edge in child.attribution_graph}
        self.assertIn("INSTANCE_OF", predicates)
        self.assertIn("DERIVED_FROM_INSTANCE", predicates)
        self.assertEqual(child.observer_relation.observer_id, "OBSERVER2")


if __name__ == "__main__":
    unittest.main()


class NodeInstantiationV2Tests(unittest.TestCase):
    def test_capability_escalation_is_rejected(self):
        definition = NodeDefinition(
            node_type="SECURE_NODE",
            version="2.0.0",
            capability_class=CapabilityClass.SMART,
            inputs=(),
            outputs=(),
            attributes=(),
            attribution_graph=(AttributionEdge("SECURE_NODE", "AUTHORED_BY", "a.keddeh"),),
            integration_contracts=(),
            template_contract=TemplateContract("secure", "2", ()),
            implementation_ref="secure",
            definition_revision=2,
            sector_id="SECURITY",
            sector_class="runtime",
            target_constraints=("LOCAL",),
            capability_requirements=("read:state",),
            evidence_requirements=("unit-test",),
        )
        registry = NodeTemplateRegistry()
        registry.register(definition)
        with self.assertRaises(ValueError):
            registry.instantiate(
                definition.definition_id,
                target_profile="LOCAL",
                capability_grant=("read:state", "write:host"),
            )

    def test_unadmitted_target_is_rejected(self):
        definition = NodeDefinition(
            node_type="TARGETED_NODE",
            version="2.0.0",
            capability_class=CapabilityClass.SYSTEM,
            inputs=(),
            outputs=(),
            attributes=(),
            attribution_graph=(AttributionEdge("TARGETED_NODE", "AUTHORED_BY", "a.keddeh"),),
            integration_contracts=(),
            template_contract=TemplateContract("targeted", "2", ()),
            implementation_ref="targeted",
            definition_revision=2,
            sector_id="CLOUD",
            sector_class="infrastructure",
            target_constraints=("PUBLIC_HOST",),
            capability_requirements=(),
            evidence_requirements=("external-readback",),
        )
        registry = NodeTemplateRegistry()
        registry.register(definition)
        with self.assertRaises(ValueError):
            registry.instantiate(definition.definition_id, target_profile="LOCAL")

    def test_instance_carries_revision_target_and_grant(self):
        definition = NodeDefinition(
            node_type="PROFILED_NODE",
            version="2.0.0",
            capability_class=CapabilityClass.AGENTIC,
            inputs=(),
            outputs=(),
            attributes=(),
            attribution_graph=(AttributionEdge("PROFILED_NODE", "AUTHORED_BY", "a.keddeh"),),
            integration_contracts=(),
            template_contract=TemplateContract("profiled", "2", ()),
            implementation_ref="profiled",
            definition_revision=3,
            sector_id="AGENTS",
            sector_class="application",
            target_constraints=("LOCAL",),
            capability_requirements=("observe",),
            evidence_requirements=("unit-test",),
        )
        registry = NodeTemplateRegistry()
        registry.register(definition)
        instance = registry.instantiate(
            definition.definition_id,
            target_profile="LOCAL",
            capability_grant=("observe",),
            instance_id="profiled-1",
        )
        self.assertEqual(instance.definition_revision, 3)
        self.assertEqual(instance.target_profile, "LOCAL")
        self.assertEqual(instance.capability_grant, ("observe",))


class NodeEvidenceRootTests(unittest.TestCase):
    def test_instance_has_runtime_evidence_root(self):
        definition = NodeDefinition(
            node_type="EVIDENCE_NODE",
            version="2.1.0",
            capability_class=CapabilityClass.SMART,
            inputs=(PortSpec("in", "signal"),),
            outputs=(PortSpec("out", "signal"),),
            attributes=(),
            attribution_graph=(AttributionEdge("EVIDENCE_NODE", "AUTHORED_BY", "a.keddeh"),),
            integration_contracts=(IntegrationContract("SIGNAL", "out", "in", ("SMART",)),),
            template_contract=TemplateContract("evidence", "2.1", ()),
            implementation_ref="evidence",
            definition_revision=2,
            sector_id="EVIDENCE",
            sector_class="runtime",
            target_constraints=("LOCAL",),
            capability_requirements=("observe",),
            evidence_requirements=("unit-test", "runtime-readback"),
        )
        registry = NodeTemplateRegistry()
        registry.register(definition)
        instance = registry.instantiate(
            definition.definition_id,
            target_profile="LOCAL",
            capability_grant=("observe",),
            instance_id="evidence-1",
        )
        self.assertTrue(instance.runtime_evidence_root)
        self.assertEqual(instance.evidence_requirements, ("unit-test", "runtime-readback"))

    def test_integration_mutation_refreshes_evidence_roots(self):
        source = NodeDefinition(
            node_type="SOURCE_EVIDENCE",
            version="2.1.0",
            capability_class=CapabilityClass.SMART,
            inputs=(PortSpec("in", "signal"),),
            outputs=(PortSpec("out", "signal"),),
            attributes=(),
            attribution_graph=(AttributionEdge("SOURCE_EVIDENCE", "AUTHORED_BY", "a.keddeh"),),
            integration_contracts=(IntegrationContract("SIGNAL", "out", "in", ("SMART",)),),
            template_contract=TemplateContract("source-evidence", "2.1", ()),
            implementation_ref="source-evidence",
        )
        target = NodeDefinition(
            node_type="TARGET_EVIDENCE",
            version="2.1.0",
            capability_class=CapabilityClass.SMART,
            inputs=(PortSpec("in", "signal"),),
            outputs=(),
            attributes=(),
            attribution_graph=(AttributionEdge("TARGET_EVIDENCE", "AUTHORED_BY", "a.keddeh"),),
            integration_contracts=(),
            template_contract=TemplateContract("target-evidence", "2.1", ()),
            implementation_ref="target-evidence",
        )
        registry = NodeTemplateRegistry()
        registry.register(source)
        registry.register(target)
        s = registry.instantiate(source.definition_id, instance_id="source-evidence-1")
        t = registry.instantiate(target.definition_id, instance_id="target-evidence-1")
        s_before = s.runtime_evidence_root
        t_before = t.runtime_evidence_root
        registry.connect(
            s.instance_id,
            t.instance_id,
            edge_type="SIGNAL",
            source_port="out",
            destination_port="in",
        )
        self.assertNotEqual(s.runtime_evidence_root, s_before)
        self.assertNotEqual(t.runtime_evidence_root, t_before)
        self.assertTrue(s.runtime_evidence_root)
        self.assertTrue(t.runtime_evidence_root)
