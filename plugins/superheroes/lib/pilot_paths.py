"""Shared path containment helpers for pilot modules."""
import os


def path_components(path):
    parts = os.path.realpath(path).split(os.sep)
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def is_inside(path, root):
    """Return True when ``path`` is the same as or under ``root``."""
    path_parts = path_components(path)
    root_parts = path_components(root)
    if len(path_parts) < len(root_parts):
        return False
    return path_parts[:len(root_parts)] == root_parts
