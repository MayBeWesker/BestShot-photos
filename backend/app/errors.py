class BestShotError(Exception):
    def __init__(self, message: str, *, code: str = "processing_error", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class AlignmentError(BestShotError):
    def __init__(self, message: str):
        super().__init__(message, code="alignment_failed", status_code=422)


class InvalidMaskError(BestShotError):
    def __init__(self, message: str):
        super().__init__(message, code="invalid_mask", status_code=422)

