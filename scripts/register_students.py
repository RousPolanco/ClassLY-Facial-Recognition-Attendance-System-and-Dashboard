from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

from app.config import (
    FACES_DIR,
    EMBEDDINGS_DIR,
)
from app.database.database import initialize_database
from app.database.repositories import (
    get_or_create_student,
)


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


def parse_student_folder(
    folder_name: str,
) -> tuple[str, str]:
    """
    Extract the student's full name and student code
    from the folder name.

    Expected format:

        FULL_NAME_STUDENT_CODE

    Example:

        FABIO_MARTIN_ENRIQUEZ_2309148

    becomes:

        Full name: FABIO MARTIN ENRIQUEZ
        Student code: 2309148
    """

    if "_" not in folder_name:
        raise ValueError(
            "Folder name does not contain '_'."
        )

    full_name_part, student_code = (
        folder_name.rsplit("_", 1)
    )

    if not full_name_part or not student_code:
        raise ValueError(
            "Folder name must contain both "
            "a full name and student code."
        )

    full_name = full_name_part.replace(
        "_",
        " ",
    ).strip()

    student_code = student_code.strip()

    return full_name, student_code


def get_image_files(
    student_folder: Path,
) -> list[Path]:

    return sorted(
        file
        for file in student_folder.iterdir()
        if file.is_file()
        and file.suffix.lower()
        in SUPPORTED_EXTENSIONS
    )


def normalize_embedding(
    embedding: np.ndarray,
) -> np.ndarray:

    norm = np.linalg.norm(embedding)

    if norm == 0:
        raise ValueError(
            "Embedding has zero magnitude."
        )

    return embedding / norm


def generate_student_embedding(
    app: FaceAnalysis,
    image_files: list[Path],
) -> tuple[np.ndarray | None, int, int]:

    embeddings = []

    processed_images = 0
    skipped_images = 0

    for image_path in image_files:

        image = cv2.imread(
            str(image_path)
        )

        if image is None:
            print(
                f"  [SKIP] Could not read: "
                f"{image_path.name}"
            )

            skipped_images += 1
            continue

        faces = app.get(image)

        if len(faces) == 0:
            print(
                f"  [SKIP] No face detected: "
                f"{image_path.name}"
            )

            skipped_images += 1
            continue

        if len(faces) > 1:
            print(
                f"  [SKIP] Multiple faces detected: "
                f"{image_path.name}"
            )

            skipped_images += 1
            continue

        face = faces[0]

        embedding = getattr(
            face,
            "normed_embedding",
            None,
        )

        if embedding is None:
            embedding = normalize_embedding(
                face.embedding
            )

        else:
            embedding = normalize_embedding(
                embedding
            )

        embeddings.append(
            embedding
        )

        processed_images += 1

    if not embeddings:
        return (
            None,
            processed_images,
            skipped_images,
        )

    # Average all valid embeddings.
    mean_embedding = np.mean(
        np.stack(embeddings),
        axis=0,
    )

    mean_embedding = normalize_embedding(
        mean_embedding
    )

    return (
        mean_embedding,
        processed_images,
        skipped_images,
    )


def save_embedding(
    student_code: str,
    embedding: np.ndarray,
) -> Path:

    EMBEDDINGS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        EMBEDDINGS_DIR
        / f"{student_code}.npy"
    )

    np.save(
        output_path,
        embedding,
    )

    return output_path


def main() -> None:

    print("=" * 60)
    print("ClassLY Student Registration")
    print("=" * 60)

    initialize_database()

    FACES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    EMBEDDINGS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("\nLoading face recognition model...")

    face_app = FaceAnalysis(
        name="buffalo_l",
        providers=[
            "CPUExecutionProvider"
        ],
    )

    face_app.prepare(
        ctx_id=0,
        det_size=(640, 640),
    )

    print("Face model ready.\n")

    student_folders = sorted(
        folder
        for folder in FACES_DIR.iterdir()
        if folder.is_dir()
    )

    if not student_folders:
        print(
            "No student folders were found."
        )
        return

    print(
        f"Found {len(student_folders)} "
        f"student folder(s).\n"
    )

    registered_count = 0
    failed_count = 0

    total_images = 0
    successful_images = 0
    skipped_images = 0

    for student_folder in student_folders:

        print("-" * 60)
        print(
            f"Processing: "
            f"{student_folder.name}"
        )

        try:
            full_name, student_code = (
                parse_student_folder(
                    student_folder.name
                )
            )

        except ValueError as error:

            print(
                f"  [ERROR] {error}"
            )

            failed_count += 1
            continue

        print(
            f"  Name: {full_name}"
        )

        print(
            f"  Student code: {student_code}"
        )

        image_files = get_image_files(
            student_folder
        )

        if not image_files:

            print(
                "  [ERROR] No supported images "
                "were found."
            )

            failed_count += 1
            continue

        print(
            f"  Images found: "
            f"{len(image_files)}"
        )

        total_images += len(image_files)

        student = get_or_create_student(
            student_code=student_code,
            full_name=full_name,
        )

        print(
            f"  SQLite student ID: "
            f"{student['id']}"
        )

        embedding, processed, skipped = (
            generate_student_embedding(
                app=face_app,
                image_files=image_files,
            )
        )

        successful_images += processed
        skipped_images += skipped

        if embedding is None:

            print(
                "  [ERROR] No valid face "
                "embeddings were generated."
            )

            failed_count += 1
            continue

        output_path = save_embedding(
            student_code=student_code,
            embedding=embedding,
        )

        print(
            f"  Valid images: {processed}"
        )

        print(
            f"  Skipped images: {skipped}"
        )

        print(
            f"  Embedding saved: "
            f"{output_path.name}"
        )

        print("  [OK] Student registered.")

        registered_count += 1

    print("\n")
    print("=" * 60)
    print("Registration Summary")
    print("=" * 60)

    print(
        f"Student folders found: "
        f"{len(student_folders)}"
    )

    print(
        f"Students processed successfully: "
        f"{registered_count}"
    )

    print(
        f"Students with errors: "
        f"{failed_count}"
    )

    print(
        f"Total images found: "
        f"{total_images}"
    )

    print(
        f"Images processed successfully: "
        f"{successful_images}"
    )

    print(
        f"Images skipped: "
        f"{skipped_images}"
    )

    print(
        f"\nEmbeddings directory: "
        f"{EMBEDDINGS_DIR}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()