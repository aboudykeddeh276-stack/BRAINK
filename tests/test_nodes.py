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
