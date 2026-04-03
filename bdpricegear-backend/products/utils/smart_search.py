# Lightweight rule-based navbar search.

import re


class SmartSearchEngine:
    MAIN_PRODUCTS = ('laptop', 'desktop', 'pc', 'computer')
    COMPONENTS = ('ram', 'ssd', 'hdd', 'gpu', 'processor', 'cpu', 'motherboard')
    COOLING_TERMS = ('cpu cooler', 'cooler', 'heatsink', 'water block', 'cpu fan', 'liquid cooler')

    def normalize_query(self, query: str) -> str:
        normalized = query.lower().strip()
        normalized = re.sub(r'\bdd\s*([3-6])\b', r'ddr\1', normalized)
        normalized = re.sub(r'\bddr\s*([3-6])\b', r'ddr\1', normalized)
        normalized = re.sub(r'(\d+)\s*(gb|tb)\b', r'\1\2', normalized)
        return ' '.join(normalized.split())

    def detect_category(self, query: str) -> str:
        if any(term in query for term in self.COOLING_TERMS):
            return 'cooling'

        for category in self.MAIN_PRODUCTS:
            if re.search(rf'\b{re.escape(category)}\b', query):
                return category

        for category in self.COMPONENTS:
            if re.search(rf'\b{re.escape(category)}\b', query):
                return 'processor' if category == 'cpu' else category

        return 'unknown'

    def extract_attributes(self, query: str) -> dict:
        attributes = {}

        capacity_match = re.search(r'\b(\d+)(gb|tb)\b', query)
        if capacity_match:
            attributes['capacity'] = f"{capacity_match.group(1)}{capacity_match.group(2)}"

        ram_generation_match = re.search(r'\bddr([3-6])\b', query)
        if ram_generation_match:
            attributes['ram_generation'] = f"ddr{ram_generation_match.group(1)}"

        return attributes


def apply_smart_search(queryset, query: str):
    from django.db.models import Q
    from products.models import Category

    engine = SmartSearchEngine()
    normalized = engine.normalize_query(query)
    category = engine.detect_category(normalized)
    attributes = engine.extract_attributes(normalized)

    def text_query(*terms):
        predicate = Q()
        for term in terms:
            predicate |= Q(name__icontains=term) | Q(description__icontains=term)
        return predicate

    cooling_query = text_query('cpu cooler', 'cooler', 'heatsink', 'water block', 'cpu fan', 'liquid cooler')
    processor_query = text_query('processor', 'cpu', 'core', 'ryzen', 'intel', 'amd', 'xeon', 'epyc', 'athlon', 'pentium')

    if category == 'cooling':
        return queryset.filter(cooling_query).order_by('-updated_at')

    if category == 'processor':
        processor_category = Category.objects.filter(
            Q(slug='processor') | Q(name__iexact='processor')
        ).first()

        if processor_category:
            queryset = queryset.filter(category=processor_category)
        else:
            queryset = queryset.filter(processor_query)

        return queryset.exclude(cooling_query).order_by('-updated_at')

    if category != 'unknown':
        matched_category = Category.objects.filter(
            Q(slug=category) | Q(name__iexact=category)
        ).first()

        if matched_category:
            queryset = queryset.filter(category=matched_category)
        else:
            queryset = queryset.filter(text_query(category))

        if category in ('ram', 'ssd', 'hdd', 'gpu') and attributes.get('capacity'):
            queryset = queryset.filter(text_query(attributes['capacity']))

        if category == 'ram' and attributes.get('ram_generation'):
            queryset = queryset.filter(text_query(attributes['ram_generation']))

        return queryset.order_by('-updated_at')

    filters = Q()
    if attributes.get('capacity'):
        filters |= text_query(attributes['capacity'])
    if attributes.get('ram_generation'):
        filters |= text_query(attributes['ram_generation'])

    if filters:
        return queryset.filter(filters).order_by('-updated_at')

    return queryset.filter(text_query(normalized)).order_by('-updated_at')
