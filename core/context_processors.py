def default_store(request):
    from core.store_access import user_can_pick_stores, user_has_store_access
    from core.store_selection import (
        get_selected_store_ids,
        resolve_write_store,
        selected_stores_queryset,
        selection_label,
        show_store_column,
    )

    store = getattr(request, "default_store", None)
    if callable(store):
        store = store()
    ctx = {"default_store": store}
    if getattr(request, "user", None) and request.user.is_authenticated:
        try:
            ctx["write_store"] = resolve_write_store(request)
        except ValueError:
            ctx["write_store"] = store
        ctx["store_selection_label"] = selection_label(request)
        ctx["selected_stores"] = selected_stores_queryset(request)
        ctx["show_store_column"] = show_store_column(request)
        ctx["user_can_pick_stores"] = user_can_pick_stores(request.user)
        ctx["has_store_access"] = user_has_store_access(request.user)
        sel = get_selected_store_ids(request)
        ctx["uses_write_store_hint"] = user_can_pick_stores(request.user) and (
            sel is None or len(sel or []) != 1
        )
    else:
        ctx["write_store"] = None
        ctx["store_selection_label"] = ""
        ctx["selected_stores"] = []
        ctx["show_store_column"] = False
        ctx["user_can_pick_stores"] = False
        ctx["has_store_access"] = False
        ctx["uses_write_store_hint"] = False
    return ctx
