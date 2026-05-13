"""Copilot sidebar for agentic assistance."""
from __future__ import annotations

from typing import Any
import streamlit as st
from scs.config import CONFIG
from scs.dashboard.agent import CopilotAgent

def render_copilot(context: dict[str, Any]) -> None:
    """Renders the persistent copilot chat interface."""
    
    # Custom styling for the copilot container
    st.markdown(
        """
        <style>
        .copilot-container {
            border-left: 1px solid rgba(120,120,120,0.2);
            padding-left: 1rem;
            height: calc(100vh - 100px);
            overflow-y: auto;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("### 🤖 Compliance Copilot")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant", 
                "content": "I'm your Supplier Compliance assistant. I can help you onboard suppliers, analyze risks, or run adversarial tests. How can I assist you today?"
            }
        ]

    # Container for messages to allow scrolling
    chat_container = st.container(height=600)
    
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("Ask me anything..."):
        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
        
        # Add to history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Initialize agent
        agent = CopilotAgent(context)

        # Generate response
        with chat_container:
            with st.chat_message("assistant"):
                with st.status("Thinking...", expanded=False) as status:
                    # Pass history excluding the last message (which is the current prompt)
                    response = agent.run(prompt, st.session_state.messages[:-1])
                    status.update(label="Response ready", state="complete", expanded=False)
                st.markdown(response)
        
        # Add to history
        st.session_state.messages.append({"role": "assistant", "content": response})
