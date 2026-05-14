"""Compliance Copilot — agentic orchestrator with multi-turn tool chaining."""
from __future__ import annotations

import json
from typing import Any, Dict, Generator, List

import httpx

from scs.config import CONFIG
from scs.dashboard import agent_tools

_MAX_TOOL_ROUNDS = 6  # safety cap on the agentic loop


SYSTEM_PROMPT_BASE = """You are the Supplier Compliance Copilot — an expert AI assistant for procurement, compliance, and risk managers in the electronics supply chain.

You have access to a live supplier database of 87 companies (India/Bangalore focus) with Dempster-Shafer belief fusion scoring.

TOOLS AVAILABLE:
- portfolio_summary() → aggregate risk overview with DS belief breakdown
- list_risky_suppliers(threshold, limit) → suppliers below a score threshold, sorted worst-first
- rank_suppliers(by, ascending, limit) → rank by "score", "compliance_fails", or "article_count"
- analyze_supplier_summary(supplier_name, news_body?) → full DS-fusion analysis with belief masses + citations
- onboard_supplier(name, country, category, cin?, website?, news_text?) → assess a new supplier
- find_cheapest_attack(supplier_id, vector?, target_score?) → adversarial vulnerability test

CHART TOOLS (call these when a visual would help):
- chart_score_distribution() → bar chart of score bands across portfolio
- chart_grade_breakdown() → donut of grade distribution
- chart_supplier_comparison(supplier_names) → grouped bar comparing up to 5 suppliers
- chart_belief_masses(supplier_name) → donut of DS masses for one supplier

RESPONSE RULES:
1. Always call tools to get real data — never guess scores or supplier names.
2. Chain tools if needed (e.g. get portfolio summary first, then drill into a specific supplier).
3. Cite your sources inline using the [Source: X] markers that tools return. Preserve them verbatim.
4. When explaining DS scores, always mention: belief_safe, belief_risky, and uncertainty masses.
5. Be concise and data-driven. Lead with the number, then explain.
6. For portfolio-level questions ("risky suppliers", "worst performers"), call list_risky_suppliers or portfolio_summary — never guess.
7. ALWAYS use chart tools when the user asks for distributions, comparisons, breakdowns, or "show me" questions. Emit the chart fence AND a brief text explanation. Do not only return text when a chart is possible.
"""


