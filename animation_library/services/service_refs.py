"""
Deferred service references.

THE PROBLEM
    Library-bound services are module-level singletons. Switching library at
    runtime resets those singletons - but any object that did

        self._db_service = get_database_service()      # in __init__

    froze the OLD instance and keeps using it. There's no crash and no error: it
    just quietly reads the previous library. Long-lived widgets (the folder tree,
    the model, the toolbar, the controllers) are all constructed once at startup,
    so every one of them is a place this can happen.

    The obvious fix - "re-inject the new service into everything after a switch" -
    fails the same way: it's a step you have to remember, for every object, every
    time someone adds one. A missed entry is invisible.

THE FIX
    Make the attribute a property that asks the accessor on EVERY use, so there's
    nothing to go stale. The accessors are just a None-check and a return, so this
    costs nothing measurable.

        class FolderTree(QTreeWidget):
            _db_service = service_ref(get_database_service, '_injected_db_service')

            def __init__(self, db_service=None):
                self._injected_db_service = db_service   # None in production

        # every existing call site keeps working unchanged:
        self._db_service.get_all_folders()

    Dependency injection still wins: if something was explicitly injected (tests),
    that instance is returned instead of the singleton.

    IMPORTANT for callers that pass services down to children: propagate the
    INJECTED value (self._injected_db_service), not the resolved property. Passing
    the resolved value re-freezes it in the child and reintroduces the bug.
"""

from typing import Any, Callable


def service_ref(accessor: Callable[[], Any], injected_attr: str) -> property:
    """A read-only attribute that resolves a service on every access.

    Args:
        accessor: The singleton accessor, e.g. get_database_service.
        injected_attr: Name of the instance attribute holding an explicitly
            injected instance (or None). When set, it takes precedence.

    Returns:
        A property. Deliberately has no setter - assigning would re-create the
        staleness this exists to prevent.
    """
    def getter(self):
        injected = getattr(self, injected_attr, None)
        return injected if injected is not None else accessor()

    getter.__doc__ = (
        f"Resolved via {accessor.__name__}() on each access "
        f"(or {injected_attr} if injected). Never cached - see service_refs.py."
    )
    return property(getter)


__all__ = ['service_ref']
