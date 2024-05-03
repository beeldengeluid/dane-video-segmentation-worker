import logging
import os
from time import time
from dane.provenance import Provenance, obtain_software_versions
from models import OutputType, ScenedetectOutput, MediaFile
from scenedetect import SceneManager, open_video, ContentDetector, scene_manager


logger = logging.getLogger(__name__)


class ScenedetectFailureException(Exception):
    pass


def _get_keyframe_dir(output_dir: str) -> str:
    return os.path.join(output_dir, OutputType.KEYFRAMES.value)


def _get_metadata_path(output_dir: str, kind: str) -> str:
    if kind == 'shot_boundaries':
        return os.path.join(
            output_dir, OutputType.METADATA.value, ScenedetectOutput.SHOT_BOUNDARIES.value
        )
    if kind == 'keyframes':
        return os.path.join(
            output_dir,
            OutputType.METADATA.value,
            ScenedetectOutput.KEYFRAME_TIMESTAMPS.value,
        )
    else:
        raise Exception() 


def run(
    media_file: MediaFile,
    output_dir: str,
    extract_keyframes=False,
) -> Provenance:
    logger.info(f"Running scenedetect on {media_file}")
    start_time = time()
    keyframe_dir = _get_keyframe_dir(output_dir)

    try:
        video = open_video(media_file.file_path)
    except Exception:
        logger.error(
            f"Failed to run scenedetect on {media_file.file_path}: "
            "Could not open video."
        )
        raise ScenedetectFailureException()
    video_scene_manager = SceneManager()
    video_scene_manager.add_detector(ContentDetector())
    # Detect all scenes in video from current position to end.
    video_scene_manager.detect_scenes(video)
    # `get_scene_list` returns a list of start/end timecode pairs
    # for each scene that was found.
    scene_list = video_scene_manager.get_scene_list()  
    shot_boundaries_path = _get_metadata_path(output_dir=output_dir, kind='shot_boundaries')
    with open(shot_boundaries_path, "w") as f:
        f.write(str(get_shot_boundaries(scene_list=scene_list)))
    output_data = {"shot_boundaries": shot_boundaries_path}

    if extract_keyframes:
        logger.info("Also telling scenedetect to extract keyframes")
        keyframe_dir = _get_keyframe_dir(output_dir)
        image_paths = scene_manager.save_images(
            scene_list=scene_list,
            video=video,
            num_images=1,
            image_extension="jpg",
            encoder_param=100,
            output_dir=keyframe_dir,
            image_name_template="$TIMESTAMP_MS",
        )
        output_data["keyframe_dir"] = keyframe_dir
        keyframes_path = _get_metadata_path(output_dir=output_dir, kind='keyframes')
        with open(keyframes_path, "w") as f:
            f.write(str(get_keyframes_timestamps(image_paths)))
        output_data["keyframe_timestamps"] = keyframes_path

    return Provenance(
        activity_name="Python Scenedetect",
        activity_description="Shot detection & keyframe extraction",
        start_time_unix=start_time,
        processing_time_ms=(time() - start_time) * 1000,
        software_version=obtain_software_versions(["scenedetect"]),
        input_data={"input_file": media_file.file_path},
        output_data=output_data,
    )


def get_shot_boundaries(scene_list):
    return [
        tuple(int(scene[i].get_seconds() * 1000) for i in (0, 1))
        for scene in scene_list
    ]


def get_keyframes_timestamps(image_paths):
    return [
        int(filename.split('.')[0])
        for v in image_paths.values()
        for filename in v
    ]


if __name__ == "__main__":
    media_file = MediaFile(file_path="data/input-files/1411058.1366653.WEEKNUMMER404-HRE000042FF_924200_1089200.mp4", source_id='source_id')
    provenance = run(
        media_file=media_file,
        output_dir='tmp',
        extract_keyframes=True,
    )
