class SubmissionStorageError(RuntimeError):
    """The dashboard could not open or query its read-only submission store."""

    def __init__(self):
        super().__init__(
            "Submission storage is unavailable. Check DATABASE_PATH and start the public interface."
        )
