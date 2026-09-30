class DatabaseNotReady(Exception):
    """DB가 준비되지 않았을 때 사용하는 오류."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)