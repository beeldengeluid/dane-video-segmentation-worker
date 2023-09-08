import base_util
import logging

logger = logging.getLogger(__name__)
hecate_path="/hecate/distribute/bin/hecate" # TODO: test environment variable instead of specifying path here


def detect_shots_and_keyframes(media_file: str)-> tuple[list[tuple[int]],list[int]]:
    cmd = f'{hecate_path} \
            -i {media_file} \
            --print_shot_info \
            --print_keyfrm_info'
    # TODO: filter video according to optional timestamps in url 
    try:
        hecate_result = base_util.run_shell_command(cmd)
        logger.info(f'Hecate result: {hecate_result}')
    except:
        logger.exception(f'Skipping hecate for {media_file}')
        return    
    return interpret_hecate_output(hecate_result.decode()) # The units are frame indices (zero-based).


def interpret_hecate_output(hecate_result:str)-> tuple[list[tuple[int]],list[int]]:
    for line in hecate_result.split('\n'):
        if line.startswith('shots:'):
            shots = [tuple([int(timestamp) for timestamp in shot[1:-1].split(':')]) for shot in 
                        line[len('shots: '):].split(',')]
        elif line.startswith('keyframes:'):
            keyframes = [int(keyframe_index) for keyframe_index in line[len('keyframes: '):][1:-1].split(',')]
    return(shots,keyframes)

