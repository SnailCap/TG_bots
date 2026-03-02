class NonRetryableTaskError(RuntimeError):
    """Raise inside handler to mark task FAILED without retries."""


class UnknownTaskTypeError(NonRetryableTaskError):
    """No handler registered for task.task_type."""
