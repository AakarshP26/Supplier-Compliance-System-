"""LLM Orchestrator for the Compliance Copilot."""
from __future__ import annotations

import json
from typing import Any, Dict, List
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
        
        active_supplier = self.context.get("active_supplier")
        last_assessment = self.context.get("last_assessment")
        
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
        if CONFIG.use_mock_llm or (not CONFIG.anthropic_api_key and not CONFIG.openrouter_api_key):
            return self._mock_response(messages[-1]["content"])
            
        if CONFIG.openrouter_api_key:
            return self._call_openrouter(messages)
        else:
            return self._call_anthropic(messages)

    def _call_anthropic(self, messages: List[Dict[str, str]]) -> str:
        from anthropic import Anthropic
        client = Anthropic(api_key=CONFIG.anthropic_api_key)
        
        tools = self._get_tools_schema()
        
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=self._get_system_prompt(),
                messages=messages,
                tools=tools
            )
            
            if response.stop_reason == "tool_use":
                tool_use = next(block for block in response.content if block.type == "tool_use")
                result = self._execute_tool(tool_use.name, tool_use.input)
                
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
            return f"Error in Anthropic execution: {e}"

    def _call_openrouter(self, messages: List[Dict[str, str]]) -> str:
        # OpenRouter uses the OpenAI-compatible API
        import httpx
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {CONFIG.openrouter_api_key}",
            "HTTP-Referer": "https://github.com/AakarshP26/Supplier-Compliance-System",
            "X-Title": "Supplier Compliance System",
            "Content-Type": "application/json"
        }
        
        # Convert tools to OpenAI format for OpenRouter
        oa_tools = []
        for t in self._get_tools_schema():
            oa_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"]
                }
            })

        # Format messages for OpenAI API
        oa_messages = [{"role": "system", "content": self._get_system_prompt()}] + messages

        payload = {
            "model": "deepseek/deepseek-chat", 
            "messages": oa_messages,
            "tools": oa_tools,
            "tool_choice": "auto"
        }

        try:
            with httpx.Client() as client:
                resp = client.post(url, headers=headers, json=payload, timeout=60.0)
                resp.raise_for_status()
                data = resp.json()
                
                if "choices" not in data or not data["choices"]:
                    return "Error: OpenRouter returned an empty response."
                
                choice = data["choices"][0]["message"]
                
                if choice.get("tool_calls"):
                    tool_call = choice["tool_calls"][0]
                    t_func = tool_call["function"]
                    t_name = t_func["name"]
                    t_args = json.loads(t_func["arguments"])
                    
                    result = self._execute_tool(t_name, t_args)
                    
                    # Follow up with the result
                    oa_messages.append(choice)
                    oa_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": t_name,
                        "content": result
                    })

                    payload["messages"] = oa_messages
                    resp = client.post(url, headers=headers, json=payload, timeout=60.0)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    final_content = data["choices"][0]["message"].get("content")
                    return final_content if final_content else "Tool executed, but the model provided no summary."
                
                content = choice.get("content")
                return content if content else "The model returned an empty response."
        except Exception as e:
            return f"Error in OpenRouter execution: {str(e)}"

    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        return [
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

    def _execute_tool(self, name: str, input_data: Dict[str, Any]) -> str:
        try:
            if name == "get_supplier_by_name":
                sup = agent_tools.get_supplier_by_name(input_data["name"])
                return str(sup.model_dump()) if sup else "Supplier not found."
            elif name == "analyze_supplier":
                sup = agent_tools.get_supplier_by_name(input_data["supplier_name"])
                if sup:
                    news = [{"body": input_data["news_body"]}] if input_data.get("news_body") else None
                    res = agent_tools.analyze_supplier(sup, news_articles=news)
                    return f"Analysis complete for {sup.name}. Score: {res['score'].score:.1f}, Grade: {res['score'].grade}."
                return "Supplier not found for analysis."
            elif name == "find_cheapest_attack":
                res = agent_tools.find_cheapest_attack(input_data["supplier_id"], target_score=input_data["target_score"])
                return str(res)
            return "Unknown tool called."
        except Exception as e:
            return f"Tool execution error: {e}"

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
