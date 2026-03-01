class NonRetryableTaskError(RuntimeError):
    """Raise inside handler to mark task FAILED without retries."""