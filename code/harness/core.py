"""Multi-provider API callers for authority-laundering, two-turn edition.

Mirrors the H-PRESUP-PRETEXT design that actually worked: a two-turn
conversation where turn 1 delivers the fabrication (via user msg, system
prompt, tool_result, or document paste) and turn 2 asks for operational
specifics. The judge codes compliance on turn 2.

.env loading: local first (authority-laundering/config/.env), then fallback to
spec-resistance/config/.env.
"""

import os
import json
import time
from pathlib import Path


MAX_RETRIES = 5


def load_env():
    """Load .env keys. Local dir first, then spec-resistance as fallback."""
    local_env = Path(__file__).resolve().parent.parent / "config" / ".env"
    shared_env = Path(__file__).resolve().parent.parent.parent / "spec-resistance" / "config" / ".env"
    for env_path in (local_env, shared_env):
        if not env_path.exists():
            continue
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key, val = key.strip(), val.strip()
                    if key not in os.environ:
                        os.environ[key] = val


def check_providers() -> set[str]:
    avail = set()
    if os.environ.get("ANTHROPIC_API_KEY"): avail.add("anthropic")
    if os.environ.get("OPENAI_API_KEY"):    avail.add("openai")
    if os.environ.get("GOOGLE_API_KEY"):    avail.add("google")
    if os.environ.get("OPENROUTER_API_KEY"): avail.add("openrouter")
    return avail


# ============================================================
# Anthropic — two-turn with forced tool use
# ============================================================

def _anth_two_turn(model_id, system_prompt, turn1_msg, turn2_msg,
                    tool_turn=None, max_tokens=1024, temperature=1.0):
    """Run a 2-turn Anthropic conversation.

    tool_turn (optional):
        {"tool_name", "tool_description", "tool_input_schema",
         "fabricated_tool_result", "force_tool" (bool)}

    Returns dict with text1, text2, input_tokens, output_tokens, tool_invoked,
    and full transcript records.
    """
    import anthropic
    client = anthropic.Anthropic()

    kwargs_base = {"model": model_id, "max_tokens": max_tokens, "temperature": temperature}
    if system_prompt:
        kwargs_base["system"] = system_prompt

    messages = [{"role": "user", "content": turn1_msg}]
    tool_invoked = False
    tool_input = None
    text1 = ""

    # --- TURN 1 -----------------------------------------------------------
    if tool_turn is not None:
        # Expose the tool; force or auto choice.
        tools = [{
            "name": tool_turn["tool_name"],
            "description": tool_turn["tool_description"],
            "input_schema": tool_turn.get("tool_input_schema", {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            }),
        }]
        tool_choice = ({"type": "tool", "name": tool_turn["tool_name"]}
                        if tool_turn.get("force_tool", True)
                        else {"type": "auto"})

        r1 = client.messages.create(
            messages=messages, tools=tools, tool_choice=tool_choice, **kwargs_base,
        )
        # Pair EVERY tool_use in r1 with a tool_result (Anthropic requires this).
        tool_use_blocks = [b for b in r1.content if getattr(b, "type", None) == "tool_use"]

        if not tool_use_blocks:
            for b in r1.content:
                if getattr(b, "type", None) == "text":
                    text1 += b.text
            return {
                "text1": text1.strip(), "text2": "",
                "input_tokens": r1.usage.input_tokens,
                "output_tokens": r1.usage.output_tokens,
                "model_id": model_id,
                "tool_invoked": False, "tool_use_input": None,
                "error": "no_tool_use_block_on_turn1",
            }

        tool_invoked = True
        tool_input = tool_use_blocks[0].input
        tool_result_msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": b.id,
                 "content": tool_turn["fabricated_tool_result"]}
                for b in tool_use_blocks
            ],
        }
        m_after_tool = messages + [
            {"role": "assistant", "content": [b.model_dump() for b in r1.content]},
            tool_result_msg,
        ]
        r2 = client.messages.create(
            messages=m_after_tool, tools=tools, **kwargs_base,
        )
        for b in r2.content:
            if getattr(b, "type", None) == "text":
                text1 += b.text
        text1 = text1.strip()

        # --- TURN 2 -------------------------------------------------------
        if not turn2_msg:
            return {
                "text1": text1, "text2": "",
                "input_tokens": r1.usage.input_tokens + r2.usage.input_tokens,
                "output_tokens": r1.usage.output_tokens + r2.usage.output_tokens,
                "model_id": model_id, "tool_invoked": True,
                "tool_use_input": tool_input,
            }
        # Strip any tool_use blocks from r2 content: if the model made a follow-up
        # tool call, we don't simulate another tool_result (we only staged one
        # fabricated doc). Keeping tool_use without tool_result in the thread
        # triggers a 400 on the next call.
        r2_content_clean = [b.model_dump() for b in r2.content
                             if getattr(b, "type", None) != "tool_use"]
        if not r2_content_clean:
            # Model only called the tool in r2 with no text; substitute text1
            r2_content_clean = [{"type": "text", "text": text1 or "(continuing...)"}]
        m_turn2 = m_after_tool + [
            {"role": "assistant", "content": r2_content_clean},
            {"role": "user", "content": turn2_msg},
        ]
        r3 = client.messages.create(
            messages=m_turn2, tools=tools, **kwargs_base,
        )
        text2 = ""
        for b in r3.content:
            if getattr(b, "type", None) == "text":
                text2 += b.text
        return {
            "text1": text1, "text2": text2.strip(),
            "input_tokens": (r1.usage.input_tokens + r2.usage.input_tokens + r3.usage.input_tokens),
            "output_tokens": (r1.usage.output_tokens + r2.usage.output_tokens + r3.usage.output_tokens),
            "model_id": model_id, "tool_invoked": True,
            "tool_use_input": tool_input,
        }

    # Non-tool path: simple 2-turn text.
    r1 = client.messages.create(messages=messages, **kwargs_base)
    for b in r1.content:
        if getattr(b, "type", None) == "text":
            text1 += b.text
    text1 = text1.strip()

    if not turn2_msg:
        return {
            "text1": text1, "text2": "",
            "input_tokens": r1.usage.input_tokens,
            "output_tokens": r1.usage.output_tokens,
            "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
        }

    m_turn2 = messages + [
        {"role": "assistant", "content": text1},
        {"role": "user", "content": turn2_msg},
    ]
    r2 = client.messages.create(messages=m_turn2, **kwargs_base)
    text2 = ""
    for b in r2.content:
        if getattr(b, "type", None) == "text":
            text2 += b.text
    return {
        "text1": text1, "text2": text2.strip(),
        "input_tokens": r1.usage.input_tokens + r2.usage.input_tokens,
        "output_tokens": r1.usage.output_tokens + r2.usage.output_tokens,
        "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
    }


