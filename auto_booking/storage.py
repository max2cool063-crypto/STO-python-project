from whitenoise.storage import CompressedManifestStaticFilesStorage


class JazzminCompatibleCompressedManifestStaticFilesStorage(
    CompressedManifestStaticFilesStorage
):
    """Keep strict manifest hashing while supporting Jazzmin's theme base path.

    Jazzmin 3.0.5 renders ``{% static 'vendor/bootswatch' %}`` as a directory
    prefix and appends the selected theme path in JavaScript. Django's manifest
    storage only contains files, so that directory lookup would otherwise raise
    ``Missing staticfiles manifest entry`` even after a successful collectstatic.
    """

    JAZZMIN_BOOTSWATCH_BASE = "vendor/bootswatch"

    def stored_name(self, name):
        if name.rstrip("/") == self.JAZZMIN_BOOTSWATCH_BASE:
            return self.JAZZMIN_BOOTSWATCH_BASE
        return super().stored_name(name)
