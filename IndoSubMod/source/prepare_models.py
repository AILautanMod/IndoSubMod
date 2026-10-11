"""Prepare the speech model and optional offline English-to-Indonesian model."""

import argparse

from argostranslate import package, translate
from faster_whisper import WhisperModel


def main(install_offline_translation: bool = True):
    if install_offline_translation:
        print("Checking offline English → Indonesian translation model…", flush=True)
        installed = translate.get_installed_languages()
        english = next((language for language in installed if language.code == "en"), None)
        indonesian = next((language for language in installed if language.code == "id"), None)
        has_pair = english is not None and indonesian is not None and english.get_translation(indonesian) is not None
        if not has_pair:
            package.update_package_index()
            available = next(
                (item for item in package.get_available_packages() if item.from_code == "en" and item.to_code == "id"),
                None,
            )
            if available is None:
                raise RuntimeError("The Argos Translate en → id package is unavailable.")
            print("Downloading the offline en → id model…", flush=True)
            package.install_from_path(available.download())
    else:
        print("Skipping optional offline translation model…", flush=True)

    print("Downloading the multilingual Whisper small model…", flush=True)
    WhisperModel("small", device="cpu", compute_type="int8")
    print("Offline models are ready.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-offline-translation", action="store_true")
    arguments = parser.parse_args()
    main(install_offline_translation=not arguments.skip_offline_translation)