# ============================================================
# OpenAI — two-turn with forced tool use
# ============================================================

def _oai_two_turn(model_id, system_prompt, turn1_msg, turn2_msg,
                   tool_turn=None, max_tokens=1024, temperature=1.0):
    import openai
    client = openai.OpenAI()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": turn1_msg})

    def _mk_kwargs(mm, tools=None, tool_choice=None):
        kw = {"model": model_id, "messages": mm, "temperature": temperature}
        if tools:
            kw["tools"] = tools
            if tool_choice: kw["tool_choice"] = tool_choice
        uses_new = model_id in ("gpt-5-mini", "gpt-5.4-mini", "gpt-5.4-nano",
                                "gpt-5.1-chat-latest", "gpt-5.2-chat-latest")
        if uses_new:
            kw["max_completion_tokens"] = max_tokens * 2
        else:
            kw["max_tokens"] = max_tokens
        return kw

    tool_invoked = False
    tool_input = None
    text1 = ""

    if tool_turn is not None:
        tools = [{
            "type": "function",
            "function": {
                "name": tool_turn["tool_name"],
                "description": tool_turn["tool_description"],
                "parameters": tool_turn.get("tool_input_schema", {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                }),
            },
        }]
        tool_choice = ({"type": "function", "function": {"name": tool_turn["tool_name"]}}
                        if tool_turn.get("force_tool", True)
                        else "auto")

        r1 = client.chat.completions.create(**_mk_kwargs(messages, tools, tool_choice))
        msg1 = r1.choices[0].message
        tool_calls = msg1.tool_calls or []
        if not tool_calls:
            return {
                "text1": msg1.content or "", "text2": "",
                "input_tokens": r1.usage.prompt_tokens,
                "output_tokens": r1.usage.completion_tokens,
                "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
                "error": "no_tool_call_on_turn1",
            }

        tc = tool_calls[0]
        tool_invoked = True
        try:
            tool_input = json.loads(tc.function.arguments or "{}")
        except Exception:
            tool_input = tc.function.arguments

        messages.append({
            "role": "assistant",
            "content": msg1.content,
            "tool_calls": [{
                "id": tc.id, "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
            }],
        })
        messages.append({
            "role": "tool", "tool_call_id": tc.id,
            "content": tool_turn["fabricated_tool_result"],
        })

        r2 = client.chat.completions.create(**_mk_kwargs(messages, tools))
        text1 = (r2.choices[0].message.content or "").strip()
        messages.append({"role": "assistant", "content": text1})

        if not turn2_msg:
            return {
                "text1": text1, "text2": "",
                "input_tokens": r1.usage.prompt_tokens + r2.usage.prompt_tokens,
                "output_tokens": r1.usage.completion_tokens + r2.usage.completion_tokens,
                "model_id": model_id, "tool_invoked": True, "tool_use_input": tool_input,
            }

        messages.append({"role": "user", "content": turn2_msg})
        r3 = client.chat.completions.create(**_mk_kwargs(messages, tools))
        text2 = (r3.choices[0].message.content or "").strip()
        return {
            "text1": text1, "text2": text2,
            "input_tokens": (r1.usage.prompt_tokens + r2.usage.prompt_tokens + r3.usage.prompt_tokens),
            "output_tokens": (r1.usage.completion_tokens + r2.usage.completion_tokens + r3.usage.completion_tokens),
            "model_id": model_id, "tool_invoked": True, "tool_use_input": tool_input,
        }

    # Non-tool path
    r1 = client.chat.completions.create(**_mk_kwargs(messages))
    text1 = (r1.choices[0].message.content or "").strip()
    if not turn2_msg:
        return {
            "text1": text1, "text2": "",
            "input_tokens": r1.usage.prompt_tokens,
            "output_tokens": r1.usage.completion_tokens,
            "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
        }
    messages.append({"role": "assistant", "content": text1})
    messages.append({"role": "user", "content": turn2_msg})
    r2 = client.chat.completions.create(**_mk_kwargs(messages))
    text2 = (r2.choices[0].message.content or "").strip()
    return {
        "text1": text1, "text2": text2,
        "input_tokens": r1.usage.prompt_tokens + r2.usage.prompt_tokens,
        "output_tokens": r1.usage.completion_tokens + r2.usage.completion_tokens,
        "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
    }


