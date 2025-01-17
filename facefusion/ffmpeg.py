from typing import List, Optional
import subprocess
import facefusion.globals
from facefusion import logger
from facefusion.typing import OutputVideoPreset, Fps, AudioBuffer
from facefusion.filesystem import get_temp_frames_pattern, get_temp_output_video_path

def run_ffmpeg(args: List[str]) -> bool:
    commands = ['ffmpeg', '-hide_banner', '-loglevel', 'error']
    commands.extend(args)
    try:
        subprocess.run(commands, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError as exception:
        logger.debug(exception.stderr.decode().strip(), __name__.upper())
        return False

def open_ffmpeg(args: List[str]) -> subprocess.Popen[bytes]:
    commands = ['ffmpeg', '-hide_banner', '-loglevel', 'error']
    commands.extend(args)
    return subprocess.Popen(commands, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def extract_frames(target_path: str, video_resolution: str, video_fps: Fps) -> bool:
    temp_frame_compression = round(31 - (facefusion.globals.temp_frame_quality * 0.31))
    trim_frame_start = facefusion.globals.trim_frame_start
    trim_frame_end = facefusion.globals.trim_frame_end
    temp_frames_pattern = get_temp_frames_pattern(target_path, '%04d')
    commands = ['-hwaccel', 'auto', '-i', target_path, '-q:v', str(temp_frame_compression), '-pix_fmt', 'rgb24']
    filter_str = ''
    if trim_frame_start is not None:
        filter_str += f'trim=start_frame={trim_frame_start}:'
    if trim_frame_end is not None:
        filter_str += f'trim=end_frame={trim_frame_end}:'
    filter_str += f'scale={video_resolution},fps={video_fps}'
    commands.extend(['-vf', filter_str])
    commands.extend(['-vsync', '0', temp_frames_pattern])
    return run_ffmpeg(commands)


def compress_image(output_path : str) -> bool:
	output_image_compression = round(31 - (facefusion.globals.output_image_quality * 0.31))
	commands = [ '-hwaccel', 'auto', '-i', output_path, '-q:v', str(output_image_compression), '-y', output_path ]
	return run_ffmpeg(commands)


def merge_video(target_path : str, video_resolution : str, video_fps : Fps) -> bool:
	temp_output_video_path = get_temp_output_video_path(target_path)
	temp_frames_pattern = get_temp_frames_pattern(target_path, '%04d')
	commands = [ '-hwaccel', 'auto', '-s', str(video_resolution), '-r', str(video_fps), '-i', temp_frames_pattern, '-c:v', facefusion.globals.output_video_encoder ]
	if facefusion.globals.output_video_encoder in [ 'libx264', 'libx265' ]:
		output_video_compression = round(51 - (facefusion.globals.output_video_quality * 0.51))
		commands.extend([ '-crf', str(output_video_compression), '-preset', facefusion.globals.output_video_preset ])
	if facefusion.globals.output_video_encoder in [ 'libvpx-vp9' ]:
		output_video_compression = round(63 - (facefusion.globals.output_video_quality * 0.63))
		commands.extend([ '-crf', str(output_video_compression) ])
	if facefusion.globals.output_video_encoder in [ 'h264_nvenc', 'hevc_nvenc' ]:
		output_video_compression = round(51 - (facefusion.globals.output_video_quality * 0.51))
		commands.extend([ '-cq', str(output_video_compression), '-preset', map_nvenc_preset(facefusion.globals.output_video_preset) ])
	commands.extend([ '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-y', temp_output_video_path ])
	return run_ffmpeg(commands)


def read_audio_buffer(target_path : str, sample_rate : int, channel_total : int) -> Optional[AudioBuffer]:
	commands = [ '-i', target_path, '-vn', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', str(sample_rate), '-ac', str(channel_total), '-' ]
	process = open_ffmpeg(commands)
	audio_buffer, error = process.communicate()
	if process.returncode == 0:
		return audio_buffer
	return None


def restore_audio(target_path : str, output_path : str, video_fps : Fps) -> bool:
	trim_frame_start = facefusion.globals.trim_frame_start
	trim_frame_end = facefusion.globals.trim_frame_end
	temp_output_video_path = get_temp_output_video_path(target_path)
	commands = [ '-hwaccel', 'auto', '-i', temp_output_video_path ]
	if trim_frame_start is not None:
		start_time = trim_frame_start / video_fps
		commands.extend([ '-ss', str(start_time) ])
	if trim_frame_end is not None:
		end_time = trim_frame_end / video_fps
		commands.extend([ '-to', str(end_time) ])
	commands.extend([ '-i', target_path, '-c', 'copy', '-map', '0:v:0', '-map', '1:a:0', '-shortest', '-y', output_path ])
	return run_ffmpeg(commands)


def replace_audio(target_path : str, audio_path : str, output_path : str) -> bool:
	temp_output_path = get_temp_output_video_path(target_path)
	commands = [ '-hwaccel', 'auto', '-i', temp_output_path, '-i', audio_path, '-c:v', 'copy', '-af', 'apad', '-shortest', '-map', '0:v:0', '-map', '1:a:0', '-y', output_path ]
	return run_ffmpeg(commands)


def map_nvenc_preset(output_video_preset : OutputVideoPreset) -> Optional[str]:
	if output_video_preset in [ 'ultrafast', 'superfast', 'veryfast' ]:
		return 'p1'
	if output_video_preset == 'faster':
		return 'p2'
	if output_video_preset == 'fast':
		return 'p3'
	if output_video_preset == 'medium':
		return 'p4'
	if output_video_preset == 'slow':
		return 'p5'
	if output_video_preset == 'slower':
		return 'p6'
	if output_video_preset == 'veryslow':
		return 'p7'
	return None
