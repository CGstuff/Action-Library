def register_all():
    from ..preferences import register_preferences
    from ..properties import register_properties
    from ..operators import register_operators
    from ..panels import register_panels

    register_preferences()
    register_properties()
    register_operators()
    register_panels()
def unregister_all():
    from ..preferences import unregister_preferences
    from ..properties import unregister_properties
    from ..operators import unregister_operators
    from ..panels import unregister_panels

    unregister_panels()
    unregister_operators()
    unregister_properties()
    unregister_preferences()