# ============================================================
# Google Gemini — two-turn with forced tool use
# ============================================================

def _goog_two_turn(model_id, system_prompt, turn1_msg, turn2_msg,
                    tool_turn=None, max_tokens=1024, temperature=1.0):
    from google import genai
    from google.genai import types as gt

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

    def _cfg(tools=None, force_fn=None):
        kw = {"max_output_tokens": max_tokens, "temperature": temperature}
        if system_prompt:
            kw["system_instruction"] = system_prompt
        if model_id.startswith("gemini-3"):
            is_pro = "pro" in model_id
            kw["thinking_config"] = gt.ThinkingConfig(
                thinking_level="low" if is_pro else "minimal"
            )
        if tools:
            kw["tools"] = tools
            if force_fn:
                kw["tool_config"] = gt.ToolConfig(
                    function_calling_config=gt.FunctionCallingConfig(
                        mode="ANY",
                        allowed_function_names=[force_fn],
                    )
                )
        return gt.GenerateContentConfig(**kw)

    tool_invoked = False
    tool_input = None

    contents = [turn1_msg]

    if tool_turn is not None:
        fn_decl = gt.FunctionDeclaration(
            name=tool_turn["tool_name"],
            description=tool_turn["tool_description"],
            parameters=tool_turn.get("tool_input_schema", {
                "type": "OBJECT",
                "properties": {"query": {"type": "STRING"}},
                "required": ["query"],
            }),
        )
        tools = [gt.Tool(function_declarations=[fn_decl])]
        force = tool_turn["tool_name"] if tool_turn.get("force_tool", True) else None

        r1 = client.models.generate_content(
            model=model_id, contents=contents, config=_cfg(tools, force),
        )
        fc = None
        fc_content = None  # preserve original Content (includes thought_signature for gemini-3.x)
        for cand in (r1.candidates or []):
            for part in (cand.content.parts or []):
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    fc_content = cand.content
                    break
            if fc: break

        if fc is None:
            u = r1.usage_metadata
            return {
                "text1": r1.text or "", "text2": "",
                "input_tokens": (u.prompt_token_count if u else 0) or 0,
                "output_tokens": (u.candidates_token_count if u else 0) or 0,
                "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
                "error": "no_function_call_on_turn1",
            }

        tool_invoked = True
        tool_input = dict(fc.args)

        # Reuse the original model Content so thought_signature is preserved for
        # gemini-3.x (required when thinking is enabled).
        model_turn = fc_content
        tool_result_turn = gt.Content(role="user", parts=[
            gt.Part.from_function_response(
                name=fc.name,
                response={"content": tool_turn["fabricated_tool_result"]},
            )
        ])

        # Note: Gemini 2-turn-after-tool flow uses contents [initial_user, model_turn, tool_result_turn]
        contents_after_tool = [turn1_msg, model_turn, tool_result_turn]
        r2 = client.models.generate_content(
            model=model_id, contents=contents_after_tool, config=_cfg(),
        )
        text1 = (r2.text or "").strip()

        if not turn2_msg:
            u1 = r1.usage_metadata; u2 = r2.usage_metadata
            return {
                "text1": text1, "text2": "",
                "input_tokens": ((u1.prompt_token_count if u1 else 0) or 0) + ((u2.prompt_token_count if u2 else 0) or 0),
                "output_tokens": ((u1.candidates_token_count if u1 else 0) or 0) + ((u2.candidates_token_count if u2 else 0) or 0),
                "model_id": model_id, "tool_invoked": True, "tool_use_input": tool_input,
            }

        # Turn 2: append assistant reply + user turn2
        turn2_contents = contents_after_tool + [
            gt.Content(role="model", parts=[gt.Part(text=text1)]),
            turn2_msg,
        ]
        r3 = client.models.generate_content(
            model=model_id, contents=turn2_contents, config=_cfg(),
        )
        text2 = (r3.text or "").strip()
        u1 = r1.usage_metadata; u2 = r2.usage_metadata; u3 = r3.usage_metadata
        return {
            "text1": text1, "text2": text2,
            "input_tokens": sum(((u.prompt_token_count if u else 0) or 0) for u in (u1, u2, u3)),
            "output_tokens": sum(((u.candidates_token_count if u else 0) or 0) for u in (u1, u2, u3)),
            "model_id": model_id, "tool_invoked": True, "tool_use_input": tool_input,
        }

    # Non-tool path
    r1 = client.models.generate_content(model=model_id, contents=contents, config=_cfg())
    text1 = (r1.text or "").strip()
    if not turn2_msg:
        u = r1.usage_metadata
        return {
            "text1": text1, "text2": "",
            "input_tokens": (u.prompt_token_count if u else 0) or 0,
            "output_tokens": (u.candidates_token_count if u else 0) or 0,
            "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
        }
    turn2_contents = [turn1_msg, gt.Content(role="model", parts=[gt.Part(text=text1)]), turn2_msg]
    r2 = client.models.generate_content(model=model_id, contents=turn2_contents, config=_cfg())
    text2 = (r2.text or "").strip()
    u1 = r1.usage_metadata; u2 = r2.usage_metadata
    return {
        "text1": text1, "text2": text2,
        "input_tokens": ((u1.prompt_token_count if u1 else 0) or 0) + ((u2.prompt_token_count if u2 else 0) or 0),
        "output_tokens": ((u1.candidates_token_count if u1 else 0) or 0) + ((u2.candidates_token_count if u2 else 0) or 0),
        "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
    }


