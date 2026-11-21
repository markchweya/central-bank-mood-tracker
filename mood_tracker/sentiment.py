"""Classify central bank speech paragraphs with an LLM.

Each paragraph gets two labels:

- stance:  hawkish / dovish / neutral / none   (monetary-policy leaning)
- outlook: positive / negative / neutral / none (view of the economy)

Two backends share one prompt and one output schema:

- OllamaScorer runs a local model through Ollama (default, free, CPU-friendly)
- ClaudeScorer calls the Anthropic API (optional, needs `pip install anthropic`
  and an API key or `ant auth login` profile)
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

STANCE_LABELS = ("hawkish", "dovish", "neutral", "none")
OUTLOOK_LABELS = ("positive", "negative", "neutral", "none")

# Numeric values used when aggregating labels into an index.
STANCE_SCORE = {"hawkish": 1.0, "dovish": -1.0, "neutral": 0.0}
OUTLOOK_SCORE = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}

MAX_PARAGRAPH_CHARS = 2000

# v1: one question, two labels (22% stance accuracy with llama3.2:3b).
# v2: topic first, then leaning, with worked examples. The topic gates the labels,
#     so a paragraph about payments or regulation cannot get a policy stance.
# v3: the single "main topic" choice became two yes/no questions. In v2 both models
#     marked policy-framework paragraphs as off-topic and missed outlooks in paragraphs
#     about risks or crises because those were not "mainly" about growth. Tuned in two
#     rounds on the 60 dev rows only.
PROMPT_VERSION = "v3"

YES_NO = ("yes", "no")

SYSTEM_PROMPT = """You label paragraphs from central bank speeches for an economic research dataset.

Answer four questions.

1. policy: does the paragraph discuss monetary policy? "yes" if it is about interest rates,
   inflation or the inflation target, the policy stance or outlook, policy tools (asset
   purchases, reserves, operations, forward guidance), or how policy is set and explained
   (strategy, framework, communication, independence). "no" for banking supervision,
   regulation, payments, financial inclusion, fintech, climate, history, statistics,
   thanks to hosts or references.

2. stance (only if policy is "yes", otherwise "none"):
- hawkish: argues for higher rates or tighter policy, or warns that inflation is too high or rising.
- dovish: argues for lower rates, looser or accommodative policy, stimulus, or warns that
  inflation is too low, demand is weak, or deflation is a risk.
- neutral: explains or describes policy without arguing for tighter or looser policy.
  Any mention of deflation, weak demand, easing or support for the economy is dovish, not neutral.

3. economy: does the paragraph make a claim about how the economy is doing or where it is
   heading? "yes" when it says growth, output, jobs, demand or trade are strong, weak,
   improving or worsening, or names a crisis, recession, shock or rising risk to the economy,
   even in one sentence. "no" when the economy is only mentioned in passing, or the paragraph
   explains how policy or markets work without saying how the economy is doing.

4. outlook (only if economy is "yes", otherwise "none"):
- positive: growth is solid or improving, conditions are favourable, a recovery is under way.
- negative: growth is weak or falling, a recession, crisis or shock, or risks to growth are rising.
- neutral: mixed or no clear direction.

