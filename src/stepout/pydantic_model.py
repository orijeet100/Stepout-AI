"""PydanticModel: the Model port on Pydantic AI's model layer, so any provider it speaks (OpenRouter, OpenAI, Gemini, a local server...) can play a Role.

Same contract as `AnthropicModel`: one request in, one Action out, no transcript. Only the provider call changes (`pydantic_ai.direct.model_request`,
which is one request and no agent loop), so the Runner, the Gate and the Roles do not know which provider answered.

A Role's `model` is a logical id (`roles.SONNET`, `roles.HAIKU`). `targets` says what runs behind it; an id not listed runs as itself on Anthropic.
"""

from __future__ import annotations

import os
from typing import Mapping

from pydantic import ValidationError
from pydantic_ai import ToolDefinition, WebSearchTool, direct
from pydantic_ai import messages as pai
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior, UserError
from pydantic_ai.models import Model as PaiModel
from pydantic_ai.models import ModelRequestParameters, infer_model

from stepout import capabilities
from stepout.domain import AnswerAction
from stepout.failure import Failure
from stepout.model import PRICING, WEB_SEARCH_COST_PER_USE, AnthropicModel, ModelRequest, ModelResponse, call_to_action, client_tools
from stepout.roles import HAIKU, SONNET

# Which environment variable holds the key for each provider prefix of a model string ("openrouter:openai/gpt-5.2").
_KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "google-gla": "GEMINI_API_KEY"}
# The two tiers a User can re-point. "strong" runs the Orchestrator and the Web Browsing agent, "cheap" Screening and the other specialists.
_TIER_VARS = ((SONNET, "STEPOUT_STRONG_MODEL"), (HAIKU, "STEPOUT_CHEAP_MODEL"))


def from_env(environ: Mapping[str, str] = os.environ) -> PydanticModel | None:
    """A PydanticModel if STEPOUT_STRONG_MODEL or STEPOUT_CHEAP_MODEL is set (a Pydantic AI model string such as `openrouter:openai/gpt-5.2`), else None."""
    targets = {logical: value for logical, var in _TIER_VARS if (value := environ.get(var, "").strip())}
    return PydanticModel(targets) if targets else None


def default_model(environ: Mapping[str, str] = os.environ) -> AnthropicModel | PydanticModel:
    """The model the app runs: the Anthropic adapter unless a tier is re-pointed in the environment. One place, so the app and the acceptance script agree."""
    return from_env(environ) or AnthropicModel()