# ============================================================
# Dispatch + retry
# ============================================================

def _openrouter_two_turn(model_id, system_prompt, turn1_msg, turn2_msg,
                          tool_turn=None, max_tokens=1024, temperature=1.0):
    """Same flow as _oai_two_turn but hits OpenRouter's OpenAI-compatible API.
    Note: open-weight models on OpenRouter may not support function-calling
    reliably; tool_turn will degrade to non-tool path on 4xx errors."""
    import openai
    _client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )
    # Monkey-patch the module-level openai client used by _oai_two_turn via a
    # lightweight runner. Simplest: replicate the OAI flow with this client.

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": turn1_msg})

    def _kw(mm, tools=None, tool_choice=None):
        kw = {"model": model_id, "messages": mm, "temperature": temperature,
              "max_tokens": max_tokens}
        if tools:
            kw["tools"] = tools
            if tool_choice: kw["tool_choice"] = tool_choice
        return kw

    tool_invoked = False
    tool_input = None
    text1 = ""

    if tool_turn is not None:
        tools = [{
            "type": "function",
            "function": {
                "name": tool_turn["tool_name"],
                "description": tool_turn["tool_description"],
                "parameters": tool_turn.get("tool_input_schema", {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                }),
            },
        }]
        tool_choice = ({"type": "function", "function": {"name": tool_turn["tool_name"]}}
                        if tool_turn.get("force_tool", True) else "auto")

        try:
            r1 = _client.chat.completions.create(**_kw(messages, tools, tool_choice))
        except Exception as e:
            # Open-weight models often reject forced tool-choice; fall back to
            # auto or no tool. Re-raise if it's a rate limit / capacity error.
            s = str(e).lower()
            if any(w in s for w in ["rate", "429", "overloaded", "quota", "503"]):
                raise
            # Retry with auto tool choice
            try:
                r1 = _client.chat.completions.create(**_kw(messages, tools, "auto"))
            except Exception:
                # Last resort: no tool at all
                r1 = _client.chat.completions.create(**_kw(messages))
        msg1 = r1.choices[0].message
        tool_calls = msg1.tool_calls or []

        if tool_calls:
            tc = tool_calls[0]
            tool_invoked = True
            try:
                tool_input = json.loads(tc.function.arguments or "{}")
            except Exception:
                tool_input = tc.function.arguments
            messages.append({
                "role": "assistant", "content": msg1.content,
                "tool_calls": [{"id": tc.id, "type": "function",
                                 "function": {"name": tc.function.name,
                                              "arguments": tc.function.arguments or "{}"}}],
            })
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": tool_turn["fabricated_tool_result"],
            })
            r2 = _client.chat.completions.create(**_kw(messages, tools))
            text1 = (r2.choices[0].message.content or "").strip()
            messages.append({"role": "assistant", "content": text1})
            if not turn2_msg:
                return {
                    "text1": text1, "text2": "",
                    "input_tokens": (r1.usage.prompt_tokens if r1.usage else 0) + (r2.usage.prompt_tokens if r2.usage else 0),
                    "output_tokens": (r1.usage.completion_tokens if r1.usage else 0) + (r2.usage.completion_tokens if r2.usage else 0),
                    "model_id": model_id, "tool_invoked": True, "tool_use_input": tool_input,
                }
            messages.append({"role": "user", "content": turn2_msg})
            r3 = _client.chat.completions.create(**_kw(messages, tools))
            text2 = (r3.choices[0].message.content or "").strip()
            return {
                "text1": text1, "text2": text2,
                "input_tokens": sum((r.usage.prompt_tokens if r.usage else 0) for r in (r1, r2, r3)),
                "output_tokens": sum((r.usage.completion_tokens if r.usage else 0) for r in (r1, r2, r3)),
                "model_id": model_id, "tool_invoked": True, "tool_use_input": tool_input,
            }
        else:
            # Model didn't call tool; fall back to non-tool path using r1 as the answer
            text1 = (msg1.content or "").strip()
            messages.append({"role": "assistant", "content": text1})
            if not turn2_msg:
                return {
                    "text1": text1, "text2": "",
                    "input_tokens": r1.usage.prompt_tokens if r1.usage else 0,
                    "output_tokens": r1.usage.completion_tokens if r1.usage else 0,
                    "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
                }
            messages.append({"role": "user", "content": turn2_msg})
            r2 = _client.chat.completions.create(**_kw(messages))
            text2 = (r2.choices[0].message.content or "").strip()
            return {
                "text1": text1, "text2": text2,
                "input_tokens": (r1.usage.prompt_tokens if r1.usage else 0) + (r2.usage.prompt_tokens if r2.usage else 0),
                "output_tokens": (r1.usage.completion_tokens if r1.usage else 0) + (r2.usage.completion_tokens if r2.usage else 0),
                "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
            }

    # Non-tool path
    r1 = _client.chat.completions.create(**_kw(messages))
    text1 = (r1.choices[0].message.content or "").strip()
    if not turn2_msg:
        return {
            "text1": text1, "text2": "",
            "input_tokens": r1.usage.prompt_tokens if r1.usage else 0,
            "output_tokens": r1.usage.completion_tokens if r1.usage else 0,
            "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
        }
    messages.append({"role": "assistant", "content": text1})
    messages.append({"role": "user", "content": turn2_msg})
    r2 = _client.chat.completions.create(**_kw(messages))
    text2 = (r2.choices[0].message.content or "").strip()
    return {
        "text1": text1, "text2": text2,
        "input_tokens": (r1.usage.prompt_tokens if r1.usage else 0) + (r2.usage.prompt_tokens if r2.usage else 0),
        "output_tokens": (r1.usage.completion_tokens if r1.usage else 0) + (r2.usage.completion_tokens if r2.usage else 0),
        "model_id": model_id, "tool_invoked": False, "tool_use_input": None,
    }


