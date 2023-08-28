import base_util
import logging

logger = logging.getLogger(__name__)
hecate_path="hecate/distribute/bin/hecate" # TODO: test environment variable instead of specifying path here

def detect_shots(media_file: str, keyframes_dir: str)-> tuple[list[(str,str)],list[str]]:
    cmd = f'{hecate_path} \
            -i {media_file} \
            -o {keyframes_dir} \
            --print_shot_info \
            --print_keyfrm_info'
    # TODO: filter video according to timestamps in url 
    try:
        hecate_result = base_util.run_shell_command(cmd)
        logger.info(f'Hecate result: {hecate_result}')
    except:
        logger.exception(f'Skipping hecate for {media_file}')
        return 
    
    pos_map = []
    msec_map = []

    while True:
        ret = vcap.grab()
        if not ret:
            break
        msec_map.append(vcap.get(cv2.CAP_PROP_POS_MSEC))
        pos_map.append(vcap.get(cv2.CAP_PROP_POS_FRAMES))
        frame_count += 1
    vcap.release()


    for line in hecate_result.split('\n'):
        if line.startswith('shots:'):
            shots = [tuple(shot[1:-1].split(':')) for shot in 
                        line[len('shots: '):].split(',')]

            shots_pos = [(pos_map[int(start)], pos_map[int(end)]) for (start, end) in shots]
            shots_msec = [(msec_map[int(start)], msec_map[int(end)]) for (start, end) in shots]
        elif line.startswith('keyframes:'):
            keyframes = line[len('keyframes: '):][1:-1].split(',')
            keyframes_pos = [int(pos_map[int(kf)]) for kf in keyframes]
            keyframes_msec = [msec_map[int(kf)] for kf in keyframes]
        elif line.startswith('hecate: thumbnail indices:'):
            thumbnails_idx = line[len('hecate: thumbnail indices: '):][2:-2].split(' ')
            thumbnails_idx = [int(t) for t in thumbnails_idx]
        # TODO: implement
        list_of_shots = []
        list_of_keyframe_timecodes = []
        return (list_of_shots, list_of_keyframe_timecodes)