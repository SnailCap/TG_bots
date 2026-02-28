class RenderableNotFoundError(Exception):
    def __init__(self, name: str):
        super().__init__(f"Renderable '{name}' not found in config.")

class EmptyRenderableTextError(Exception):
    def __init__(self, name: str):
        super().__init__(f"Renderable '{name}' has no text.")