class PydanticModel:
    def __init__(self, targets: Mapping[str, str | PaiModel] | None = None) -> None:
        self._targets = dict(targets or {})
        self._built: dict[str, PaiModel] = {}

    def target(self, logical: str) -> str | PaiModel:
        return self._targets.get(logical, f"anthropic:{logical}")

    def key_vars(self) -> list[str]:
        """The environment variables the two tiers need, for the start-up check."""
        prefixes = [t.split(":", 1)[0] for logical in (SONNET, HAIKU) if isinstance(t := self.target(logical), str) and ":" in t]
        return sorted({_KEY_VARS[p] for p in prefixes if p in _KEY_VARS})

    def _model(self, logical: str) -> PaiModel:
        if logical not in self._built:
            target = self.target(logical)
            try:
                self._built[logical] = infer_model(target) if isinstance(target, str) else target
            except UserError as exc:  # the provider's key (or package) is missing
                raise _explain(exc) from exc
        return self._built[logical]

    async def call(self, request: ModelRequest) -> ModelResponse:
        model = self._model(request.model)
        functions = [
            ToolDefinition(
                name=t["name"], description=t.get("description"), parameters_json_schema=t["input_schema"],
                metadata={"reaches_web": bool((cap := capabilities.get(t["name"])) and cap.reaches_web)},  # for a Gate hook, once the loop moves
            )
            for t in client_tools(request)
        ]
        native = []
        if request.search and request.max_searches > 0:
            if WebSearchTool not in type(model).supported_native_tools():  # answering "from a search" without one would be made up
                raise Failure("no_search", f"The model provider behind {request.model} cannot search the web, so a search cannot run on it. Pick a model that can, or ask without it.")
            native.append(WebSearchTool(max_uses=request.max_searches))
        settings = {"max_tokens": 4096, "parallel_tool_calls": False}  # one Action per turn: the Runner runs one, so a second call would be dropped silently
        if request.temperature is not None:  # never send null: only set it when asked
            settings["temperature"] = request.temperature
        messages = [pai.ModelRequest(parts=[pai.SystemPromptPart(request.system), pai.UserPromptPart(request.user_text)])]
        try:
            response = await direct.model_request(
                model, messages, model_settings=settings,
                model_request_parameters=ModelRequestParameters(function_tools=functions, native_tools=native, allow_text_output=True),
            )
        except (ModelAPIError, UnexpectedModelBehavior, UserError) as exc:
            raise _explain(exc) from exc
        try:
            calls = [p for p in response.parts if isinstance(p, pai.ToolCallPart)]
            action = call_to_action(calls[0].tool_name, calls[0].args_as_dict(), frozenset(d["name"] for d in request.tool_defs)) if calls else None
            if action is None:  # no tool call, or one we did not offer: the words are the answer
                action = AnswerAction(text="".join(p.content for p in response.parts if isinstance(p, pai.TextPart)))
            searches = sum(1 for p in response.parts if isinstance(p, pai.NativeToolCallPart) and p.tool_name == WebSearchTool.kind)
            return ModelResponse(action=action, cost_usd=self._cost(request.model, response, searches), searches=searches)
        except (AttributeError, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise Failure("malformed", "The model's reply could not be understood. Try again; if it repeats, tell the developer.") from exc

    def _cost(self, logical: str, response: pai.ModelResponse, searches: int) -> float:
        usage = response.usage
        if logical in PRICING and self.target(logical) == f"anthropic:{logical}":  # the default route keeps the Anthropic adapter's table, so the two agree to the cent
            rate_in, rate_out = PRICING[logical]
            return usage.input_tokens * rate_in / 1_000_000 + usage.output_tokens * rate_out / 1_000_000 + searches * WEB_SEARCH_COST_PER_USE
        try:  # ponytail: a search is priced at Anthropic's rate whatever the provider charges, until search is a client tool
            return float(response.cost().total_price) + searches * WEB_SEARCH_COST_PER_USE
        except LookupError as exc:  # an unknown price must not read as free: the $1 cap would never trip
            raise Failure("pricing", f"No price is known for {response.model_name}, so the spending cap could not be enforced. Pick a model with a published price.") from exc


def _explain(exc: Exception) -> Failure:
    """The provider said no, or could not be reached: one line for the User and the cause for the Ledger."""
    match exc:
        case UserError():
            return Failure("no_key", f"A model provider is not set up ({str(exc).strip()}). Put its API key in the .env file (copy .env.example), then restart the app.")
        case ModelHTTPError(status_code=401 | 403 as status):
            return Failure("auth", f"The model provider rejected the API key ({status}). Check the key in the .env file, then restart the app.", status)
        case ModelHTTPError(status_code=402 as status):
            return Failure("credit", "Your model provider account is out of credit. Add credit with the provider, then try again.", status)
        case ModelHTTPError(status_code=429 as status):
            return Failure("rate_limit", f"The model provider is rate-limiting requests right now ({status}). Wait a minute, then send it again.", status)
        case ModelHTTPError(status_code=status) if "credit balance" in str(exc.body).lower():
            return Failure("credit", "Your model provider account is out of credit. Add credit with the provider, then try again.", status)
        case ModelHTTPError(status_code=status) if status >= 500:
            return Failure("server_error", f"The model provider had a server error ({status}). Try again in a minute.", status)
        case ModelHTTPError(status_code=status):
            return Failure("rejected", f"The model provider rejected the request ({status}). Try again; if it repeats, tell the developer.", status)
        case UnexpectedModelBehavior():
            return Failure("malformed", "The model's reply could not be understood. Try again; if it repeats, tell the developer.")
        case _:  # ModelAPIError that is not an HTTP status: a timeout or a connection that failed
            return Failure("connection", "Could not reach the model provider. Check your internet connection, then try again.")
