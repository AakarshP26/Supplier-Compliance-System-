"""LLM Orchestrator for the Compliance Copilot."""
from __future__ import annotations

import json
from typing import Any, Dict, List
import streamlit as st
from scs.config import CONFIG
from scs.dashboard import agent_tools

class CopilotAgent:
    def __init__(self, context: dict[str, Any]):
        self.context = context
        self.model = "claude-3-5-sonnet-20240620" # Standard sonnet
        
    def _get_system_prompt(self) -> str:
        page = self.context.get("page", "Overview")
        use_defense = self.context.get("use_defense", True)
        threshold = self.context.get("threshold", 50.0)
        
        # Extract context from session state
        active_supplier = st.session_state.get("detail_picker") or st.session_state.get("adv_supplier")
        last_assessment = st.session_state.get("last_assessment")
        
        context_str = f"""
Current Context:
- Active Page: {page}
- Trust-Calibrated Defense: {'Enabled' if use_defense else 'Disabled'}
- Risk Threshold: {threshold}
"""
        if active_supplier:
            context_str += f"- Selected Supplier: {active_supplier}\n"
        
        if last_assessment:
            ls = last_assessment["supplier"]
            context_str += f"- Recently onboarded: {ls.name} ({ls.country})\n"

        return f"""You are the Supplier Compliance Copilot, an AI assistant for industrial procurement and risk managers.
Your goal is to help users analyze suppliers, onboard new ones, and test system resilience.

{context_str}

Capabilities:
- Finding suppliers in the directory.
- Running compliance and risk assessments.
- Explaining risk scores and belief decomposition (DS fusion).
- Automating red-team attacks in the Adversarial Lab.

Available Tools:
- get_supplier_by_name(name): Returns a Supplier object.
- analyze_supplier(supplier_obj, news_articles=None): Runs the full pipeline. Returns a report.
- find_cheapest_attack(supplier_id, vector, target_score): Finds min budget to flip a score.

Guidelines:
- If a user mentions a supplier name, use `get_supplier_by_name` to verify.
- Be concise but data-driven. Reference "belief masses" and "uncertainty" when explaining scores.
- For onboarding, if the user provides news text, use `analyze_supplier` with that text.
- If on the 'Adversarial lab' page, focus on vulnerability analysis and score lift.
"""

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        if CONFIG.use_mock_llm or not CONFIG.anthropic_api_key:
            return self._mock_response(messages[-1]["content"])
            
        from anthropic import Anthropic
        client = Anthropic(api_key=CONFIG.anthropic_api_key)
        
        tools = [
            {
                "name": "get_supplier_by_name",
                "description": "Finds a supplier in the directory by name (fuzzy).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The name of the supplier to find."}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "analyze_supplier",
                "description": "Runs full compliance and risk analysis for a supplier.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "supplier_name": {"type": "string", "description": "Name of the supplier to analyze."},
                        "news_body": {"type": "string", "description": "Optional news text to analyze."}
                    },
                    "required": ["supplier_name"]
                }
            },
            {
                "name": "find_cheapest_attack",
                "description": "Finds the minimum budget required to push a score above a target.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "supplier_id": {"type": "string", "description": "The ID of the supplier."},
                        "target_score": {"type": "number", "description": "The target score to reach."}
                    },
                    "required": ["supplier_id", "target_score"]
                }
            }
        ]
        
        try:
            # 1. Get initial response
            response = client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=self._get_system_prompt(),
                messages=messages,
                tools=tools
            )
            
            # 2. Handle tool calls
            if response.stop_reason == "tool_use":
                tool_use = next(block for block in response.content if block.type == "tool_use")
                tool_name = tool_use.name
                tool_input = tool_use.input
                
                result = "Tool execution failed."
                if tool_name == "get_supplier_by_name":
                    sup = agent_tools.get_supplier_by_name(tool_input["name"])
                    result = str(sup.model_dump()) if sup else "Supplier not found."
                elif tool_name == "analyze_supplier":
                    sup = agent_tools.get_supplier_by_name(tool_input["supplier_name"])
                    if sup:
                        news = [{"body": tool_input["news_body"]}] if tool_input.get("news_body") else None
                        res = agent_tools.analyze_supplier(sup, news_articles=news)
                        result = f"Analysis complete for {sup.name}. Score: {res['score'].score:.1f}, Grade: {res['score'].grade}."
                    else:
                        result = "Supplier not found for analysis."
                elif tool_name == "find_cheapest_attack":
                    res = agent_tools.find_cheapest_attack(tool_input["supplier_id"], target_score=tool_input["target_score"])
                    result = str(res)
                
                # 3. Get final response with tool result
                final_response = client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    system=self._get_system_prompt(),
                    messages=messages + [
                        {"role": "assistant", "content": response.content},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": result
                                }
                            ]
                        }
                    ],
                    tools=tools
                )
                return "".join(block.text for block in final_response.content if block.type == "text")
            
            return "".join(block.text for block in response.content if block.type == "text")
        except Exception as e:
            return f"Error in agent execution: {e}"

    def _mock_response(self, prompt: str) -> str:
        prompt_low = prompt.lower()
        if "hello" in prompt_low or "hi" in prompt_low:
            return "Hello! I'm your Compliance Copilot. How can I help you with your supplier risk management today?"
        
        if "onboard" in prompt_low or "new supplier" in prompt_low:
            return "I can help you onboard a new supplier. Please provide the company name, country, and any recent news articles you'd like me to analyze."
            
        if "attack" in prompt_low or "red team" in prompt_low:
            return "I can run adversarial simulations. For which supplier should I find the cheapest attack vector?"

        if "risk" in prompt_low or "score" in prompt_low:
             return "I can explain the risk scores. The system uses Dempster-Shafer fusion to combine compliance signals and news sentiment. Which supplier's score should we look at?"
             
        return f"I've noted your request about '{prompt}'. I'm currently in Phase 1 of my integration, so my ability to run tools is limited, but I can discuss the methodology and data with you."

    def run(self, user_prompt: str, history: List[Dict[str, str]]) -> str:
        messages = history + [{"role": "user", "content": user_prompt}]
        return self._call_llm(messages)
