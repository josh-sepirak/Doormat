"""Execute an ApiRecipe against a JSON body and emit an ExtractedListing.

Pure function; no I/O. The caller (Mode A0 or the validator) is responsible
for the HTTP fetch.
"""

from __future__ import annotations

from typing import Any

from doormat.extraction.schemas import ApiRecipe, ExtractedListing
from doormat.schemas import PetsPolicy


def extract_listing_via_recipe(
    recipe: ApiRecipe, response_json: Any
) -> ExtractedListing:
    """Walk response_json by recipe.response_root, then by each field_path.
    
    Args:
        recipe: The ApiRecipe with response_root and field_paths.
        response_json: The parsed JSON response from the API.
        
    Returns:
        An ExtractedListing with all required fields populated.
        
    Raises:
        ValueError: If response_root doesn't resolve or required fields are missing.
    """
    root = _walk_path(response_json, recipe.response_root)
    if root is None:
        raise ValueError(f"response_root '{recipe.response_root}' resolved to None")

    def get(field: str) -> Any:
        path = recipe.field_paths.get(field)
        if not path:
            return None
        return _walk_path(root, path)

    address = get("address")
    rent = get("rent")
    bedrooms = get("bedrooms")
    bathrooms = get("bathrooms")
    sqft = get("sqft")
    pets = get("pets_policy")
    amenities = get("amenities") or []
    photos = get("photos") or []
    description = get("description") or ""

    # Validate required fields
    if address is None:
        raise ValueError("required field 'address' resolved to None")
    if rent is None:
        raise ValueError("required field 'rent' resolved to None")
    if bedrooms is None:
        raise ValueError("required field 'bedrooms' resolved to None")
    if bathrooms is None:
        raise ValueError("required field 'bathrooms' resolved to None")

    return ExtractedListing(
        address=str(address),
        rent=int(float(rent)),
        bedrooms=int(bedrooms),
        bathrooms=float(bathrooms),
        sqft=int(sqft) if sqft is not None else None,
        pets_policy=_coerce_pets_policy(pets),
        amenities=[str(a) for a in amenities][:20] if isinstance(amenities, list) else [],
        photos=[str(p) for p in photos][:20] if isinstance(photos, list) else [],
        description=str(description)[:2000],
    )


def _walk_path(obj: Any, path: str) -> Any:
    """Minimal JSONPath subset: $, $.key, $.list[N], $.key.subkey.
    
    Args:
        obj: The object to traverse (dict or list).
        path: JSONPath expression.
        
    Returns:
        The value at the path, or None if not found.
    """
    if path == "$" or path == "":
        return obj
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]

    cur = obj
    for token in _tokenize_path(path):
        if cur is None:
            return None
        if isinstance(token, int):
            if not isinstance(cur, list) or token >= len(cur):
                return None
            cur = cur[token]
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(token)
    return cur


def _tokenize_path(path: str) -> list[int | str]:
    """Split 'data.listings[0].name' into ['data', 'listings', 0, 'name']."""
    out: list[int | str] = []
    for part in path.split("."):
        if "[" in part:
            key, _, rest = part.partition("[")
            if key:
                out.append(key)
            while rest:
                idx_str, _, rest = rest.partition("]")
                if idx_str:
                    out.append(int(idx_str))
                if rest.startswith("["):
                    rest = rest[1:]
        else:
            if part:
                out.append(part)
    return out


def _coerce_pets_policy(raw: Any) -> PetsPolicy:
    """Heuristic coercion from various API pet policy representations to PetsPolicy enum."""
    if raw is None:
        return PetsPolicy.UNKNOWN
    if isinstance(raw, PetsPolicy):
        return raw
    s = str(raw).lower()
    if "no" in s and ("pet" in s or "dog" in s):
        return PetsPolicy.NONE_ALLOWED
    if "cat" in s and "only" in s:
        return PetsPolicy.CATS_ONLY
    if any(t in s for t in ["allow", "ok", "welcome", "consider", "small dog"]):
        return PetsPolicy.ALLOWED_WITH_SMALL_DOG
    return PetsPolicy.UNKNOWN
