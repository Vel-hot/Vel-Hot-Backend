class DataSourceUnavailable(Exception):
    """Levée quand S3 ou Athena est inaccessible / mal configuré.

    Capturée par un exception handler dans main.py pour retourner
    un 503 propre au lieu d'un 500 brut.
    """
    def __init__(self, source: str, detail: str):
        self.source = source   # "S3" ou "Athena"
        self.detail = detail
        super().__init__(f"[{source}] {detail}")
