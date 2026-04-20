import itertools
import json
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from django.db.models import Q


PROJECT_DIR = Path(__file__).resolve().parent

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from products.models import Product


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost")
OPENROUTER_X_TITLE = os.getenv("OPENROUTER_X_TITLE", "BDPriceGear Terminal Chatbot")

COMPONENT_BY_CATEGORY = {
    "Processor": "cpu",
    "CPU": "cpu",
    "Motherboard": "motherboard",
    "RAM": "ram",
    "SSD": "storage",
    "HDD": "storage",
    "GPU": "gpu",
    "Power Supply": "psu",
    "Cabinet": "case",
}

PRODUCT_CATEGORY_FILTERS = {
    "cpu": ["Processor", "CPU"],
    "gpu": ["GPU"],
    "motherboard": ["Motherboard"],
    "ram": ["RAM"],
    "storage": ["SSD", "HDD"],
    "psu": ["Power Supply"],
    "case": ["Cabinet"],
}


@dataclass
class ProductRow:
    id: int
    name: str
    category_name: str
    current_price: Decimal
    stock_status: str
    is_available: bool
    product_url: str
    shop_name: str


def parse_budget_bdt(text: str) -> Optional[int]:
    lowered = text.lower()

    preferred_patterns = [
        r"under\s*(\d+(?:[\.,]\d+)?)\s*(k)?\s*(?:bdt|tk|taka)?",
        r"budget\s*(?:of|is|=)?\s*(\d+(?:[\.,]\d+)?)\s*(k)?\s*(?:bdt|tk|taka)?",
        r"(\d+(?:[\.,]\d+)?)\s*(k)\b",
        r"(\d+(?:[\.,]\d+)?)\s*(?:bdt|tk|taka)\b",
    ]

    for pattern in preferred_patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        raw_value = match.group(1).replace(",", "")
        value = float(raw_value)
        has_k = len(match.groups()) >= 2 and bool(match.group(2))
        if has_k:
            value *= 1000
        if value > 0:
            return int(value)

    # Conservative fallback for plain numeric budgets like "build pc 50000".
    # Avoid matching model numbers such as "i5-11400f" by requiring non-word/hyphen boundaries.
    fallback = re.search(r"(?<![a-z0-9-])(\d{4,7})(?![a-z0-9-])", lowered)
    if fallback:
        return int(fallback.group(1))
    return None


def parse_budget_range_bdt(text: str) -> Tuple[Optional[int], Optional[int]]:
    lowered = text.lower()

    range_match = re.search(
        r"(\d+(?:[\.,]\d+)?)\s*(k)?\s*(?:-|to)\s*(\d+(?:[\.,]\d+)?)\s*(k)?\s*(?:bdt|tk|taka)?",
        lowered,
    )
    if range_match:
        left = float(range_match.group(1).replace(",", ""))
        right = float(range_match.group(3).replace(",", ""))
        left_has_k = bool(range_match.group(2))
        right_has_k = bool(range_match.group(4))
        
        # If either side has 'k', treat both as thousands (e.g., "10-15k" means "10k-15k")
        if left_has_k or right_has_k:
            left *= 1000
            right *= 1000
        
        low = int(min(left, right))
        high = int(max(left, right))
        return low, high

    around_match = re.search(r"around\s*(\d+(?:[\.,]\d+)?)\s*(k)?\s*(?:bdt|tk|taka)?", lowered)
    if around_match:
        value = float(around_match.group(1).replace(",", ""))
        if around_match.group(2):
            value *= 1000
        center = int(value)
        return int(center * 0.9), int(center * 1.1)

    return None, None


def parse_component_price_constraints(text: str) -> Dict[str, Tuple[int, int]]:
    lowered = text.lower()
    constraints: Dict[str, Tuple[int, int]] = {}

    component_keywords = {
        "cpu": ["cpu", "processor", "intel processor", "amd processor"],
        "gpu": ["gpu", "graphics card", "vga"],
        "ram": ["ram", "memory"],
        "storage": ["ssd", "hdd", "storage"],
        "motherboard": ["motherboard", "mainboard"],
        "psu": ["psu", "power supply"],
        "case": ["case", "cabinet", "casing"],
    }

    range_patterns = [
        r"(\d+(?:[\.,]\d+)?)\s*(k)?\s*(?:-|to)\s*(\d+(?:[\.,]\d+)?)\s*(k)?",
        r"between\s*(\d+(?:[\.,]\d+)?)\s*(k)?\s*(?:and)\s*(\d+(?:[\.,]\d+)?)\s*(k)?",
        r"around\s*(\d+(?:[\.,]\d+)?)\s*(k)?",
    ]

    for component, keywords in component_keywords.items():
        if not any(keyword in lowered for keyword in keywords):
            continue

        min_price: Optional[int] = None
        max_price: Optional[int] = None

        range_match = re.search(range_patterns[0], lowered) or re.search(range_patterns[1], lowered)
        if range_match:
            left = float(range_match.group(1).replace(",", ""))
            right = float(range_match.group(3).replace(",", ""))
            left_has_k = bool(range_match.group(2))
            right_has_k = bool(range_match.group(4))
            if left_has_k or right_has_k:
                left *= 1000
                right *= 1000
            min_price = int(min(left, right))
            max_price = int(max(left, right))
        else:
            around_match = re.search(range_patterns[2], lowered)
            if around_match:
                center = float(around_match.group(1).replace(",", ""))
                if around_match.group(2):
                    center *= 1000
                min_price = int(center * 0.9)
                max_price = int(center * 1.1)

        if min_price is not None and max_price is not None:
            constraints[component] = (min_price, max_price)

    return constraints


def detect_component_intent(text: str) -> Optional[str]:
    lowered = text.lower()

    component_aliases = {
        "cpu": ["cpu", "processor", "intel", "ryzen", "amd processor"],
        "gpu": ["gpu", "graphics card", "vga", "rtx", "gtx", "radeon"],
        "motherboard": ["motherboard", "mainboard"],
        "ram": ["ram", "memory", "ddr4", "ddr5"],
        "storage": ["ssd", "hdd", "storage", "nvme", "hard drive", "hard disk"],
        "psu": ["psu", "power supply"],
        "case": ["case", "cabinet", "casing", "chassis"],
    }

    for component, aliases in component_aliases.items():
        if any(alias in lowered for alias in aliases):
            return component
    return None


def detect_brand_intent(text: str) -> Optional[str]:
    lowered = text.lower()
    if "intel" in lowered:
        return "intel"
    if "ryzen" in lowered or "amd" in lowered:
        return "amd"
    if any(token in lowered for token in ["nvidia", "geforce", "rtx", "gtx"]):
        return "nvidia"
    if any(token in lowered for token in ["radeon", "amd gpu"]):
        return "radeon"
    return None


def is_product_lookup_request(text: str) -> bool:
    if is_build_request(text):
        return False

    lowered = text.lower()
    component_detected = detect_component_intent(text) is not None
    min_budget, max_budget = parse_budget_range_bdt(text)
    single_budget = parse_budget_bdt(text)

    if not component_detected:
        return False

    # Advisory/planning questions should stay in general chat mode.
    advisory_terms = ["allocation", "percentage", "%", "breakdown", "distribution", "split", "plan"]
    if "budget" in lowered and any(term in lowered for term in advisory_terms):
        return False

    # Negative preference statements like "I don't want a GPU" are usually intent
    # to modify a build or ask advice, not product lookup.
    negative_preference_terms = ["dont want", "don't want", "do not want", "without"]
    if any(term in lowered for term in negative_preference_terms):
        explicit_shopping_terms = ["show", "list", "suggest", "recommend", "buy", "available", "price", "cheapest", "lowest"]
        if not any(term in lowered for term in explicit_shopping_terms):
            return False

    # Explicit component + budget-range requests should count as lookup intent even without
    # classic lookup words like 'suggest' or 'cheapest'.
    if min_budget is not None or max_budget is not None:
        return True

    if single_budget and any(token in lowered for token in ["around", "under", "within", "between", "budget", "tk", "bdt", "taka"]):
        return True

    query_terms = [
        "suggest",
        "recommend",
        "recommended",
        "recommendation",
        "cheapest",
        "lowest",
        "low cost",
        "budget",
        "budget friendly",
        "value for money",
        "expensive",
        "most expensive",
        "costly",
        "highest",
        "high price",
        "premium",
        "high end",
        "top end",
        "flagship",
        "best one",
        "best option",
        "best",
        "price",
        "pricing",
        "cost",
        "buy",
        "purchase",
        "get",
        "available",
        "in stock",
        "stock",
        "have",
        "do you have",
        "show me",
        "show",
        "list",
        "give me",
        "find",
        "search",
        "looking for",
        "options",
        "choices",
        "models",
        "within",
        "between",
        "range",
        "around",
        "under",
        "over",
        "above",
    ]

    return any(term in lowered for term in query_terms)


