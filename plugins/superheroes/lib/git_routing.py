"""The one home of the git routing-variable list (stdlib only, no imports).

Environment variables that redirect where git looks for a repository, its index, its objects or its
configuration. Every module that scrubs a git child's environment imports this tuple; none keeps a copy.
"""

GIT_ROUTING_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_EXTERNAL_DIFF",
    "GIT_REPLACE_REF_BASE",
)
