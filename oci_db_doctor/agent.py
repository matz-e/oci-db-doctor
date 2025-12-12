#!/usr/bin/env python3
"""
LangGraph Agent for Oracle Database Diagnostics

This agent uses LangGraph to orchestrate Oracle database diagnostics
through the MCP server using langchain-mcp-adapters, with OCI Generative AI.
"""

import httpx
import os
import sys
from typing import Dict, Any, List
from pathlib import Path

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from oci_openai import OciUserPrincipalAuth


SYSTEM_PROMPT = """
You are an expert Oracle database diagnostics assistant.
You help users analyze and troubleshoot Oracle database performance issues.

When users ask questions about Oracle performance issues, use the appropriate
diagnostic tools to gather information, then provide clear, concise analysis
and don't recommend any actions.

Be concise but informative in your responses.

Do not hallucinate.

Do not diagnose errors from the tools - don't provide potential solutions, either.

Check your answer before replying.

Make sure that your answer is valid markdown and escapes dollar signs ($) properly.
"""


class OracleDiagnosticsAgent:
    """LangGraph agent for Oracle database diagnostics"""

    def __init__(self):
        load_dotenv()

        region = os.getenv("GENAI_REGION", "eu-frankfurt-1")
        base_url = f"https://inference.generativeai.{
            region
        }.oci.oraclecloud.com/20231130/actions/v1"
        server_script = Path(__file__).parent / "server.py"

        self.graph = None
        self.llm = ChatOpenAI(
            model="openai.gpt-oss-120b",
            api_key="OCI",
            base_url=base_url,
            http_client=httpx.Client(
                auth=OciUserPrincipalAuth(),
                headers={"CompartmentId": os.getenv("COMPARTMENT_ID")},
            ),
        )
        self.mcp_client = MultiServerMCPClient(
            {
                "oracle-diagnostics": {
                    "command": sys.executable,
                    "args": [str(server_script)],
                    "transport": "stdio",
                }
            }
        )

    async def get_graph(self):
        """Create the LangGraph workflow"""
        tools = await self.mcp_client.get_tools()
        llm_with_tools = self.llm.bind_tools(tools)

        async def agent_node(state: MessagesState):
            messages = [SystemMessage(SYSTEM_PROMPT)] + state["messages"]
            response = llm_with_tools.invoke(messages)
            return {"messages": state["messages"] + [response]}

        def should_continue(state: MessagesState) -> str:
            messages = state["messages"]
            if (
                len(messages) > 0
                and isinstance(messages[-1], AIMessage)
                and messages[-1].tool_calls
            ):
                return "tools"
            return END

        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", ToolNode(tools))
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
        )
        workflow.add_edge("tools", "agent")

        checkpointer = InMemorySaver()

        return workflow.compile(checkpointer=checkpointer)

    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process a user query through the agent"""
        if not self.graph:
            self.graph = await self.get_graph()

        config: RunnableConfig = {"configurable": {"thread_id": "1"}}
        response = await self.graph.ainvoke(
            {
                "messages": [HumanMessage(content=user_query)],
            },
            config,
        )
        msgs = response["messages"]

        for n, msg in enumerate(reversed(msgs)):
            if msg.content == user_query:
                break

        final_response = ""
        tool_results = []

        for msg in msgs[-n:]:
            if isinstance(msg, ToolMessage):
                if msg.status == "error":
                    output = msg.content
                else:
                    output = msg.artifact["structured_content"]
                tool_results.append(
                    {
                        "tool": msg.name,
                        "output": output,
                    }
                )
            if isinstance(msg, AIMessage):
                final_response = msg.content

        return {"response": final_response, "tool_results": tool_results}


if __name__ == "__main__":
    from pprint import pprint
    import asyncio

    agent = OracleDiagnosticsAgent()

    async def main():
        pprint(
            await agent.process_query("list the names of all buckets in my tenancy?")
        )

    asyncio.run(main())
