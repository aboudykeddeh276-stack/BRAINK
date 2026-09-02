from openai import OpenAI

client = OpenAI()
response = client.responses.create(
    model="gpt-5.6",
    tools=[{
        "type": "mcp",
        "server_label": "braink",
        "server_url": "https://YOUR-BRAINK-MCP-HOST/mcp",
        "allowed_tools": [
            "braink_resolve_identity",
            "braink_create_work_envelope",
            "braink_consume_work_envelope",
            "braink_acquire_work_lease",
            "braink_get_work_lease",
            "braink_provision_domain_authority",
            "braink_observe_domain_authority",
            "braink_write_checkpoint",
            "braink_read_checkpoint",
        ],
        "require_approval": "always",
    }],
    input="Create and execute a durable BRAINK work item for a Domain Authority transition, read it back, and checkpoint it.",
)
print(response.output_text)