Judge only what the paragraph says, not what you know about the period."""

# Short invented paragraphs (not taken from the validation set) showing each case.
EXAMPLES = [
    ("Inflation has stayed well above our 2 percent target and wage growth is accelerating. "
     "The Committee therefore judged that a further increase in the policy rate was warranted.",
     {"policy": "yes", "stance": "hawkish", "economy": "no", "outlook": "none"}),
    ("With inflation running below target and unemployment rising, we lowered the policy rate "
     "and will keep monetary conditions accommodative to support the recovery.",
     {"policy": "yes", "stance": "dovish", "economy": "yes", "outlook": "negative"}),
    ("Real GDP grew by 3.1 percent last year, driven by strong exports and household "
     "consumption, and we expect a similar pace this year.",
     {"policy": "no", "stance": "none", "economy": "yes", "outlook": "positive"}),
    ("The new capital requirements will strengthen the resilience of banks, and supervisors "
     "will monitor their implementation closely.",
     {"policy": "no", "stance": "none", "economy": "no", "outlook": "none"}),
    ("Let me thank the organisers for inviting me to this conference on digital payments.",
     {"policy": "no", "stance": "none", "economy": "no", "outlook": "none"}),
    ("Lower interest rates make borrowing cheaper, which supports spending by households and "
     "firms; this is the main channel through which monetary policy affects the economy.",
     {"policy": "yes", "stance": "neutral", "economy": "no", "outlook": "none"}),
    ("Publishing the minutes of our policy meetings helps the public understand how the "
     "Board weighs the arguments, and it makes us accountable for our decisions.",
     {"policy": "yes", "stance": "neutral", "economy": "no", "outlook": "none"}),
    ("Banks have adjusted well to the new rules. Still, an escalation of trade disputes would "
     "hit exports and investment, and that risk has grown in recent months.",
     {"policy": "no", "stance": "none", "economy": "yes", "outlook": "negative"}),
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "policy": {"type": "string", "enum": list(YES_NO)},
        "stance": {"type": "string", "enum": list(STANCE_LABELS)},
        "economy": {"type": "string", "enum": list(YES_NO)},
        "outlook": {"type": "string", "enum": list(OUTLOOK_LABELS)},
    },
    "required": ["policy", "stance", "economy", "outlook"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Label:
    stance: str
    outlook: str


def parse_label(raw: str) -> Label:
    data = json.loads(raw)
    policy, economy = data.get("policy"), data.get("economy")
    stance, outlook = data.get("stance"), data.get("outlook")
    if (policy not in YES_NO or economy not in YES_NO
            or stance not in STANCE_LABELS or outlook not in OUTLOOK_LABELS):
        raise ValueError(f"Unexpected labels in model output: {raw!r}")
    # The yes/no answers gate the labels, whatever the model put in the other fields.
    if policy == "no":
        stance = "none"
    elif stance == "none":
        stance = "neutral"
    if economy == "no":
        outlook = "none"
    elif outlook == "none":
        outlook = "neutral"
    return Label(stance, outlook)


def build_messages(paragraph: str) -> list[dict]:
    messages = []
    for text, answer in EXAMPLES:
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": json.dumps(answer)})
    messages.append({"role": "user", "content": paragraph[:MAX_PARAGRAPH_CHARS]})
    return messages


class OllamaScorer:
    """Score paragraphs with a local Ollama model, using its JSON-schema output mode."""

    backend = "ollama"

    def __init__(self, model: str = "llama3.2:3b", host: str = "http://localhost:11434"):
        self.model = model
        self.url = f"{host.rstrip('/')}/api/chat"

    def score(self, paragraph: str) -> Label:
        body = {
            "model": self.model,
            "stream": False,
            "format": OUTPUT_SCHEMA,
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *build_messages(paragraph)],
        }
        request = urllib.request.Request(
            self.url, json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        # Larger models now and then return an empty or cut-off reply; one retry
        # usually fixes it. A second bad reply raises ValueError for the caller.
        for attempt in range(2):
            with urllib.request.urlopen(request, timeout=300) as response:
                reply = json.load(response)
            try:
                return parse_label(reply["message"]["content"])
            except ValueError:
                if attempt == 1:
                    raise


class ClaudeScorer:
    """Score paragraphs with Claude through the Anthropic API, using structured outputs."""

    backend = "claude"

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "low"):
        import anthropic  # optional dependency, only needed for this backend

        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort

    def score(self, paragraph: str) -> Label:
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
            # If a safety classifier declines, the API retries on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=build_messages(paragraph),
        )
        if response.stop_reason == "refusal":
            raise ValueError("Model declined to label this paragraph")
        text = next(block.text for block in response.content if block.type == "text")
        return parse_label(text)


def make_scorer(backend: str, model: str | None = None):
    if backend == "ollama":
        return OllamaScorer(model or "llama3.2:3b")
    if backend == "claude":
        return ClaudeScorer(model or "claude-opus-5-5")
    raise ValueError(f"Unknown backend {backend!r}; use 'ollama' or 'claude'")