def parse_lookup_result_limit(text: str, default_limit: int = 3, max_limit: int = 10) -> int:
    """Extract requested result count from lookup prompts like 'top 5 cpu'."""
    lowered = text.lower()

    patterns = [
        r"\btop\s+(\d{1,2})\b",
        r"\b(?:show|list|give(?:\s+me)?|need|want|send)\s+(?:me\s+)?(\d{1,2})\b",
        r"\b(\d{1,2})\s+(?:cpu|cpus|processor|processors|gpu|gpus|ram|ssd|hdd|items|options|products)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        requested = int(match.group(1))
        if requested > 0:
            return max(1, min(requested, max_limit))

    return default_limit


def is_lookup_next_request(text: str) -> bool:
    lowered = text.lower()
    # Avoid treating CPU generation phrases like "next gen" as pagination.
    if "next gen" in lowered or "next generation" in lowered:
        return False
    return any(token in lowered for token in ["next", "more", "next page", "more options"])


def detect_lookup_mode(text: str) -> Optional[str]:
    lowered = text.lower()
    if any(token in lowered for token in ["cheapest", "lowest", "low price"]):
        return "cheapest"
    if any(token in lowered for token in ["expensive", "most expensive", "costly", "highest", "high price"]):
        return "expensive"
    if any(token in lowered for token in ["best", "top", "high end", "premium"]):
        return "best"
    return None


def product_lookup_response(
    user_input: str,
    context_component: Optional[str] = None,
    context_brand: Optional[str] = None,
    context_mode: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = None,
) -> Optional[str]:
    component = detect_component_intent(user_input) or context_component
    if not component:
        return None

    category_filters = PRODUCT_CATEGORY_FILTERS.get(component, [])
    if not category_filters:
        return None

    lowered = user_input.lower()
    brand = detect_brand_intent(user_input) or context_brand
    mode_hint = detect_lookup_mode(user_input) or context_mode
    cheapest_mode = mode_hint == "cheapest"
    expensive_mode = mode_hint == "expensive"
    best_mode = mode_hint == "best" or expensive_mode
    result_limit = limit if isinstance(limit, int) and limit > 0 else parse_lookup_result_limit(user_input)
    page_offset = max(0, int(offset))
    min_budget, max_budget = parse_budget_range_bdt(user_input)

    # Follow-up budget-only message like "around 10k".
    if min_budget is None and max_budget is None:
        single_budget = parse_budget_bdt(user_input)
        if single_budget and any(token in lowered for token in ["around", "under", "budget", "tk", "bdt", "taka"]):
            if "under" in lowered:
                min_budget, max_budget = 0, single_budget
            else:
                min_budget, max_budget = int(single_budget * 0.9), int(single_budget * 1.1)

    queryset = Product.objects.select_related("shop", "category").filter(
        category__name__in=category_filters,
        is_available=True,
        stock_status="in_stock",
    )

    if brand == "intel":
        queryset = queryset.filter(name__icontains="intel")
    elif brand == "amd":
        queryset = queryset.filter(Q(name__icontains="amd") | Q(name__icontains="ryzen"))
    elif brand == "nvidia":
        queryset = queryset.filter(
            Q(name__icontains="nvidia")
            | Q(name__icontains="geforce")
            | Q(name__icontains="rtx")
            | Q(name__icontains="gtx")
        )
    elif brand == "radeon":
        queryset = queryset.filter(Q(name__icontains="radeon") | Q(name__icontains="amd"))

    if min_budget is not None:
        queryset = queryset.filter(current_price__gte=min_budget)
    if max_budget is not None:
        queryset = queryset.filter(current_price__lte=max_budget)

    if component == "storage":
        queryset = queryset.exclude(
            Q(name__icontains="adapter")
            | Q(name__icontains="enclosure")
            | Q(name__icontains="expansion card")
            | Q(name__icontains="caddy")
            | Q(name__icontains="dock")
        )
    if component == "cpu":
        cpu_include_terms = ["intel", "ryzen", "threadripper", "xeon", "processor", "cpu", "core i", "pentium", "celeron", "athlon"]
        queryset = queryset.exclude(
            Q(name__icontains="cooler")
            | Q(name__icontains="fan")
            | Q(name__icontains="thermal paste")
            | Q(name__icontains="bracket")
            | Q(name__icontains="holder")
            | Q(name__icontains="mount")
            | Q(name__icontains="router")
            | Q(name__icontains="mac studio")
            | Q(name__icontains="mac mini")
            | Q(name__icontains="laptop")
            | Q(name__icontains="notebook")
            | Q(name__icontains="all-in-one")
            | Q(name__icontains="panel")
            | Q(name__icontains="monitor")
            | Q(name__icontains="tv")
        )
        cpu_name_filter = Q()
        for term in cpu_include_terms:
            cpu_name_filter |= Q(name__icontains=term)
        queryset = queryset.filter(cpu_name_filter)
    if component == "gpu":
        queryset = queryset.exclude(
            Q(name__icontains="holder")
            | Q(name__icontains="stand")
            | Q(name__icontains="support")
            | Q(name__icontains="bracket")
            | Q(name__icontains="mount")
            | Q(name__icontains="riser")
            | Q(name__icontains="vertical kit")
            | Q(name__icontains="extender")
            | Q(name__icontains="cable")
        )

    if best_mode and not cheapest_mode:
        rows = list(queryset.order_by("-current_price", "name")[page_offset:page_offset + result_limit])
    elif cheapest_mode:
        rows = list(queryset.order_by("current_price", "name")[page_offset:page_offset + result_limit])
    else:
        rows = list(queryset.order_by("current_price", "name")[page_offset:page_offset + result_limit])

    if not rows:
        if page_offset > 0:
            return f"I could not find more in-stock {component.upper()} products for that request in your database."
        wanted = f" {brand.upper()}" if brand else ""
        budget_text = ""
        if min_budget is not None or max_budget is not None:
            lo = f"{min_budget}" if min_budget is not None else "0"
            hi = f"{max_budget}" if max_budget is not None else "any"
            budget_text = f" within {lo}-{hi} BDT"
        return f"I could not find any in-stock{wanted} {component.upper()} products{budget_text} in your database right now."

    if cheapest_mode:
        title = f"Cheapest in-stock {brand.upper() + ' ' if brand else ''}{component.upper()} I found:"
    elif expensive_mode:
        title = f"Most expensive in-stock {brand.upper() + ' ' if brand else ''}{component.upper()} I found:"
    elif best_mode:
        title = f"Top in-stock {brand.upper() + ' ' if brand else ''}{component.upper()} options from your database:"
    else:
        title = f"Here are in-stock {brand.upper() + ' ' if brand else ''}{component.upper()} options from your database:"

    lines = [title]
    for idx, row in enumerate(rows, start=page_offset + 1):
        shop_name = row.shop.name if getattr(row, "shop", None) else "N/A"
        price_text = f"{int(Decimal(str(row.current_price)))} BDT"
        link_text = row.product_url or "N/A"
        lines.append(f"{idx}. {row.name} - {price_text} ({shop_name})")
        lines.append(f"   Link: {link_text}")

    return "\n".join(lines)


def is_product_lookup_followup_request(text: str, has_lookup_context: bool) -> bool:
    if not has_lookup_context:
        return False

    lowered = text.lower()
    if any(token in lowered for token in ["build", "pc build", "rebuild", "full build"]):
        return False

    # Keep advisory budgeting questions in general chat mode.
    advisory_terms = ["allocation", "percentage", "%", "breakdown", "distribution", "split", "plan"]
    if "budget" in lowered and any(term in lowered for term in advisory_terms):
        return False

    # Check for budget-based followups (e.g., "around 10k", "under 20k")
    min_budget, max_budget = parse_budget_range_bdt(text)
    if min_budget is not None or max_budget is not None:
        return True

    single_budget = parse_budget_bdt(text)
    if single_budget and any(token in lowered for token in ["around", "under", "budget", "tk", "bdt", "taka"]):
        return True

    # Allow brand-preference followups that rely on prior lookup context,
    # e.g. "i want intel instead of amd".
    brand_followup_terms = [
        "instead of",
        "rather than",
        "switch to",
        "change to",
        "i want intel",
        "want intel",
        "need intel",
        "prefer intel",
        "i want amd",
        "want amd",
        "need amd",
        "prefer amd",
        "nvidia instead",
        "amd instead",
    ]
    if any(term in lowered for term in brand_followup_terms):
        return True

    # Check for generic product lookup continuations (e.g., "any specific processor", "show me options")
    # These indicate the user is continuing the product lookup within existing context
    lookup_continuation_terms = [
        "any", "specific", "other", "different", "more", "next",  # Selection requests
        "show", "options", "recommendations", "suggest",  # Display requests
        "which",  # Question continuations
        "details", "info", "information",  # Info requests
        "available", "stock",  # Availability checks
        "price", "cost",  # Price refinements
    ]
    if any(term in lowered for term in lookup_continuation_terms):
        return True

    return False


def is_build_request(text: str) -> bool:
    lowered = text.lower()
    budget = parse_budget_bdt(text)
    if (
        ("build" in lowered and "pc" in lowered)
        or ("build" in lowered and budget is not None)
        or "gaming pc" in lowered
    ):
        return True

    # Handle natural phrasing like "recommend a PC with 16GB RAM, 512GB SSD, 1TB HDD around 70k"
    # that may not explicitly include the word "build".
    system_terms = [" pc", "computer", "desktop"]
    mentions_system = any(term in lowered for term in system_terms)
    if not mentions_system:
        return False

    capacity_requirements = parse_build_capacity_requirements(text)

    # Count distinct component classes referenced to distinguish full-build requests
    # from single-component shopping queries like "pc case under 5k".
    component_classes = {
        "cpu": ["cpu", "processor", "intel", "amd", "ryzen", "core i"],
        "motherboard": ["motherboard", "mainboard"],
        "ram": ["ram", "memory", "ddr4", "ddr5"],
        "storage": ["ssd", "hdd", "nvme", "hard disk", "hard drive", "storage"],
        "gpu": ["gpu", "graphics card", "vga", "rtx", "gtx", "radeon"],
        "psu": ["psu", "power supply"],
        "case": ["case", "cabinet", "casing", "chassis"],
    }
    mentioned_classes = 0
    for terms in component_classes.values():
        if any(term in lowered for term in terms):
            mentioned_classes += 1

    has_build_like_detail = bool(capacity_requirements) or mentioned_classes >= 2
    has_build_like_budget = parse_total_build_budget(text) is not None
    has_build_request_terms = any(term in lowered for term in ["recommend", "suggest", "configuration", "setup"])

    if has_build_like_detail and (has_build_like_budget or has_build_request_terms):
        return True

    return False


def is_db_only_commerce_query(text: str) -> bool:
    """Detect product/build shopping queries that must never go to generic LLM replies."""
    lowered = text.lower()

    component_terms = [
        "cpu", "processor", "gpu", "graphics card", "vga", "motherboard", "ram", "memory",
        "ssd", "hdd", "storage", "psu", "power supply", "case", "cabinet", "casing",
    ]
    build_terms = ["build", "pc", "computer", "desktop", "configuration", "setup"]
    shopping_terms = [
        "product", "products", "price", "shop", "link", "buy", "available", "stock",
        "recommend", "suggest", "cheapest", "lowest", "best", "under", "around", "between",
        "budget", "bdt", "tk", "taka",
    ]

    has_hardware_context = any(term in lowered for term in component_terms + build_terms)
    has_shopping_context = any(term in lowered for term in shopping_terms)
    return has_hardware_context and has_shopping_context


def is_pc_domain_general_question(text: str) -> bool:
    """Allow general chat only when the question is still about PC parts, gaming, or builds."""
    lowered = text.lower()
    allowed_terms = [
        "pc", "computer", "desktop", "laptop", "gaming", "build", "builds",
        "cpu", "processor", "gpu", "graphics card", "motherboard", "ram",
        "memory", "ssd", "hdd", "storage", "psu", "power supply", "case",
        "cabinet", "casing", "monitor", "keyboard", "mouse", "cooler",
        "fan", "thermal paste", "fps", "bottleneck", "overclock", "upgrade",
    ]
    return any(term in lowered for term in allowed_terms)


def out_of_scope_pc_redirect_response() -> str:
    """Friendly response for topics outside PC/gaming scope."""
    return (
        "I cannot help with that topic, but I can chat normally about PC and gaming topics. "
        "Tell me your budget or use-case, and I can suggest parts or a full build."
    )


def small_talk_response(text: str) -> Optional[str]:
    """Handle casual greetings/chitchat while keeping factual off-topic QA blocked."""
    lowered = text.lower().strip()

    if lowered in {"hi", "hello", "hey", "yo", "sup", "assalamu alaikum", "salam"}:
        return "Hey! I am good. Tell me what you want for your PC or gaming setup."

    if any(phrase in lowered for phrase in ["how are you", "how are u", "kemon aso", "kemon acho"]):
        return "I am doing great. Ready to help with your PC build, parts, or gaming setup."

    if any(phrase in lowered for phrase in ["thanks", "thank you", "thx", "ty"]):
        return "You are welcome. If you want, I can suggest a build based on your budget."

    if any(phrase in lowered for phrase in ["good morning", "good afternoon", "good evening", "good night"]):
        return "Hello! Share your budget or use-case and I will help with a solid PC setup."

    return None


def is_minimum_budget_build_request(text: str) -> bool:
    lowered = text.lower()
    min_tokens = ["minimum", "min", "lowest", "least"]
    budget_tokens = ["budget", "cost", "price"]
    build_tokens = ["build", "pc", "computer"]
    return (
        any(token in lowered for token in min_tokens)
        and any(token in lowered for token in budget_tokens)
        and any(token in lowered for token in build_tokens)
    )


def parse_total_build_budget(text: str) -> Optional[int]:
    """Extract total system budget. For ranges, prefer upper bound (e.g. 30k-35k -> 35k)."""
    lowered = text.lower()
    single = parse_budget_bdt(text)
    low, high = parse_budget_range_bdt(text)

    has_budget_cue = any(
        cue in lowered for cue in ["budget", "total", "overall", "under", "build", "pc", "between", "range"]
    )

    if low is not None and high is not None and has_budget_cue:
        return high
    return single


def is_hard_cap_budget_request(text: str) -> bool:
    lowered = text.lower()
    cap_terms = ["under", "less than", "within", "max", "at most", "upto", "up to"]
    return any(term in lowered for term in cap_terms)


def is_no_budget_followup(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in [
            "no budget",
            "dont have a budget",
            "don't have a budget",
            "do not have a budget",
            "without budget",
            "no fixed budget",
            "budget not fixed",
            "budget is not fixed",
            "budget not fix",
            "budget is not fix",
            "not fixed budget",
            "flexible budget",
            "budget is flexible",
            "budget flexible",
        ]
    )


def is_build_continue_request(text: str) -> bool:
    lowered = text.lower().strip()
    continue_phrases = [
        "just give me build",
        "give me build",
        "just build",
        "give build",
        "proceed with build",
        "continue build",
        "just give me a build",
        "give me a build",
    ]
    return any(phrase in lowered for phrase in continue_phrases)


def is_build_budget_adjustment_request(text: str) -> bool:
    lowered = text.lower().strip()
    phrases = [
        "increase budget",
        "increase the budget",
        "higher budget",
        "raise budget",
        "raise the budget",
        "change budget",
        "new budget",
        "update budget",
        "reduce budget",
        "lower budget",
        "decrease budget",
        "budget increase",
    ]
    return any(phrase in lowered for phrase in phrases)


def parse_build_capacity_requirements(text: str) -> Dict[str, int]:
    lowered = text.lower()
    requirements: Dict[str, int] = {}

    ram_match = re.search(r"(\d+)\s*gb\s*ram", lowered)
    if ram_match:
        requirements["ram_gb"] = int(ram_match.group(1))

    ssd_gb_match = re.search(r"(\d+)\s*gb\s*ssd", lowered)
    ssd_tb_match = re.search(r"(\d+(?:\.\d+)?)\s*tb\s*ssd", lowered)
    if ssd_tb_match:
        requirements["ssd_gb"] = int(float(ssd_tb_match.group(1)) * 1000)
    elif ssd_gb_match:
        requirements["ssd_gb"] = int(ssd_gb_match.group(1))

    hdd_gb_match = re.search(r"(\d+)\s*gb\s*hdd", lowered)
    hdd_tb_match = re.search(r"(\d+(?:\.\d+)?)\s*tb\s*hdd", lowered)
    if hdd_tb_match:
        requirements["hdd_gb"] = int(float(hdd_tb_match.group(1)) * 1000)
    elif hdd_gb_match:
        requirements["hdd_gb"] = int(hdd_gb_match.group(1))

    return requirements


def estimate_minimum_build_budget_response(user_input: str) -> str:
    """Estimate the minimum feasible build budget from in-stock parts."""
    prefs = parse_build_preferences(user_input)
    requirements = parse_build_capacity_requirements(user_input)

    cpu_pool = fetch_candidates(["Processor", "CPU"], limit=24, preferences=prefs)
    if prefs.get("cpu_brand") == "intel":
        cpu_pool = [item for item in cpu_pool if "intel" in item.name.lower()]
    elif prefs.get("cpu_brand") == "amd":
        cpu_pool = [item for item in cpu_pool if ("amd" in item.name.lower() or "ryzen" in item.name.lower())]

    if not cpu_pool:
        return "I could not find any in-stock CPU options matching your preference to estimate a minimum budget."

    cpu = min(cpu_pool, key=lambda item: Decimal(str(item.current_price)))

    mb_pool = fetch_candidates(["Motherboard"], limit=36, preferences=prefs)
    mb_pool = [item for item in mb_pool if is_cpu_motherboard_compatible(cpu.name, item.name)]

    ram_pool = fetch_candidates(["RAM"], limit=24, preferences=prefs)
    required_ram = max(requirements.get("ram_gb", 0), 8)
    ram_pool = [item for item in ram_pool if parse_ram_capacity_gb(item.name) >= required_ram]

    storage_pool = fetch_candidates(["SSD", "HDD"], limit=36, preferences=prefs)
    storage_pool = [
        item for item in storage_pool
        if not any(token in item.name.lower() for token in ["adapter", "enclosure", "caddy", "dock", "external", "usb", "hdd box", "ssd box", "drive box"])
    ]

    required_ssd = requirements.get("ssd_gb", 0)
    required_hdd = requirements.get("hdd_gb", 0)
    selected_ssd: Optional[ProductRow] = None
    selected_hdd: Optional[ProductRow] = None

    if required_ssd > 0:
        ssd_pool = [item for item in storage_pool if is_ssd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= required_ssd]
        if not ssd_pool:
            closest_ssd = [item for item in storage_pool if is_ssd(item.name, item.category_name)]
            if not closest_ssd:
                return f"I could not find any in-stock SSD in your database right now."
            closest_ssd.sort(key=lambda item: (abs(parse_storage_capacity_gb(item.name) - required_ssd), int(item.current_price)))
            lines = [
                f"I could not find an in-stock SSD of at least {required_ssd}GB right now.",
                "Closest SSD options from your database:",
            ]
            for idx, item in enumerate(closest_ssd[:3], start=1):
                lines.extend([
                    f"{idx}. {item.name}",
                    f"   Price: {int(item.current_price)} BDT",
                    f"   Shop: {item.shop_name or 'N/A'}",
                    f"   Link: {item.product_url or 'N/A'}",
                ])
            return "\n".join(lines)
        selected_ssd = min(ssd_pool, key=lambda item: Decimal(str(item.current_price)))

    if required_hdd > 0:
        hdd_pool = [item for item in storage_pool if is_hdd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= required_hdd]
        if not hdd_pool:
            closest_hdd = [item for item in storage_pool if is_hdd(item.name, item.category_name)]
            if not closest_hdd:
                return f"I could not find any in-stock HDD in your database right now."
            closest_hdd.sort(key=lambda item: (abs(parse_storage_capacity_gb(item.name) - required_hdd), int(item.current_price)))
            lines = [
                f"I could not find an in-stock HDD of at least {required_hdd}GB right now.",
                "Closest HDD options from your database:",
            ]
            for idx, item in enumerate(closest_hdd[:3], start=1):
                lines.extend([
                    f"{idx}. {item.name}",
                    f"   Price: {int(item.current_price)} BDT",
                    f"   Shop: {item.shop_name or 'N/A'}",
                    f"   Link: {item.product_url or 'N/A'}",
                ])
            return "\n".join(lines)
        selected_hdd = min(hdd_pool, key=lambda item: Decimal(str(item.current_price)))

    if required_ssd == 0 and required_hdd == 0:
        if not storage_pool:
            return "I could not find any in-stock storage options in your database right now."
        selected_ssd = min(storage_pool, key=lambda item: Decimal(str(item.current_price)))

    psu_pool = fetch_candidates(["Power Supply"], limit=24, preferences=prefs)
    case_pool = fetch_candidates(["Cabinet"], limit=24, preferences=prefs)

    pools = {
        "motherboard": mb_pool,
        "ram": ram_pool,
        "psu": psu_pool,
        "case": case_pool,
    }

    missing = [key for key, values in pools.items() if not values]
    if missing:
        missing_text = ", ".join(component.upper() for component in missing)
        return (
            "I could not estimate a reliable minimum build budget right now because these in-stock "
            f"components are missing: {missing_text}."
        )

    cheapest = {
        "cpu": cpu,
        "motherboard": min(mb_pool, key=lambda item: Decimal(str(item.current_price))),
        "ram": min(ram_pool, key=lambda item: Decimal(str(item.current_price))),
        "psu": min(psu_pool, key=lambda item: Decimal(str(item.current_price))),
        "case": min(case_pool, key=lambda item: Decimal(str(item.current_price))),
    }

    if selected_ssd:
        cheapest["ssd"] = selected_ssd
    if selected_hdd:
        cheapest["hdd"] = selected_hdd

    total = int(sum(int(item.current_price) for item in cheapest.values()))

    brand_hint = ""
    if prefs.get("cpu_brand") == "intel":
        brand_hint = " with an Intel processor"
    elif prefs.get("cpu_brand") == "amd":
        brand_hint = " with an AMD processor"

    lines = [
        f"Estimated minimum budget to build a basic PC{brand_hint}: {total} BDT",
        "",
        f"CPU: {cheapest['cpu'].name}",
        f"  Price: {int(cheapest['cpu'].current_price)} BDT",
        f"  Shop: {cheapest['cpu'].shop_name or 'N/A'}",
        f"  Link: {cheapest['cpu'].product_url or 'N/A'}",
        f"Motherboard: {cheapest['motherboard'].name}",
        f"  Price: {int(cheapest['motherboard'].current_price)} BDT",
        f"  Shop: {cheapest['motherboard'].shop_name or 'N/A'}",
        f"  Link: {cheapest['motherboard'].product_url or 'N/A'}",
        f"RAM: {cheapest['ram'].name}",
        f"  Price: {int(cheapest['ram'].current_price)} BDT",
        f"  Shop: {cheapest['ram'].shop_name or 'N/A'}",
        f"  Link: {cheapest['ram'].product_url or 'N/A'}",
    ]

    if "ssd" in cheapest:
        lines.extend([
            f"SSD: {cheapest['ssd'].name}",
            f"  Price: {int(cheapest['ssd'].current_price)} BDT",
            f"  Shop: {cheapest['ssd'].shop_name or 'N/A'}",
            f"  Link: {cheapest['ssd'].product_url or 'N/A'}",
        ])

    if "hdd" in cheapest:
        lines.extend([
            f"HDD: {cheapest['hdd'].name}",
            f"  Price: {int(cheapest['hdd'].current_price)} BDT",
            f"  Shop: {cheapest['hdd'].shop_name or 'N/A'}",
            f"  Link: {cheapest['hdd'].product_url or 'N/A'}",
        ])

    lines.extend([
        f"PSU: {cheapest['psu'].name}",
        f"  Price: {int(cheapest['psu'].current_price)} BDT",
        f"  Shop: {cheapest['psu'].shop_name or 'N/A'}",
        f"  Link: {cheapest['psu'].product_url or 'N/A'}",
        f"Case: {cheapest['case'].name}",
        f"  Price: {int(cheapest['case'].current_price)} BDT",
        f"  Shop: {cheapest['case'].shop_name or 'N/A'}",
        f"  Link: {cheapest['case'].product_url or 'N/A'}",
        "",
        "Note: This is a baseline estimate without a dedicated GPU.",
    ])
    return "\n".join(lines)


def component_match_score(name: str, component: str, preferences: Optional[Dict[str, str]] = None) -> int:
    if preferences is None:
        preferences = {}
    
    n = name.lower()

    # Hard-block obvious accessory words across all component types.
    global_block_terms = [
        "adapter",
        "enclosure",
        "expansion card",
        "converter",
        "caddy",
        "dock",
        "hub",
        "holder",
        "bracket",
        "mount",
    ]
    if any(term in n for term in global_block_terms):
        return -999

    include_terms = {
        "cpu": [" ryzen", " intel ", "core i3", "core i5", "core i7", "core i9", "pentium", "celeron", "athlon", "processor", "apu"],
        "gpu": [" geforce", " rtx", " gtx", " radeon", " rx ", " arc ", "graphics card", "vga", "gddr"],
        "motherboard": ["motherboard", "mother board", "mainboard", "am4", "am5", "lga", "h410", "h510", "h610", "b450", "b550", "b660", "b760", "z690", "z790"],
        "ram": [" ram", "ddr3", "ddr4", "ddr5", "memory", "udimm", "sodimm"],
        "storage": ["ssd", "nvme", "hdd", "hard disk", "hard drive", "sata", "m.2", "pcie"],
        "psu": ["power supply", "psu", "watt", "atx power", "80 plus"],
        "case": ["case", "cabinet", "casing", "chassis", "tower", "micro atx", "mid tower", "full tower"],
    }

    exclude_terms = {
        "cpu": ["cooler", "fan", "thermal", "paste", "holder", "bracket"],
        "gpu": ["holder", "stand", "support", "adapter", "bridge", "bracket"],
        "motherboard": ["cooler", "fan", "holder", "converter", "rgb convertor", "hub"],
        "ram": ["tv box", "ssd", "hdd", "fan", "holder", "case"],
        "storage": ["enclosure", "holder", "caddy", "adapter", "cooler", "heatsink", "expansion card"],
        "psu": ["cable", "hub", "holder", "adapter", "mount"],
        "case": ["case fan", "cooling fan", "fan", "holder", "power supply"],
    }

    score = 0
    for term in include_terms.get(component, []):
        if term in n:
            score += 2
    for term in exclude_terms.get(component, []):
        if term in n:
            score -= 3

    # Apply brand preferences for CPU
    if component == "cpu":
        if preferences.get("cpu_brand") == "intel" and "intel" in n:
            score += 5  # Strong preference boost for Intel
        elif preferences.get("cpu_brand") == "amd" and ("ryzen" in n or "amd" in n):
            score += 5  # Strong preference boost for AMD
        elif preferences.get("cpu_brand") == "intel" and ("amd" in n or "ryzen" in n):
            score -= 8  # Penalize wrong brand
        elif preferences.get("cpu_brand") == "amd" and "intel" in n:
            score -= 8  # Penalize wrong brand
    
    # Apply GPU preferences
    if component == "gpu":
        if preferences.get("gpu_brand") == "nvidia" and ("nvidia" in n or "geforce" in n or "rtx" in n or "gtx" in n):
            score += 5
        elif preferences.get("gpu_brand") == "amd" and ("amd" in n or "radeon" in n or " rx " in n):
            score += 5
        elif preferences.get("gpu_brand") == "nvidia" and ("amd" in n or "radeon" in n):
            score -= 8
        elif preferences.get("gpu_brand") == "amd" and ("nvidia" in n or "geforce" in n):
            score -= 8

    if component == "ram" and re.search(r"\b(8|16|32|64)\s*gb\b", n):
        score += 3
    if component == "gpu" and re.search(r"\b(4|6|8|10|12|16|24)\s*gb\b", n):
        score += 2
    if component == "psu" and re.search(r"\b(450|500|550|600|650|700|750|850|1000|1200)\s*w\b", n):
        score += 2

    return score


def fetch_candidates(category_filters: List[str], limit: int = 24, preferences: Optional[Dict[str, str]] = None) -> List[ProductRow]:
    if preferences is None:
        preferences = {}
        
    scan_limit = min(max(limit * 20, 200), 800)
    rows = (
        Product.objects.select_related("category", "shop")
        .filter(
            category__name__in=category_filters,
            is_available=True,
            stock_status="in_stock",
        )
        .order_by("current_price", "name")[:scan_limit]
    )
    
    # Double-check to ensure only in-stock products are processed
    scored_rows: List[Tuple[int, Decimal, Product]] = []
    for row in rows:
        # Skip if stock status is not exactly "in_stock" or is_available is False
        if row.stock_status != "in_stock" or not row.is_available:
            continue
            
        component = COMPONENT_BY_CATEGORY.get(row.category.name if row.category else "", "")
        match_score = component_match_score(row.name, component, preferences) if component else 0
        if match_score > 0:
            scored_rows.append((match_score, Decimal(str(row.current_price)), row))

    if not scored_rows:
        # Soft fallback: keep rows that are not obviously accessories.
        obvious_noise = [
            "holder",
            "enclosure",
            "bracket",
            "thermal paste",
            "cooler",
            "mount",
            "adapter",
            "expansion card",
            "converter",
            "caddy",
            "dock",
            "hub",
        ]
        for row in rows:
            # Only include products that are in stock
            if row.stock_status != "in_stock" or not row.is_available:
                continue
                
            name_lower = row.name.lower()
            if any(term in name_lower for term in obvious_noise):
                continue
            scored_rows.append((0, Decimal(str(row.current_price)), row))

    scored_rows.sort(key=lambda x: (-x[0], x[1]))

    # Storage pools should not include accessory products like external boxes/enclosures.
    if any(cat in category_filters for cat in ["SSD", "HDD"]):
        storage_noise_terms = [
            "enclosure",
            "external",
            "hdd box",
            "ssd box",
            "drive box",
            "case",
            "caddy",
            "dock",
            "adapter",
            "usb to",
        ]
        scored_rows = [
            item for item in scored_rows
            if not any(term in item[2].name.lower() for term in storage_noise_terms)
        ]

    result: List[ProductRow] = []
    for _, _, row in scored_rows[:limit]:
        result.append(
            ProductRow(
                id=int(row.id),
                name=str(row.name),
                category_name=str(row.category.name if row.category else ""),
                current_price=Decimal(str(row.current_price)),
                stock_status=str(row.stock_status),
                is_available=bool(row.is_available),
                product_url=str(row.product_url or ""),
                shop_name=str(row.shop.name if getattr(row, "shop", None) else ""),
            )
        )
    return result


def cpu_has_integrated_graphics(cpu_name: str) -> bool:
    name = cpu_name.lower()
    markers = [" 5600g", " 5700g", " 4600g", " 3200g", " 3400g", "apu", "with radeon", "graphics"]
    if "intel" in name and any(token in name for token in [" i3", " i5", " i7", " i9"]):
        return "-f" not in name and " f" not in name
    return any(marker in name for marker in markers)


def is_cpu_motherboard_compatible(cpu_name: str, mb_name: str) -> bool:
    cpu = cpu_name.lower()
    mb = mb_name.lower()

    if "ryzen" in cpu or "amd" in cpu:
        if any(token in mb for token in ["am4", "b450", "b550", "a520", "x570"]):
            return True
        if any(token in mb for token in ["am5", "b650", "x670", "a620"]):
            return True
        return False

    if "intel" in cpu or any(token in cpu for token in ["i3", "i5", "i7", "i9"]):
        return any(token in mb for token in ["lga", "h510", "h610", "b560", "b660", "b760", "z690", "z790"])

    return True


def is_ram_motherboard_compatible(ram_name: str, mb_name: str) -> bool:
    ram = ram_name.lower()
    mb = mb_name.lower()

    ram_ddr5 = "ddr5" in ram
    ram_ddr4 = "ddr4" in ram

    mb_ddr5 = any(token in mb for token in ["ddr5", "b650", "x670", "z790", "b760 d5", "z690 d5"])
    mb_ddr4 = any(token in mb for token in ["ddr4", "h410", "h510", "h610", "b450", "b550", "b560", "b660", "b760", "z690"])

    if ram_ddr5:
        return mb_ddr5
    if ram_ddr4:
        return mb_ddr4
    return True


def parse_ram_capacity_gb(name: str) -> int:
    match = re.search(r"(\d+)\s*gb", name.lower())
    if match:
        return int(match.group(1))
    return 0


def parse_storage_capacity_gb(name: str) -> int:
    lowered = name.lower()
    tb_match = re.search(r"(\d+(?:\.\d+)?)\s*tb", lowered)
    if tb_match:
        return int(float(tb_match.group(1)) * 1000)

    gb_match = re.search(r"(\d+)\s*gb", lowered)
    if gb_match:
        return int(gb_match.group(1))
    return 0


def parse_cpu_generation(name: str) -> int:
    lowered = name.lower()

    intel_match = re.search(r"i[3579][\-\s]?(\d{4,5})", lowered)
    if intel_match:
        sku = intel_match.group(1)
        if len(sku) == 5:
            return int(sku[:2])
        return int(sku[:1])

    amd_match = re.search(r"ryzen\s*[3579]?\s*(\d{4})", lowered)
    if amd_match:
        return int(amd_match.group(1)[0])

    return 0


def is_hdd(name: str, category_name: str) -> bool:
    n = name.lower()
    c = category_name.lower()
    return (
        "hdd" in n
        or "hard disk" in n
        or "hard drive" in n
        or "7200" in n
        or "hdd" in c
        or "hard" in c
    )


def is_ssd(name: str, category_name: str) -> bool:
    n = name.lower()
    return "ssd" in n or "nvme" in n or category_name.lower() == "ssd"


def pick_best_build(
    candidates: Dict[str, List[ProductRow]],
    budget: int,
    prefer_gpu: bool,
    favor_budget_utilization: bool,
) -> Tuple[Optional[Dict[str, ProductRow]], bool]:
    required_keys = ["cpu", "motherboard", "ram", "storage", "psu", "case"]
    if prefer_gpu:
        required_keys.append("gpu")

    if any(not candidates.get(key) for key in required_keys):
        return None, prefer_gpu

    combo_order = ["cpu", "motherboard", "ram", "storage", "psu", "case"]
    if prefer_gpu:
        combo_order.insert(4, "gpu")

    # Keep search bounded but allow wider CPU/motherboard exploration so higher
    # budget builds can use better CPU tiers and compatible boards.
    pools: List[List[ProductRow]] = []
    for key in combo_order:
        if key == "cpu":
            pools.append(candidates[key][:8])
        elif key == "motherboard":
            pools.append(candidates[key][:6])
        elif key == "gpu":
            pools.append(candidates[key][:6])
        else:
            pools.append(candidates[key][:4])

    best_combo: Optional[Dict[str, ProductRow]] = None
    best_score = Decimal("-1")

    for combo in itertools.product(*pools):
        picked = dict(zip(combo_order, combo))

        if not is_cpu_motherboard_compatible(picked["cpu"].name, picked["motherboard"].name):
            continue

        if not is_ram_motherboard_compatible(picked["ram"].name, picked["motherboard"].name):
            continue

        ram_gb = parse_ram_capacity_gb(picked["ram"].name)
        if ram_gb and ram_gb < 8:
            continue

        if not prefer_gpu and not cpu_has_integrated_graphics(picked["cpu"].name):
            continue

        total = sum((item.current_price for item in picked.values()), Decimal("0"))
        if total > Decimal(budget):
            continue

        score = Decimal("0")
        if "gpu" in picked:
            score += picked["gpu"].current_price * Decimal("1.40")
        score += picked["cpu"].current_price * Decimal("1.00")
        score += picked["motherboard"].current_price * Decimal("0.60")
        score += picked["ram"].current_price * Decimal("0.70")
        score += picked["storage"].current_price * Decimal("0.50")
        score += picked["psu"].current_price * Decimal("0.45")
        score += picked["case"].current_price * Decimal("0.20")

        if parse_ram_capacity_gb(picked["ram"].name) >= 16:
            score += Decimal("1200")
        if is_ssd(picked["storage"].name, picked["storage"].category_name):
            score += Decimal("1200")

        utilization_weight = Decimal("1200") if favor_budget_utilization else Decimal("450")
        score += (total / Decimal(max(budget, 1))) * utilization_weight

        utilization = total / Decimal(max(budget, 1))
        # For non-hard-cap budgets (e.g., "budget 40k"), target near full budget usage.
        if favor_budget_utilization and utilization < Decimal("0.98"):
            score -= (Decimal("0.98") - utilization) * Decimal("12000")
        # For hard-cap budgets (e.g., "under 40k"), bias away from maxing the cap.
        if not favor_budget_utilization and utilization > Decimal("0.95"):
            score -= (utilization - Decimal("0.95")) * Decimal("2500")

        cpu_gen = parse_cpu_generation(picked["cpu"].name)
        cpu_name_lower = picked["cpu"].name.lower()
        low_tier_cpu_terms = ["athlon", "pentium", "celeron", "core i3", "a-series", "a4", "a6", "a8"]
        mid_high_cpu_terms = ["core i5", "core i7", "core i9", "ryzen 5", "ryzen 7", "ryzen 9"]

        if budget >= 70000:
            if cpu_gen >= 10:
                score += Decimal("1800")
            elif cpu_gen >= 8:
                score += Decimal("900")
            elif cpu_gen > 0 and cpu_gen <= 4:
                score -= Decimal("3800")
            if any(term in cpu_name_lower for term in low_tier_cpu_terms):
                score -= Decimal("3200")
            if any(term in cpu_name_lower for term in mid_high_cpu_terms):
                score += Decimal("1200")
            if picked["cpu"].current_price < Decimal(budget * 0.10):
                score -= Decimal("1800")
            if picked["ram"].current_price > Decimal(budget * 0.20):
                score -= Decimal("2200")
        elif budget <= 45000:
            if cpu_gen > 0 and cpu_gen <= 4:
                score += Decimal("700")
            if picked["cpu"].current_price > Decimal(budget * 0.45):
                score -= Decimal("1000")

        if score > best_score:
            best_score = score
            best_combo = picked

    return best_combo, prefer_gpu


def build_sql_queries(user_budget: int, include_gpu: bool) -> Dict[str, str]:
    base = (
        "SELECT p.id, p.name, c.name AS category_name, CAST(p.current_price AS REAL) AS current_price, "
        "p.stock_status, p.is_available "
        "FROM products_product p JOIN products_category c ON p.category_id = c.id "
        "WHERE c.name IN ({cats}) AND p.is_available = 1 AND p.stock_status = 'in_stock' "
        "AND CAST(p.current_price AS REAL) <= {max_price} ORDER BY CAST(p.current_price AS REAL) {order} LIMIT 3;"
    )

    caps = {
        "cpu": int(user_budget * (0.30 if not include_gpu else 0.24)),
        "motherboard": int(user_budget * (0.20 if not include_gpu else 0.15)),
        "ram": int(user_budget * (0.16 if not include_gpu else 0.10)),
        "storage": int(user_budget * (0.14 if not include_gpu else 0.08)),
        "gpu": int(user_budget * 0.40),
        "psu": int(user_budget * (0.10 if not include_gpu else 0.06)),
        "case": int(user_budget * (0.10 if not include_gpu else 0.04)),
    }

    return {
        "cpu": base.format(cats="'Processor','CPU'", max_price=max(caps["cpu"], 1), order="DESC"),
        "gpu": base.format(cats="'GPU'", max_price=max(caps["gpu"], 1), order="DESC"),
        "ram": base.format(cats="'RAM'", max_price=max(caps["ram"], 1), order="DESC"),
        "motherboard": base.format(cats="'Motherboard'", max_price=max(caps["motherboard"], 1), order="DESC"),
        "storage": base.format(cats="'SSD','HDD'", max_price=max(caps["storage"], 1), order="DESC"),
        "psu": base.format(cats="'Power Supply'", max_price=max(caps["psu"], 1), order="DESC"),
        "case": base.format(cats="'Cabinet'", max_price=max(caps["case"], 1), order="ASC"),
    }


def make_explanation(build: Dict[str, str], total: int, budget: int, used_gpu: bool) -> str:
    reasons = [
        "This build prioritizes gaming performance while keeping every selected part in stock and available.",
        "CPU and motherboard are selected for socket/chipset compatibility.",
        "RAM and storage are balanced for smooth gaming and daily use.",
    ]
    if used_gpu:
        reasons.append("A dedicated GPU gets the biggest performance budget share for better FPS.")
    else:
        reasons.append("The budget is optimized with an integrated-graphics CPU to stay under the cap.")
    reasons.append(f"Total stays within budget: {total} BDT / {budget} BDT.")
    return " ".join(reasons)


def call_openrouter(messages: List[Dict[str, str]]) -> Optional[str]:
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_X_TITLE,
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def make_db_grounded_reply(user_input: str, db_result_text: str) -> Optional[str]:
    """Generate a natural chat response grounded on database results."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful PC shopping assistant. Respond naturally like ChatGPT/Gemini. "
                "Use the provided database result as source of truth for products, prices, shops, and links. "
                "Do not invent products not present in the database result. "
                "If result is empty or weak, explain clearly and suggest next best query from user."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User request:\n{user_input}\n\n"
                f"Database result:\n{db_result_text}\n\n"
                "Write a concise, friendly, natural response."
            ),
        },
    ]
    return call_openrouter(messages)


def format_product_lookup_response(response_text: str) -> str:
    lines = [line.rstrip() for line in response_text.splitlines() if line.strip()]
    if not lines:
        return response_text

    header = lines[0]
    items: List[Dict[str, str]] = []
    current_item: Dict[str, str] = {}

    for line in lines[1:]:
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            if current_item:
                items.append(current_item)
                current_item = {}

            match = re.match(r"^(\d+)\.\s+(.*?)\s+-\s+([^\(]+)\s+\((.*?)\)$", stripped)
            if match:
                current_item = {
                    "index": match.group(1).strip(),
                    "name": match.group(2).strip(),
                    "price": match.group(3).strip(),
                    "shop": match.group(4).strip(),
                }
            else:
                current_item = {"name": stripped}
        elif stripped.lower().startswith("link:") and current_item:
            current_item["link"] = stripped.split(":", 1)[1].strip()

    if current_item:
        items.append(current_item)

    if not items:
        return response_text

    formatted = [header, ""]
    for index, item in enumerate(items, start=1):
        item_index = item.get("index", str(index))
        formatted.append(f"{item_index}. {item.get('name', 'N/A')}")
        formatted.append(f"   Price: {item.get('price', 'N/A')}")
        formatted.append(f"   Shop: {item.get('shop', 'N/A')}")
        formatted.append(f"   Link: {item.get('link', 'N/A')}")
        if index != len(items):
            formatted.append("")

    return "\n".join(formatted)


def plan_chat_route(
    user_input: str,
    last_budget: Optional[int],
    last_purchase_mode: Optional[str],
    has_lookup_context: bool,
) -> str:
    """Choose how to handle a message: general chat, product lookup, or PC build."""
    lowered = user_input.lower()
    if "budget" in lowered and any(term in lowered for term in ["allocation", "percentage", "%", "breakdown", "distribution", "split", "plan"]):
        return "general"

    if is_minimum_budget_build_request(user_input):
        return "build_min_budget"

    if last_purchase_mode == "build" and is_no_budget_followup(user_input):
        return "build_min_budget"

    if is_build_request(user_input):
        return "build"

    if last_purchase_mode == "build" and is_build_preference_followup_request(user_input):
        if parse_total_build_budget(user_input) is None and last_budget is None:
            return "build_ask_budget"
        return "build_followup"

    if last_purchase_mode == "build" and is_build_details_followup_request(user_input):
        return "build_details"

    if last_purchase_mode == "build" and is_build_continue_request(user_input):
        if parse_total_build_budget(user_input) is None:
            return "build_min_budget"
        return "build_followup"

    if last_purchase_mode == "build" and is_build_budget_adjustment_request(user_input):
        if parse_total_build_budget(user_input) is None:
            return "build_ask_budget"
        return "build_followup"

    # In build context, allow budget-only followups like "my budget is 50k".
    if (
        last_purchase_mode == "build"
        and parse_total_build_budget(user_input)
        and detect_component_intent(user_input) is None
    ):
        return "build_followup"

    # Check build_followup BEFORE lookup: "i want intel" after a build is a build modification, not a product lookup
    if last_budget and is_build_modification_request(
        user_input,
        assume_build_context=(last_purchase_mode == "build"),
    ):
        return "build_followup"

    if is_product_lookup_request(user_input):
        return "lookup"

    if is_product_lookup_followup_request(user_input, has_lookup_context):
        return "lookup_followup"

    return "general"


def append_chat_turn(conversation: List[Dict[str, str]], user_input: str, assistant_reply: str) -> None:
    conversation.append({"role": "user", "content": user_input})
    conversation.append({"role": "assistant", "content": assistant_reply})


def build_pc_response(user_input: str) -> str:
    budget = parse_total_build_budget(user_input)

    # Parse user preferences and optional per-component constraints early so we can
    # disambiguate component price ranges from total build budget intent.
    prefs = parse_build_preferences(user_input)
    capacity_requirements = parse_build_capacity_requirements(user_input)
    price_constraints = parse_component_price_constraints(user_input)

    lowered = user_input.lower()

    # If user is clearly talking about total budget range (e.g. "budget between 30k-35k"),
    # do not reinterpret that same range as a CPU/component constraint.
    has_budget_phrase = "budget" in lowered
    has_explicit_component_price_phrase = any(
        phrase in lowered
        for phrase in [
            "cpu price",
            "processor price",
            "gpu price",
            "ram price",
            "storage price",
            "motherboard price",
            "psu price",
            "case price",
        ]
    )
    if has_budget_phrase and not has_explicit_component_price_phrase:
        price_constraints = {}

    has_component_price_constraint = bool(price_constraints)
    has_explicit_total_budget_cue = any(
        phrase in lowered
        for phrase in [
            "total budget",
            "overall budget",
            "full budget",
            "whole build",
            "entire build",
            "total price",
            "overall price",
        ]
    )
    has_under_total_budget = "under" in lowered and any(
        marker in lowered for marker in ["build", "pc", "total", "budget"]
    )
    has_explicit_total_budget_cue = has_explicit_total_budget_cue or has_under_total_budget

    # Example: "make a build with an intel processor thats price is between 10-12k"
    # should NOT force full system budget to 12k. Ask for total budget instead.
    if has_component_price_constraint and not has_explicit_total_budget_cue:
        budget = None

    if not budget:
        return json.dumps(
            {
                "queries": {"cpu": "", "gpu": "", "ram": "", "motherboard": "", "storage": "", "psu": "", "case": ""},
                "build": {
                    "CPU": "",
                    "Motherboard": "",
                    "RAM": "",
                    "Storage": "",
                    "GPU": "",
                    "PSU": "",
                    "Case": "",
                    "total_price": "0 BDT",
                },
                "explanation": (
                    "Please provide the total PC budget in BDT (for example: build a gaming PC under 50000 BDT). "
                    "You can still keep component constraints like CPU 10-12k."
                ),
            },
            ensure_ascii=True,
        )

    def as_component(item: ProductRow) -> Dict[str, str]:
        return {
            "name": item.name,
            "price": f"{int(item.current_price)} BDT",
            "shop": item.shop_name or "N/A",
            "shop_link": item.product_url or "N/A",
        }

    def no_build_response(
        explanation: str,
        queries_payload: Optional[Dict[str, str]] = None,
        fallback_items: Optional[Dict[str, ProductRow]] = None,
    ) -> str:
        build_payload: Dict[str, object] = {
            "CPU": "No matching product found",
            "Motherboard": "No matching product found",
            "RAM": "No matching product found",
            "Storage": "No matching product found",
            "GPU": "No matching product found",
            "PSU": "No matching product found",
            "Case": "No matching product found",
            "total_price": "0 BDT",
        }

        if fallback_items:
            label_map = {
                "cpu": "CPU",
                "motherboard": "Motherboard",
                "ram": "RAM",
                "storage": "Storage",
                "gpu": "GPU",
                "psu": "PSU",
                "case": "Case",
            }
            total = 0
            for key, item in fallback_items.items():
                label = label_map.get(key)
                if not label:
                    continue
                build_payload[label] = as_component(item)
                total += int(item.current_price)

            if "gpu" not in fallback_items:
                build_payload["GPU"] = "Not included (integrated graphics build)"
            build_payload["total_price"] = f"{total} BDT" if total else "0 BDT"

            explanation = (
                explanation
                + " Closest in-stock alternatives from your database are shown above with price, shop, and link."
            )

        return json.dumps(
            {
                "queries": queries_payload or {"cpu": "", "gpu": "", "ram": "", "motherboard": "", "storage": "", "psu": "", "case": ""},
                "build": build_payload,
                "explanation": explanation,
            },
            ensure_ascii=True,
        )

    candidates = {
        "cpu": fetch_candidates(["Processor", "CPU"], limit=24, preferences=prefs),
        "motherboard": fetch_candidates(["Motherboard"], limit=24, preferences=prefs),
        "ram": fetch_candidates(["RAM"], limit=24, preferences=prefs),
        "storage": fetch_candidates(["SSD", "HDD"], limit=24, preferences=prefs),
        "gpu": fetch_candidates(["GPU"], limit=24, preferences=prefs),
        "psu": fetch_candidates(["Power Supply"], limit=24, preferences=prefs),
        "case": fetch_candidates(["Cabinet"], limit=24, preferences=prefs),
    }

    requested_cpu_gen = prefs.get("cpu_generation_min")
    if isinstance(requested_cpu_gen, int) and requested_cpu_gen > 0 and prefs.get("cpu_brand") == "intel":
        gen_filtered_cpus = [
            item for item in candidates["cpu"]
            if parse_cpu_generation(item.name) >= requested_cpu_gen
        ]
        if not gen_filtered_cpus:
            return no_build_response(
                f"Could not create an in-stock build because no INTEL {requested_cpu_gen}th gen (or newer) CPU is currently available in your database within this build context.",
                fallback_items=None,
            )
        candidates["cpu"] = gen_filtered_cpus

    if prefs.get("prefer_better_cpu") == "yes" and candidates.get("cpu"):
        # Prefer stronger CPU tiers for upgrade-type followups.
        better_cpu_pool = [
            item for item in candidates["cpu"]
            if (
                parse_cpu_generation(item.name) >= 6
                or any(token in item.name.lower() for token in ["core i5", "core i7", "core i9", "ryzen 5", "ryzen 7", "ryzen 9"])
            )
        ]
        if better_cpu_pool:
            candidates["cpu"] = better_cpu_pool

    if budget >= 70000 and candidates.get("cpu"):
        preferred_cpus = [
            item for item in candidates["cpu"]
            if (
                parse_cpu_generation(item.name) >= 8
                or any(token in item.name.lower() for token in ["core i5", "core i7", "core i9", "ryzen 5", "ryzen 7", "ryzen 9"])
            )
        ]
        if preferred_cpus:
            candidates["cpu"] = preferred_cpus

    def closest_fallback_components(include_gpu: bool) -> Dict[str, ProductRow]:
        fallback: Dict[str, ProductRow] = {}
        if candidates.get("cpu"):
            fallback["cpu"] = candidates["cpu"][0]
        if candidates.get("motherboard"):
            if "cpu" in fallback:
                compatible = [
                    item for item in candidates["motherboard"]
                    if is_cpu_motherboard_compatible(fallback["cpu"].name, item.name)
                ]
                fallback["motherboard"] = compatible[0] if compatible else candidates["motherboard"][0]
            else:
                fallback["motherboard"] = candidates["motherboard"][0]
        if candidates.get("ram"):
            fallback["ram"] = candidates["ram"][0]
        if candidates.get("storage"):
            fallback["storage"] = candidates["storage"][0]
        if include_gpu and candidates.get("gpu"):
            fallback["gpu"] = candidates["gpu"][0]
        if candidates.get("psu"):
            fallback["psu"] = candidates["psu"][0]
        if candidates.get("case"):
            fallback["case"] = candidates["case"][0]
        return fallback

    required_ram = capacity_requirements.get("ram_gb", 0)
    required_ssd = capacity_requirements.get("ssd_gb", 0)
    required_hdd = capacity_requirements.get("hdd_gb", 0)
    dual_requested = required_hdd > 0 and required_ssd > 0
    prefer_gpu = budget >= 45000

    if required_ram > 0:
        filtered_ram = [item for item in candidates["ram"] if parse_ram_capacity_gb(item.name) >= required_ram]
        if not filtered_ram:
            return no_build_response(
                f"Could not create an in-stock build because no RAM option with at least {required_ram}GB is currently available in your database.",
                fallback_items=closest_fallback_components(prefer_gpu),
            )
        candidates["ram"] = filtered_ram

    if required_ssd > 0:
        filtered_storage = [
            item
            for item in candidates["storage"]
            if is_ssd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= required_ssd
        ]
        if not filtered_storage:
            return no_build_response(
                f"Could not create an in-stock build because no SSD option with at least {required_ssd}GB is currently available in your database.",
                fallback_items=closest_fallback_components(prefer_gpu),
            )
        candidates["storage"] = filtered_storage

    if required_hdd > 0 and required_ssd == 0:
        filtered_storage = [
            item
            for item in candidates["storage"]
            if is_hdd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= required_hdd
        ]
        if not filtered_storage:
            return no_build_response(
                f"Could not create an in-stock build because no HDD option with at least {required_hdd}GB is currently available in your database.",
                fallback_items=closest_fallback_components(prefer_gpu),
            )
        candidates["storage"] = filtered_storage

    # Apply optional per-component price constraints from user prompt.
    for component_key, price_range in price_constraints.items():
        low, high = price_range
        if component_key in candidates:
            filtered = [
                item for item in candidates[component_key]
                if low <= int(item.current_price) <= high
            ]
            if filtered:
                candidates[component_key] = filtered

    def apply_component_band(component_key: str, min_ratio: float, max_ratio: float) -> None:
        if component_key not in candidates or not candidates[component_key]:
            return
        lo = int(budget * min_ratio)
        hi = int(budget * max_ratio)
        filtered = [
            item for item in candidates[component_key]
            if lo <= int(item.current_price) <= hi
        ]
        if filtered:
            candidates[component_key] = filtered

    if budget >= 70000:
        apply_component_band("cpu", 0.12, 0.38)
        apply_component_band("motherboard", 0.08, 0.24)
        apply_component_band("ram", 0.05, 0.18)
        apply_component_band("storage", 0.03, 0.16)
        apply_component_band("psu", 0.04, 0.14)
        apply_component_band("case", 0.03, 0.12)
    elif budget <= 45000:
        apply_component_band("cpu", 0.10, 0.32)
        apply_component_band("motherboard", 0.08, 0.24)
        apply_component_band("ram", 0.05, 0.16)
        apply_component_band("storage", 0.04, 0.16)

    favor_budget_utilization = not is_hard_cap_budget_request(user_input)

    auto_reserved_hdd: Optional[ProductRow] = None
    effective_budget = budget
    if budget >= 70000 and not dual_requested:
        ssd_primary_pool = [
            item
            for item in candidates["storage"]
            if is_ssd(item.name, item.category_name)
        ]
        hdd_pool = [
            item
            for item in fetch_candidates(["HDD"], limit=24, preferences=prefs)
            if is_hdd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= 1000
        ]
        if hdd_pool and ssd_primary_pool:
            auto_reserved_hdd = min(hdd_pool, key=lambda item: Decimal(str(item.current_price)))
            reserved_cost = int(auto_reserved_hdd.current_price)
            if reserved_cost < budget:
                effective_budget = max(1, budget - reserved_cost)

            # On higher budgets, keep SSD as primary and add HDD as secondary.
            candidates["storage"] = ssd_primary_pool

    picked, used_gpu = pick_best_build(
        candidates,
        effective_budget,
        prefer_gpu=prefer_gpu,
        favor_budget_utilization=favor_budget_utilization,
    )
    if picked is None and prefer_gpu:
        picked, used_gpu = pick_best_build(
            candidates,
            effective_budget,
            prefer_gpu=False,
            favor_budget_utilization=favor_budget_utilization,
        )

    extra_hdd: Optional[ProductRow] = None
    extra_ssd: Optional[ProductRow] = None
    if picked and auto_reserved_hdd and not dual_requested:
        extra_hdd = auto_reserved_hdd

    if picked and required_hdd > 0 and required_ssd > 0:
        hdd_pool = [
            item
            for item in fetch_candidates(["HDD"], limit=24, preferences=prefs)
            if is_hdd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= required_hdd
        ]
        if not hdd_pool:
            picked = None
        else:
            extra_hdd = min(hdd_pool, key=lambda item: Decimal(str(item.current_price)))

    if picked and not dual_requested and budget >= 70000:
        primary = picked["storage"]
        primary_is_ssd = is_ssd(primary.name, primary.category_name)
        primary_is_hdd = is_hdd(primary.name, primary.category_name)

        if primary_is_ssd:
            hdd_pool = [
                item
                for item in fetch_candidates(["HDD"], limit=24, preferences=prefs)
                if is_hdd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= 1000
            ]
            if hdd_pool:
                candidate_hdd = min(hdd_pool, key=lambda item: Decimal(str(item.current_price)))
                projected_total = int(sum(item.current_price for item in picked.values())) + int(candidate_hdd.current_price)
                if projected_total <= budget:
                    extra_hdd = candidate_hdd
        elif primary_is_hdd:
            ssd_pool = [
                item
                for item in fetch_candidates(["SSD"], limit=24, preferences=prefs)
                if is_ssd(item.name, item.category_name) and parse_storage_capacity_gb(item.name) >= 240
            ]
            if ssd_pool:
                candidate_ssd = min(ssd_pool, key=lambda item: Decimal(str(item.current_price)))
                projected_total = int(sum(item.current_price for item in picked.values())) + int(candidate_ssd.current_price)
                if projected_total <= budget:
                    extra_ssd = candidate_ssd

    queries = build_sql_queries(budget, include_gpu=used_gpu if picked else prefer_gpu)

    if not picked:
        explanation = "Could not create a compatible in-stock build under this budget from the active Render database."
        requirement_hints: List[str] = []
        if required_ram:
            requirement_hints.append(f"RAM >= {required_ram}GB")
        if required_ssd:
            requirement_hints.append(f"SSD >= {required_ssd}GB")
        if required_hdd:
            requirement_hints.append(f"HDD >= {required_hdd}GB")
        if requirement_hints:
            explanation = (
                "Could not create an in-stock build matching your requested specs ("
                + ", ".join(requirement_hints)
                + ") within this budget."
            )
        if prefs.get("cpu_brand") in {"intel", "amd"}:
            min_hint = estimate_minimum_build_budget_response(f"minimum budget to build a pc with {prefs['cpu_brand']} processor")
            min_match = re.search(r":\s*(\d+)\s*BDT", min_hint)
            if min_match:
                minimum_budget = int(min_match.group(1))
                explanation = (
                    f"Could not create a compatible in-stock {prefs['cpu_brand'].upper()} build under this budget. "
                    f"Estimated minimum is about {minimum_budget} BDT."
                )

        return no_build_response(explanation, queries, fallback_items=closest_fallback_components(prefer_gpu))

    # Validate that all picked items are in stock before displaying
    for component_name, item in picked.items():
        if item.stock_status != "in_stock" or not item.is_available:
            return json.dumps(
                {
                    "queries": queries,
                    "build": {
                        "CPU": "No matching product found",
                        "Motherboard": "No matching product found",
                        "RAM": "No matching product found",
                        "Storage": "No matching product found",
                        "GPU": "No matching product found",
                        "PSU": "No matching product found",
                        "Case": "No matching product found",
                        "total_price": "0 BDT",
                    },
                    "explanation": f"One of the selected components ({component_name}) is no longer in stock. Please try again to get available products.",
                },
                ensure_ascii=True,
            )

    total = int(sum(item.current_price for item in picked.values()))
    if extra_hdd:
        total += int(extra_hdd.current_price)
    if extra_ssd:
        total += int(extra_ssd.current_price)

    if total > budget:
        return no_build_response(
            "Could not include all requested storage requirements within this total budget.",
            queries,
            fallback_items=closest_fallback_components(prefer_gpu),
        )

    build_json = {
        "CPU": as_component(picked["cpu"]),
        "Motherboard": as_component(picked["motherboard"]),
        "RAM": as_component(picked["ram"]),
        "Storage": (
            {
                "name": (
                    f"SSD: {picked['storage'].name} + HDD: {extra_hdd.name}"
                    if extra_hdd and not extra_ssd
                    else f"HDD: {picked['storage'].name} + SSD: {extra_ssd.name}"
                ),
                "price": (
                    f"{int(picked['storage'].current_price) + int(extra_hdd.current_price)} BDT"
                    if extra_hdd and not extra_ssd
                    else f"{int(picked['storage'].current_price) + int(extra_ssd.current_price)} BDT"
                ),
                "shop": (
                    f"SSD: {picked['storage'].shop_name or 'N/A'} | HDD: {extra_hdd.shop_name or 'N/A'}"
                    if extra_hdd and not extra_ssd
                    else f"HDD: {picked['storage'].shop_name or 'N/A'} | SSD: {extra_ssd.shop_name or 'N/A'}"
                ),
                "shop_link": (
                    f"SSD: {picked['storage'].product_url or 'N/A'} | HDD: {extra_hdd.product_url or 'N/A'}"
                    if extra_hdd and not extra_ssd
                    else f"HDD: {picked['storage'].product_url or 'N/A'} | SSD: {extra_ssd.product_url or 'N/A'}"
                ),
            }
            if (extra_hdd or extra_ssd)
            else as_component(picked["storage"])
        ),
        "GPU": as_component(picked["gpu"]) if used_gpu and "gpu" in picked else "Not included (integrated graphics build)",
        "PSU": as_component(picked["psu"]),
        "Case": as_component(picked["case"]),
        "total_price": f"{total} BDT",
    }

    return json.dumps(
        {
            "queries": queries,
            "build": build_json,
            "explanation": make_explanation(build_json, total=total, budget=budget, used_gpu=used_gpu),
        },
        ensure_ascii=True,
    )


def format_build_response_for_terminal(response_json: str, show_queries: bool = False) -> str:
    try:
        payload = json.loads(response_json)
    except json.JSONDecodeError:
        return response_json

    build = payload.get("build", {})
    explanation = payload.get("explanation", "")
    queries = payload.get("queries", {})

    # For missing-budget prompts, return a concise actionable message.
    if (
        "Please provide a budget in BDT" in explanation
        or "Please provide the total PC budget in BDT" in explanation
    ):
        return explanation

    def render_component(label: str) -> List[str]:
        value = build.get(label, "N/A")
        if isinstance(value, dict):
            return [
                f"{label}: {value.get('name', 'N/A')}",
                f"  Price: {value.get('price', 'N/A')}",
                f"  Shop: {value.get('shop', 'N/A')}",
                f"  Link: {value.get('shop_link', 'N/A')}",
            ]
        return [f"{label}: {value}"]

    lines = [
        "Build Recommendation",
        "--------------------",
    ]

    for key in ["CPU", "Motherboard", "RAM", "Storage", "GPU", "PSU", "Case"]:
        lines.extend(render_component(key))

    lines.extend([
        f"Total: {build.get('total_price', 'N/A')}",
        "",
        f"Why this build: {explanation}",
    ])

    if show_queries and queries:
        lines.append("")
        lines.append("SQL Queries")
        lines.append("-----------")
        for key in ["cpu", "gpu", "ram", "motherboard", "storage", "psu", "case"]:
            query = queries.get(key)
            if query:
                lines.append(f"{key.upper()}: {query}")

    return "\n".join(lines)


def parse_build_preferences(text: str) -> Dict[str, str]:
    """Extract build preferences from user input."""
    lowered = text.lower()
    preferences = {}
    
    # CPU brand preference
    if "intel" in lowered:
        preferences["cpu_brand"] = "intel"
    elif "amd" in lowered or "ryzen" in lowered:
        preferences["cpu_brand"] = "amd"
    
    # GPU preference
    if "no gpu" in lowered or "without gpu" in lowered or "integrated" in lowered:
        preferences["gpu"] = "no"
    elif "nvidia" in lowered or "geforce" in lowered or "rtx" in lowered or "gtx" in lowered:
        preferences["gpu_brand"] = "nvidia"
    elif "radeon" in lowered or "amd gpu" in lowered:
        preferences["gpu_brand"] = "amd"
    elif "with gpu" in lowered or "dedicated gpu" in lowered:
        preferences["gpu"] = "yes"
    
    # Build purpose
    if "gaming" in lowered:
        preferences["purpose"] = "gaming"
    elif "workstation" in lowered:
        preferences["purpose"] = "workstation"
    elif "office" in lowered or "general" in lowered:
        preferences["purpose"] = "office"
    elif "streaming" in lowered:
        preferences["purpose"] = "streaming"

    # CPU generation preference (e.g., "10 gen", "10th gen", "12th generation").
    gen_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:gen|generation)\b", lowered)
    if gen_match:
        preferences["cpu_generation_min"] = int(gen_match.group(1))

    # Upgrade intent used to bias CPU selection upward.
    if any(term in lowered for term in ["better processor", "better cpu", "use a better", "upgrade cpu", "upgrade processor"]):
        preferences["prefer_better_cpu"] = "yes"
    
    return preferences


def is_build_modification_request(text: str, assume_build_context: bool = False) -> bool:
    """Detect if user is modifying a previous build request."""
    lowered = text.lower()
    upgrade_terms = [
        "better processor",
        "better cpu",
        "use a better",
        "upgrade cpu",
        "upgrade processor",
        "newer gen",
        "higher gen",
        "latest gen",
    ]
    if assume_build_context and any(term in lowered for term in upgrade_terms):
        return True

    prefs = parse_build_preferences(text)
    if not prefs:
        return False

    # In build context, explicit lookup-style prompts (e.g. "cheapest intel processor")
    # should stay in lookup mode instead of forcing a full rebuild.
    explicit_lookup_terms = [
        "cheapest",
        "lowest",
        "price",
        "suggest",
        "recommend",
        "available",
        "show",
        "list",
        "within",
        "between",
        "range",
        "under",
        "around",
    ]
    if detect_component_intent(text) and any(term in lowered for term in explicit_lookup_terms):
        return False

    if assume_build_context:
        return True

    build_cues = ["build", "pc", "rebuild", "change", "replace", "same budget", "under "]
    return any(cue in lowered for cue in build_cues)


def is_build_preference_followup_request(text: str) -> bool:
    """Detect natural follow-ups that adjust build brand/preferences."""
    lowered = text.lower()

    pref_terms = [
        "intel",
        "amd",
        "ryzen",
        "nvidia",
        "radeon",
        "geforce",
        "with gpu",
        "without gpu",
        "no gpu",
    ]
    change_terms = ["instead of", "rather than", "switch", "change", "use", "prefer", "want"]

    mentions_pref = any(term in lowered for term in pref_terms)
    mentions_change = any(term in lowered for term in change_terms)
    mentions_existing_build = "this build" in lowered or "in this build" in lowered

    return (mentions_pref and mentions_change) or (mentions_existing_build and mentions_pref)


def is_build_details_followup_request(text: str) -> bool:
    lowered = text.lower()
    detail_terms = ["price", "prices", "shop", "link", "where", "buy", "cost", "details"]
    show_terms = ["show", "give", "tell", "include", "both"]
    if "where" in lowered and any(term in lowered for term in ["shop", "link", "buy"]):
        return True
    return any(term in lowered for term in detail_terms) and any(term in lowered for term in show_terms)


def build_with_context(
    user_input: str,
    last_budget: Optional[int],
    preferences_override: Optional[Dict[str, str]] = None,
    base_request: Optional[str] = None,
) -> Optional[str]:
    """Rebuild PC with same budget but different preferences."""
    if not last_budget:
        return None

    # Parse preferences from the user's modification request.
    prefs = preferences_override or parse_build_preferences(user_input)
    pref_tokens: List[str] = []
    if prefs.get("cpu_brand"):
        pref_tokens.append(f"{prefs['cpu_brand']} processor")
    if prefs.get("gpu") == "no":
        pref_tokens.append("without gpu")
    elif prefs.get("gpu") == "yes":
        pref_tokens.append("with gpu")
    if prefs.get("gpu_brand"):
        pref_tokens.append(f"{prefs['gpu_brand']} gpu")
    if prefs.get("purpose"):
        pref_tokens.append(prefs["purpose"])
    if isinstance(prefs.get("cpu_generation_min"), int):
        pref_tokens.append(f"{prefs['cpu_generation_min']}th gen")
    if prefs.get("prefer_better_cpu") == "yes":
        pref_tokens.append("better cpu")

    if base_request:
        normalized_base_request = base_request
        # Remove prior budget expressions so the latest follow-up budget is authoritative.
        normalized_base_request = re.sub(r"\b(?:under|around|about|between)\s*\d+(?:[\.,]\d+)?\s*(?:k|bdt|tk|taka)?\b", "", normalized_base_request, flags=re.IGNORECASE)
        normalized_base_request = re.sub(r"\b\d+(?:[\.,]\d+)?\s*(?:-|to)\s*\d+(?:[\.,]\d+)?\s*(?:k|bdt|tk|taka)?\b", "", normalized_base_request, flags=re.IGNORECASE)
        normalized_base_request = re.sub(r"\b\d+(?:[\.,]\d+)?\s*(?:k|bdt|tk|taka)\b", "", normalized_base_request, flags=re.IGNORECASE)
        normalized_base_request = re.sub(r"\s+", " ", normalized_base_request).strip()
        combined_request = f"{normalized_base_request} total budget {last_budget} {' '.join(pref_tokens)} {user_input}".strip()
    else:
        combined_request = f"build me a pc under {last_budget} {' '.join(pref_tokens)} {user_input}".strip()
    raw_response = build_pc_response(combined_request)

    # If strict preference matching fails, retry with relaxed preferences
    # while preserving the user's budget and build context.
    try:
        payload = json.loads(raw_response)
        build = payload.get("build", {})
        strict_failed = isinstance(build, dict) and build.get("CPU") == "No matching product found"
    except Exception:
        strict_failed = False

    if strict_failed:
        strict_requirements = parse_build_capacity_requirements(combined_request)
        strict_component_constraints = parse_component_price_constraints(combined_request)
        strict_pref_signals = parse_build_preferences(combined_request)
        has_strict_constraints = bool(strict_requirements) or bool(strict_component_constraints) or bool(
            strict_pref_signals.get("cpu_brand")
            or strict_pref_signals.get("gpu") in {"yes", "no"}
            or strict_pref_signals.get("gpu_brand")
        )

        if has_strict_constraints:
            lowered = user_input.lower()
            show_queries = (
                "show sql" in lowered
                or "show queries" in lowered
                or "show sql queries" in lowered
            )
            return format_build_response_for_terminal(raw_response, show_queries=show_queries)

        relaxed_request = f"build me a pc under {last_budget}"
        raw_response = build_pc_response(relaxed_request)
        try:
            relaxed_payload = json.loads(raw_response)
            explanation = relaxed_payload.get("explanation", "")
            if prefs.get("cpu_brand"):
                relaxed_payload["explanation"] = (
                    f"Could not find a strict {prefs['cpu_brand'].upper()} build within this budget. "
                    f"Showing the best available compatible build instead. {explanation}"
                )
            raw_response = json.dumps(relaxed_payload, ensure_ascii=True)
        except Exception:
            pass

    lowered = user_input.lower()
    show_queries = (
        "show sql" in lowered
        or "show queries" in lowered
        or "show sql queries" in lowered
    )
    return format_build_response_for_terminal(raw_response, show_queries=show_queries)


def main() -> None:
    print("\nBDPriceGear Chatbot (type 'exit' to quit)\n" + "-" * 50)

    conversation: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are BDPriceGear assistant. Chat naturally for general questions. "
                "For any product/build/budget shopping request, only use database-grounded flows and never invent products, prices, shops, or links."
            ),
        }
    ]
    
    last_budget: Optional[int] = None
    last_lookup_context: Dict[str, str] = {}
    last_purchase_mode: Optional[str] = None
    last_build_preferences: Dict[str, str] = {}
    last_build_request: str = ""
    last_build_response_text: str = ""

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        route = plan_chat_route(
            user_input=user_input,
            last_budget=last_budget,
            last_purchase_mode=last_purchase_mode,
            has_lookup_context=bool(last_lookup_context),
        )

        if route == "build_min_budget":
            min_budget_query = last_build_request or user_input
            final_reply = estimate_minimum_build_budget_response(min_budget_query)
            last_purchase_mode = "build"
            last_build_response_text = final_reply
            append_chat_turn(conversation, user_input, final_reply)
            print("\nBot:\n" + final_reply + "\n")
            continue

        if route == "build":
            raw_response = build_pc_response(user_input)
            last_budget = parse_total_build_budget(user_input)
            last_lookup_context = {}
            last_purchase_mode = "build"
            last_build_preferences = parse_build_preferences(user_input)
            last_build_request = user_input
            lowered = user_input.lower()
            show_queries = (
                "show sql" in lowered
                or "show queries" in lowered
                or "show sql queries" in lowered
            )
            pretty_response = format_build_response_for_terminal(raw_response, show_queries=show_queries)

            final_reply = pretty_response
            last_build_response_text = final_reply
            append_chat_turn(conversation, user_input, final_reply)
            print("\nBot:\n" + final_reply + "\n")
            continue

        if route == "build_details":
            final_reply = last_build_response_text or "I do not have a recent build to show yet. Please ask me to build first."
            append_chat_turn(conversation, user_input, final_reply)
            print("\nBot:\n" + final_reply + "\n")
            continue

        if route == "build_ask_budget":
            final_reply = (
                "Sure, share your new total budget in BDT (for example: 80000 BDT), "
                "and I will rebuild using only your database products with price, shop, and link."
            )
            last_purchase_mode = "build"
            append_chat_turn(conversation, user_input, final_reply)
            print("\nBot:\n" + final_reply + "\n")
            continue

        if route in {"lookup", "lookup_followup"}:
            next_lookup = is_lookup_next_request(user_input)
            previous_limit = int(last_lookup_context.get("limit", 3) or 3)
            current_limit = parse_lookup_result_limit(user_input, default_limit=previous_limit)
            previous_offset = int(last_lookup_context.get("offset", 0) or 0)
            lookup_offset = previous_offset + previous_limit if next_lookup else 0
            current_mode = detect_lookup_mode(user_input) or last_lookup_context.get("mode")

            product_reply = product_lookup_response(
                user_input,
                context_component=last_lookup_context.get("component"),
                context_brand=last_lookup_context.get("brand"),
                context_mode=current_mode,
                offset=lookup_offset,
                limit=current_limit,
            )
            # Always update context for this lookup (success or failure)
            component = detect_component_intent(user_input) or last_lookup_context.get("component")
            brand = detect_brand_intent(user_input) or last_lookup_context.get("brand")
            if component:
                last_lookup_context["component"] = component
            if brand:
                last_lookup_context["brand"] = brand
            last_lookup_context["offset"] = lookup_offset
            last_lookup_context["limit"] = current_limit
            if current_mode:
                last_lookup_context["mode"] = current_mode
            
            last_purchase_mode = "lookup"
            
            if product_reply:
                # Successful lookup with products found
                final_reply = format_product_lookup_response(product_reply)
            else:
                # No products found - create helpful response
                wanted = f" {brand.upper()}" if brand else ""
                final_reply = (
                    f"I couldn't find any in-stock{wanted} {component.upper() if component else 'products'} "
                    f"in the current database. Could you try a different budget range or component type?"
                )
            
            append_chat_turn(conversation, user_input, final_reply)
            print("\nBot:\n" + final_reply + "\n")
            continue

        if route == "build_followup":
            updated_budget = parse_total_build_budget(user_input) or last_budget
            current_prefs = parse_build_preferences(user_input)
            merged_prefs = dict(last_build_preferences)
            merged_prefs.update(current_prefs)
            modified_build = build_with_context(
                user_input,
                updated_budget,
                preferences_override=merged_prefs,
                base_request=last_build_request,
            )
            if modified_build:
                last_budget = updated_budget
                last_purchase_mode = "build"
                last_build_preferences = merged_prefs
                last_build_request = f"{last_build_request} {user_input}".strip()
                final_reply = modified_build
                last_build_response_text = final_reply
                append_chat_turn(conversation, user_input, final_reply)
                print("\nBot:\n" + final_reply + "\n")
            else:
                # Failed to build with preferences - give feedback
                final_reply = (
                    f"I couldn't create a build with those preferences and the {last_budget} BDT budget. "
                    f"Please try different specifications or a higher budget."
                )
                append_chat_turn(conversation, user_input, final_reply)
                print("\nBot:\n" + final_reply + "\n")
            continue

        # Hard guardrail: never send shopping/build requests to generic LLM chat.
        if is_db_only_commerce_query(user_input) or (
            last_purchase_mode == "build"
            and (
                is_no_budget_followup(user_input)
                or is_build_continue_request(user_input)
                or is_build_budget_adjustment_request(user_input)
            )
        ):
            build_routes = {"build", "build_followup", "build_min_budget", "build_ask_budget", "build_details"}
            if route in build_routes:
                pass
            else:
                if last_purchase_mode == "build" and (
                    is_no_budget_followup(user_input)
                    or (is_build_continue_request(user_input) and parse_total_build_budget(user_input) is None)
                    or (is_build_budget_adjustment_request(user_input) and parse_total_build_budget(user_input) is None)
                ):
                    if is_build_budget_adjustment_request(user_input) and parse_total_build_budget(user_input) is None:
                        final_reply = (
                            "Sure, share your new total budget in BDT (for example: 80000 BDT), "
                            "and I will rebuild using only your database products with price, shop, and link."
                        )
                    else:
                        final_reply = estimate_minimum_build_budget_response(last_build_request or user_input)
                    last_purchase_mode = "build"
                    last_build_response_text = final_reply
                    append_chat_turn(conversation, user_input, final_reply)
                    print("\nBot:\n" + final_reply + "\n")
                    continue

                component = detect_component_intent(user_input)
                if component:
                    product_reply = product_lookup_response(user_input)
                    if product_reply:
                        final_reply = format_product_lookup_response(product_reply)
                    else:
                        final_reply = (
                            f"I could not find in-stock {component.upper()} products for that request in your database. "
                            "Please try another budget range or refine the component."
                        )
                    last_purchase_mode = "lookup"
                    last_lookup_context = {"component": component}
                    brand = detect_brand_intent(user_input)
                    if brand:
                        last_lookup_context["brand"] = brand
                    append_chat_turn(conversation, user_input, final_reply)
                    print("\nBot:\n" + final_reply + "\n")
                    continue

                build_reply = format_build_response_for_terminal(build_pc_response(user_input))
                final_reply = build_reply
                last_purchase_mode = "build"
                last_budget = parse_total_build_budget(user_input)
                last_build_preferences = parse_build_preferences(user_input)
                last_build_request = user_input
                last_build_response_text = final_reply
                append_chat_turn(conversation, user_input, final_reply)
                print("\nBot:\n" + final_reply + "\n")
                continue

        last_purchase_mode = None
        last_lookup_context = {}
        last_build_preferences = {}
        last_build_request = ""
        last_build_response_text = ""

        casual_reply = small_talk_response(user_input)
        if casual_reply:
            append_chat_turn(conversation, user_input, casual_reply)
            print("\nBot:\n" + casual_reply + "\n")
            continue

        if not is_pc_domain_general_question(user_input):
            final_reply = out_of_scope_pc_redirect_response()
            append_chat_turn(conversation, user_input, final_reply)
            print("\nBot:\n" + final_reply + "\n")
            continue

        conversation.append({"role": "user", "content": user_input})
        llm_reply = call_openrouter(conversation)
        if llm_reply is None:
            print("\nBot: API key is missing or OpenRouter request failed. Add OPENROUTER_API_KEY in .env.\n")
            continue

        conversation.append({"role": "assistant", "content": llm_reply})
        print("\nBot:", llm_reply, "\n")

    print("\nChat ended. Goodbye!")


if __name__ == "__main__":
    main()