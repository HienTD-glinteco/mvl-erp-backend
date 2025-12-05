import re


def _parse_tag_for_sorting(tag):
    """
    Parse tag to extract numeric prefix for proper sorting.
    For example: "0.8: Geographic" -> (0, 8, 0, "Geographic")
                 "1.1: Auth" -> (1, 1, 0, "Auth")
                 "9.2.10: Asset Allocation" -> (9, 2, 10, "Asset Allocation")
                 "10.2: Decision" -> (10, 2, 0, "Decision")
                 "Geographic" -> (999999, 0, 0, "Geographic")
    """
    if not tag:
        return (999999, 0, 0, "")

    # Match pattern like "1.2.3: Name" or "9.2.10: Name" (with colon, up to 3 numeric parts)
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?:\s+(.*)$", tag)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2)) if match.group(2) else 0
        patch = int(match.group(3)) if match.group(3) else 0
        name = match.group(4)
        return (major, minor, patch, name)

    # Fallback: Match old format "1.2.3 Name" (without colon) for backward compatibility
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?\s+(.*)$", tag)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2)) if match.group(2) else 0
        patch = int(match.group(3)) if match.group(3) else 0
        name = match.group(4)
        return (major, minor, patch, name)

    # No numeric prefix, sort at the end
    return (999999, 0, 0, tag)


def sort_schema_by_tags(result, generator, request, public):
    """
    Post-processing hook that sorts the OpenAPI schema paths and tags numerically.

    This runs AFTER schema generation, when tags are available.
    """
    if not isinstance(result, dict) or "paths" not in result:
        return result

    # Sort the tags array numerically if it exists
    if "tags" in result and isinstance(result["tags"], list):
        result["tags"] = sorted(result["tags"], key=lambda tag_obj: _parse_tag_for_sorting(tag_obj.get("name", "")))

    paths = result["paths"]

    # Create a list of (path, operations) tuples with their primary tag for sorting
    path_items = []
    for path, operations in paths.items():
        # Get the first operation's first tag
        primary_tag = ""
        for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
            if method in operations:
                tags = operations[method].get("tags", [])
                if tags:
                    primary_tag = tags[0]
                    break

        path_items.append((path, operations, primary_tag))

    # Sort by tag (numerically), then by path
    def sort_key(item):
        path, operations, tag = item
        tag_key = _parse_tag_for_sorting(tag)
        # Sort foo{arg} after foo/, but before foo/bar
        sorted_path = path
        if sorted_path.endswith("/"):
            sorted_path = sorted_path[:-1] + " "
        sorted_path = sorted_path.replace("{", "!")
        return (tag_key, sorted_path)

    sorted_items = sorted(path_items, key=sort_key)

    # Rebuild the paths dict in sorted order
    sorted_paths = {}
    for path, operations, _ in sorted_items:
        sorted_paths[path] = operations

    result["paths"] = sorted_paths
    return result
