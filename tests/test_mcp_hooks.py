"""
Unit Tests for MCP Hooks & Isolated Context Streams.
"""

import asyncio
from src.mcp.hooks import MCPAgentBridge

def test_mcp_agent_context_isolation():
    async def _run():
        bridge = MCPAgentBridge()

        # Sync United Beats event
        await bridge.sync_tenant_context("united_beats", {"track": "detroit_techno"}, "stream/ingest")

        # Sync Excel Legacy Realty event
        await bridge.sync_tenant_context("excel_legacy_realty", {"lead": "marcus_vance"}, "leads/ingest")

        ub_history = bridge.get_tenant_mcp_history("united_beats")
        excel_history = bridge.get_tenant_mcp_history("excel_legacy_realty")

        assert len(ub_history) == 1
        assert "detroit_techno" in ub_history[0]["data_summary"]

        assert len(excel_history) == 1
        assert "marcus_vance" in excel_history[0]["data_summary"]

        # Verify zero leakage
        assert "detroit_techno" not in excel_history[0]["data_summary"]
        assert "marcus_vance" not in ub_history[0]["data_summary"]

    asyncio.run(_run())

def test_mcp_tool_definitions():
    bridge = MCPAgentBridge()
    tools = bridge.get_supported_mcp_tools()
    tool_names = [t["name"] for t in tools]
    assert "vrl1_route_api" in tool_names
    assert "vrl1_get_radial_status" in tool_names
    assert "vrl1_query_tenant_ledger" in tool_names
