def default_store(request):
    store = getattr(request, "default_store", None)
    if callable(store):
        store = store()
    return {"default_store": store}
