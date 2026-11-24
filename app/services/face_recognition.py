from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

from app.config import EMBEDDINGS_DIR


class FaceRecognitionService:
    """
    Face recognition service for ClassLY.

    Responsibilities:
    - Load the InsightFace model.
    - Load registered student embeddings.
    - Detect faces in an image.
    - Generate face embeddings.
    - Compare detected faces against registered students.
    - Determine whether a face is known or unknown.
    """

    def __init__(
        self,
        model_name: str = "buffalo_l",
        threshold: float = 0.65,
    ) -> None:

        self.model_name = model_name
        self.threshold = threshold

        self.face_app = FaceAnalysis(
            name=self.model_name,
            providers=[
                "CPUExecutionProvider"
            ],
        )

        self.face_app.prepare(
            ctx_id=0,
            det_size=(640, 640),
        )

        self.embeddings = (
            self._load_embeddings()
        )

    # ========================================================
    # EMBEDDINGS
    # ========================================================

    def _load_embeddings(self) -> dict[str, np.ndarray]:
        """
        Load all registered student embeddings.

        Files are expected to have the format:

            data/embeddings/STUDENT_CODE.npy
        """

        embeddings = {}

        EMBEDDINGS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        for file in sorted(
            EMBEDDINGS_DIR.glob("*.npy")
        ):

            student_code = file.stem

            embedding = np.load(
                file
            )

            embedding = self._normalize(
                embedding
            )

            embeddings[
                student_code
            ] = embedding

        return embeddings

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize(
        embedding: np.ndarray,
    ) -> np.ndarray:
        """
        Normalize an embedding to unit length.
        """

        norm = np.linalg.norm(
            embedding
        )

        if norm == 0:
            raise ValueError(
                "Embedding has zero magnitude."
            )

        return embedding / norm

    # ========================================================
    # SIMILARITY
    # ========================================================

    @staticmethod
    def _cosine_similarity(
        embedding_a: np.ndarray,
        embedding_b: np.ndarray,
    ) -> float:
        """
        Calculate cosine similarity between
        two normalized embeddings.
        """

        embedding_a = (
            FaceRecognitionService._normalize(
                embedding_a
            )
        )

        embedding_b = (
            FaceRecognitionService._normalize(
                embedding_b
            )
        )

        return float(
            np.dot(
                embedding_a,
                embedding_b,
            )
        )

    # ========================================================
    # RECOGNITION
    # ========================================================

    def recognize_face(
        self,
        face,
    ) -> dict:
        """
        Recognize a single detected face.

        Returns the best candidate, second-best
        candidate, similarity score and whether
        the face is considered known.
        """

        embedding = getattr(
            face,
            "normed_embedding",
            None,
        )

        if embedding is None:

            embedding = face.embedding

        embedding = self._normalize(
            embedding
        )

        if not self.embeddings:

            return {
                "student_code": None,
                "similarity": 0.0,
                "second_best_similarity": 0.0,
                "is_known": False,
            }

        similarities = {}

        for (
            student_code,
            reference_embedding,
        ) in self.embeddings.items():

            similarities[
                student_code
            ] = self._cosine_similarity(
                embedding,
                reference_embedding,
            )

        ranked = sorted(
            similarities.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        best_code, best_similarity = (
            ranked[0]
        )

        if len(ranked) > 1:

            second_best_code, (
                second_best_similarity
            ) = ranked[1]

        else:

            second_best_code = None
            second_best_similarity = 0.0

        is_known = (
            best_similarity
            >= self.threshold
        )

        return {
            "student_code": (
                best_code
                if is_known
                else None
            ),
            "candidate_code": best_code,
            "similarity": best_similarity,
            "second_best_code": (
                second_best_code
            ),
            "second_best_similarity": (
                second_best_similarity
            ),
            "is_known": is_known,
        }

    # ========================================================
    # IMAGE RECOGNITION
    # ========================================================

    def recognize_image(
        self,
        image: np.ndarray,
    ) -> list[dict]:
        """
        Detect and recognize all faces in an image.

        Returns one result dictionary per detected face.
        """

        faces = self.face_app.get(
            image
        )

        results = []

        for face in faces:

            result = self.recognize_face(
                face
            )

            result["bbox"] = (
                face.bbox.tolist()
                if face.bbox is not None
                else None
            )

            results.append(
                result
            )

        return results

    def recognize_image_file(
        self,
        image_path: str | Path,
    ) -> list[dict]:
        """
        Load an image from disk and recognize
        all faces in it.
        """

        image = cv2.imread(
            str(image_path)
        )

        if image is None:

            raise ValueError(
                f"Could not read image: "
                f"{image_path}"
            )

        return self.recognize_image(
            image
        )

    # ========================================================
    # INFORMATION
    # ========================================================

    def reload_embeddings(self) -> None:
        """
        Reload embeddings from disk.

        Useful when new students are registered
        while the application is not restarted.
        """

        self.embeddings = (
            self._load_embeddings()
        )

    def get_registered_student_count(
        self,
    ) -> int:
        """
        Return the number of registered
        student embeddings.
        """

        return len(
            self.embeddings
        )