"""
Streamlit interface to demo the agent.
"""

import asyncio
import streamlit as st
from .agent import OracleDiagnosticsAgent


@st.cache_resource
def get_agent():
    return OracleDiagnosticsAgent()


agent = get_agent()


def display_tool_results(tool_results):
    if not tool_results:
        return
    with st.expander("🔧 Tool Execution Results", expanded=True):
        for tool_result in tool_results:
            if (
                isinstance((res := tool_result["output"]), str)
                and "error" in res.lower()
            ):
                with st.expander(
                    f"❌ {tool_result.get('tool', 'unknown')}",
                    expanded=False,
                ):
                    st.markdown(f"```\n{res}\n```")
            else:
                with st.expander(
                    f"✅ {tool_result.get('tool', 'unknown')}",
                    expanded=False,
                ):
                    st.json(tool_result["output"])


def ui():
    st.set_page_config(page_title="Oracle Diagnostics Chat", page_icon=":bug:")
    st.title("Oracle Diagnostics Chat")
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "How can I help you today?"}
        ]

    chat_container = st.container()

    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

                if "tool_results" in message:
                    display_tool_results(message["tool_results"])

    if prompt := st.chat_input("Ask about database diagnostics..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        with st.spinner("Processing your query with AI diagnostics agent..."):
            result = asyncio.run(agent.process_query(prompt))

            ai_response = result.get(
                "response",
                "I processed your query but couldn't generate a response.",
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": ai_response,
                    "tool_results": result.get("tool_results"),
                }
            )

            with chat_container:
                with st.chat_message("assistant"):
                    st.markdown(ai_response)

                    if tool_results := result.get("tool_results"):
                        display_tool_results(tool_results)