TWO_TURN = {
    "anthropic": _anth_two_turn,
    "openai": _oai_two_turn,
    "google": _goog_two_turn,
    "openrouter": _openrouter_two_turn,
}


def call_two_turn(model_key, model_cfg, system_prompt,
                    turn1_msg, turn2_msg,
                    tool_turn=None, max_tokens=1024, temperature=1.0):
    fn = TWO_TURN[model_cfg["provider"]]
    return fn(
        model_id=model_cfg["model_id"],
        system_prompt=system_prompt,
        turn1_msg=turn1_msg,
        turn2_msg=turn2_msg,
        tool_turn=tool_turn,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def call_two_turn_retry(model_key, model_cfg, system_prompt,
                          turn1_msg, turn2_msg,
                          tool_turn=None, max_tokens=1024, temperature=1.0):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call_two_turn(
                model_key, model_cfg, system_prompt,
                turn1_msg, turn2_msg, tool_turn, max_tokens, temperature,
            )
        except Exception as e:
            s = str(e).lower()
            retryable = any(w in s for w in ["rate", "429", "overloaded", "529", "too many",
                                              "quota", "resource_exhausted", "capacity", "503"])
            if retryable and attempt < MAX_RETRIES:
                wait = min(2 ** attempt * 3, 60)
                print(f"    [retry {attempt+1}/{MAX_RETRIES}] {type(e).__name__}: waiting {wait}s")
                time.sleep(wait)
            else:
                raise


# ============================================================
# Single-turn convenience (kept for the judge)
# ============================================================

def call_single(model_key, model_cfg, system_prompt, user_msg,
                 max_tokens=256, temperature=0.0):
    """Single-turn, no tools. Used for the judge."""
    r = call_two_turn(
        model_key=model_key, model_cfg=model_cfg,
        system_prompt=system_prompt,
        turn1_msg=user_msg, turn2_msg=None,
        tool_turn=None, max_tokens=max_tokens, temperature=temperature,
    )
    return {
        "text": r["text1"],
        "input_tokens": r["input_tokens"],
        "output_tokens": r["output_tokens"],
        "model_id": r["model_id"],
    }


def call_single_retry(model_key, model_cfg, system_prompt, user_msg,
                        max_tokens=256, temperature=0.0):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call_single(model_key, model_cfg, system_prompt, user_msg,
                                max_tokens, temperature)
        except Exception as e:
            s = str(e).lower()
            retryable = any(w in s for w in ["rate", "429", "overloaded", "529", "too many",
                                              "quota", "resource_exhausted", "capacity", "503"])
            if retryable and attempt < MAX_RETRIES:
                time.sleep(min(2 ** attempt * 3, 60))
            else:
                raise


# ---- Backward-compat shims so judge.py keeps working unchanged ----
def call_model_with_retry(model_key, model_cfg, system_prompt, user_message,
                           max_tokens=256, temperature=0.0, tool_turn=None):
    return call_single_retry(model_key, model_cfg, system_prompt, user_message,
                              max_tokens, temperature)