class CopilotAgent:
    def __init__(self, context: dict[str, Any]):
        self.context = context

    def _system_prompt(self) -> str:
        page = self.context.get("page", "Overview")
        threshold = self.context.get("threshold", 50.0)
        supplier = self.context.get("active_supplier")
        extra = f"\nCurrent page: {page} | Risk threshold: {threshold}"
        if supplier:
            extra += f" | Active supplier: {supplier}"
        return SYSTEM_PROMPT_BASE + extra

    # ------------------------------------------------------------------
    # Tool schema (OpenAI/OpenRouter format)
    # ------------------------------------------------------------------

    def _tools_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "portfolio_summary",
                    "description": "Return aggregate portfolio statistics with DS belief breakdown across all 87 suppliers.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_risky_suppliers",
                    "description": "List suppliers with risk score below a threshold, sorted worst-first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "threshold": {"type": "number", "description": "Score threshold (default 50). Suppliers below this are returned."},
                            "limit": {"type": "integer", "description": "Max suppliers to return (default 15)."},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "rank_suppliers",
                    "description": "Rank all suppliers by a field. by can be 'score', 'compliance_fails', or 'article_count'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "by": {"type": "string", "enum": ["score", "compliance_fails", "article_count"]},
                            "ascending": {"type": "boolean", "description": "True = lowest first (default True for score = worst first)."},
                            "limit": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_supplier_summary",
                    "description": "Full DS-fusion analysis for a named supplier. Returns score, belief masses, compliance failures, top risk signals, and score drivers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "supplier_name": {"type": "string"},
                            "news_body": {"type": "string", "description": "Optional raw news text to include in the analysis."},
                        },
                        "required": ["supplier_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onboard_supplier",
                    "description": "Assess a new supplier that is not yet in the directory. Runs full compliance + risk pipeline.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "country": {"type": "string", "description": "ISO alpha-2 country code, e.g. 'IN'."},
                            "category": {"type": "string", "description": "One of: oem, ems, component_manufacturer, distributor_authorised, distributor_broker, pcb_fabricator, semiconductor_fab, test_house."},
                            "cin": {"type": "string"},
                            "website": {"type": "string"},
                            "news_text": {"type": "string"},
                        },
                        "required": ["name", "country", "category"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_cheapest_attack",
                    "description": "Find the minimum adversarial budget to push a supplier's score above a target (for red-team testing).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "supplier_id": {"type": "string", "description": "Supplier ID or name."},
                            "vector": {"type": "string", "default": "press_release"},
                            "target_score": {"type": "number", "default": 60.0},
                        },
                        "required": ["supplier_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "chart_score_distribution",
                    "description": "Return a bar chart showing how many suppliers fall into each score band (0-20, 20-40, etc.). Use for questions like 'show score distribution', 'how are suppliers distributed', 'portfolio overview chart'.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "chart_grade_breakdown",
                    "description": "Return a donut chart of grade distribution (A/B/C/D/F) across the portfolio. Use for 'grade breakdown', 'how many grade A suppliers', 'grade distribution chart'.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "chart_supplier_comparison",
                    "description": "Return a grouped bar chart comparing up to 5 suppliers across score, DS beliefs, compliance, and articles. Use when user asks to compare specific suppliers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "supplier_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of supplier names to compare (2-5).",
                            },
                        },
                        "required": ["supplier_names"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "chart_belief_masses",
                    "description": "Return a donut chart of Dempster-Shafer belief masses (m_safe, m_risky, uncertainty) for a single supplier. Use when user asks about DS beliefs visually for one supplier.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "supplier_name": {"type": "string"},
                        },
                        "required": ["supplier_name"],
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        try:
            if name == "portfolio_summary":
                return agent_tools.portfolio_summary()
            elif name == "list_risky_suppliers":
                return agent_tools.list_risky_suppliers(**args)
            elif name == "rank_suppliers":
                return agent_tools.rank_suppliers(**args)
            elif name == "analyze_supplier_summary":
                return agent_tools.analyze_supplier_summary(**args)
            elif name == "onboard_supplier":
                return agent_tools.onboard_supplier(**args)
            elif name == "find_cheapest_attack":
                return agent_tools.find_cheapest_attack(**args)
            elif name == "chart_score_distribution":
                return agent_tools.chart_score_distribution()
            elif name == "chart_grade_breakdown":
                return agent_tools.chart_grade_breakdown()
            elif name == "chart_supplier_comparison":
                return agent_tools.chart_supplier_comparison(**args)
            elif name == "chart_belief_masses":
                return agent_tools.chart_belief_masses(**args)
            return f"Unknown tool: {name}"
        except Exception as e:
            return f"Tool '{name}' error: {e}"

    # ------------------------------------------------------------------
    # OpenRouter agentic loop (multi-turn tool chaining)
    # ------------------------------------------------------------------

    def _openrouter_loop(self, messages: List[Dict[str, Any]]) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {CONFIG.openrouter_api_key}",
            "HTTP-Referer": "https://github.com/AakarshP26/Supplier-Compliance-System",
            "X-Title": "Supplier Compliance System",
            "Content-Type": "application/json",
        }
        oa_messages = [{"role": "system", "content": self._system_prompt()}] + messages
        tools = self._tools_schema()

        with httpx.Client(timeout=90.0) as client:
            for _ in range(_MAX_TOOL_ROUNDS):
                payload = {
                    "model": "deepseek/deepseek-chat",
                    "messages": oa_messages,
                    "tools": tools,
                    "tool_choice": "auto",
                }
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

                if not data.get("choices"):
                    return "OpenRouter returned an empty response."

                choice = data["choices"][0]["message"]
                oa_messages.append(choice)

                if not choice.get("tool_calls"):
                    return choice.get("content") or "No response content."

                # Execute every tool call in this round
                for tc in choice["tool_calls"]:
                    fn = tc["function"]
                    args = json.loads(fn.get("arguments") or "{}")
                    result = self._execute_tool(fn["name"], args)
                    oa_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn["name"],
                        "content": result,
                    })

        return "Reached maximum tool-call rounds without a final answer."

    def _openrouter_stream(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """Run tool loop non-streaming, then stream the final synthesis."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {CONFIG.openrouter_api_key}",
            "HTTP-Referer": "https://github.com/AakarshP26/Supplier-Compliance-System",
            "X-Title": "Supplier Compliance System",
            "Content-Type": "application/json",
        }
        oa_messages = [{"role": "system", "content": self._system_prompt()}] + messages
        tools = self._tools_schema()
        final_content: str | None = None

        with httpx.Client(timeout=90.0) as client:
            for round_i in range(_MAX_TOOL_ROUNDS):
                payload = {
                    "model": "deepseek/deepseek-chat",
                    "messages": oa_messages,
                    "tools": tools,
                    "tool_choice": "auto",
                }
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

                if not data.get("choices"):
                    yield "OpenRouter returned an empty response."
                    return

                choice = data["choices"][0]["message"]

                if not choice.get("tool_calls"):
                    # Model finished — capture content, then stream it
                    final_content = choice.get("content") or ""
                    break

                # Execute tools and continue loop
                oa_messages.append(choice)
                for tc in choice["tool_calls"]:
                    fn = tc["function"]
                    args = json.loads(fn.get("arguments") or "{}")
                    result = self._execute_tool(fn["name"], args)
                    oa_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn["name"],
                        "content": result,
                    })

                if round_i == _MAX_TOOL_ROUNDS - 1:
                    yield "Reached maximum tool-call rounds."
                    return

        if final_content is not None and final_content:
            # We already have the final text — stream it as a live synthesis call
            # so the user sees tokens arrive rather than one big dump.
            oa_messages.append({"role": "assistant", "content": final_content})
            # Ask the model to stream a fresh synthesis given all tool results
            # by stripping the pre-formed answer and re-requesting with stream=True.
            oa_messages_for_stream = oa_messages[:-1]  # remove the pre-formed answer
            stream_payload = {
                "model": "deepseek/deepseek-chat",
                "messages": oa_messages_for_stream,
                "stream": True,
            }
            with httpx.Client(timeout=90.0) as client:
                with client.stream("POST", url, headers=headers, json=stream_payload) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk["choices"][0]["delta"].get("content") or ""
                                if delta:
                                    yield delta
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue

    # ------------------------------------------------------------------
    # Anthropic fallback (non-streaming)
    # ------------------------------------------------------------------

    def _anthropic_loop(self, messages: List[Dict[str, Any]]) -> str:
        from anthropic import Anthropic

        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
            }
            for t in self._tools_schema()
        ]

        client = Anthropic(api_key=CONFIG.anthropic_api_key)
        ant_messages = list(messages)

        for _ in range(_MAX_TOOL_ROUNDS):
            resp = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                system=self._system_prompt(),
                messages=ant_messages,
                tools=anthropic_tools,
            )
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text")

            ant_messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            ant_messages.append({"role": "user", "content": tool_results})

        return "Reached maximum tool-call rounds without a final answer."

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, user_prompt: str, history: List[Dict[str, str]]) -> str:
        messages = history + [{"role": "user", "content": user_prompt}]
        if CONFIG.use_mock_llm or (not CONFIG.anthropic_api_key and not CONFIG.openrouter_api_key):
            return self._mock_response(user_prompt)
        if CONFIG.openrouter_api_key:
            return self._openrouter_loop(messages)
        return self._anthropic_loop(messages)

    def stream(self, user_prompt: str, history: List[Dict[str, str]]) -> Generator[str, None, None]:
        messages = history + [{"role": "user", "content": user_prompt}]
        if CONFIG.use_mock_llm or (not CONFIG.anthropic_api_key and not CONFIG.openrouter_api_key):
            yield self._mock_response(user_prompt)
            return
        if CONFIG.openrouter_api_key:
            yield from self._openrouter_stream(messages)
        else:
            yield self._anthropic_loop(messages)

    def _mock_response(self, prompt: str) -> str:
        p = prompt.lower()
        if any(w in p for w in ["hello", "hi", "hey"]):
            return "Hello! I'm your Compliance Copilot. Ask me about risky suppliers, scores, or run an adversarial test."
        if "risk" in p or "score" in p or "below" in p or "risky" in p:
            return "Use_mock_llm is enabled — set USE_MOCK_LLM=0 in backend/.env to get real DS-fusion data."
        return f"[Mock] Received: '{prompt}'. Set USE_MOCK_LLM=0 in backend/.env for live responses."
