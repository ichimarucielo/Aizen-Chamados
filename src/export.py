from pathlib import Path
from shutil import copy2


def create_output_copy(
    template_path: Path,
    output_path: Path,
) -> Path:
    """
    Cria uma cópia do template do Plano N2.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    copy2(
        src=template_path,
        dst=output_path,
    )

    return output_path