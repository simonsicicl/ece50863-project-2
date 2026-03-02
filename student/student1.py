from typing import List

# Adapted from code by Zach Peats

# ======================================================================================================================
# Do not touch the client message class!
# ======================================================================================================================


class ClientMessage:
	"""
	This class will be filled out and passed to student_entrypoint for your algorithm.
	"""
	total_seconds_elapsed: float	  # The number of simulated seconds elapsed in this test
	previous_throughput: float		  # The measured throughput for the previous chunk in kB/s

	buffer_current_fill: float		    # The number of kB currently in the client buffer
	buffer_seconds_per_chunk: float     # Number of seconds that it takes the client to watch a chunk. Every
										# buffer_seconds_per_chunk, a chunk is consumed from the client buffer.
	buffer_seconds_until_empty: float   # The number of seconds of video left in the client buffer. A chunk must
										# be finished downloading before this time to avoid a rebuffer event.
	buffer_max_size: float              # The maximum size of the client buffer. If the client buffer is filled beyond
										# maximum, then download will be throttled until the buffer is no longer full

	# The quality bitrates are formatted as follows:
	#
	#   quality_levels is an integer reflecting the # of quality levels you may choose from.
	#
	#   quality_bitrates is a list of floats specifying the number of kilobytes the upcoming chunk is at each quality
	#   level. Quality level 2 always costs twice as much as quality level 1, quality level 3 is twice as big as 2, and
	#   so on.
	#       quality_bitrates[0] = kB cost for quality level 1
	#       quality_bitrates[1] = kB cost for quality level 2
	#       ...
	#
	#   upcoming_quality_bitrates is a list of quality_bitrates for future chunks. Each entry is a list of
	#   quality_bitrates that will be used for an upcoming chunk. Use this for algorithms that look forward multiple
	#   chunks in the future. Will shrink and eventually become empty as streaming approaches the end of the video.
	#       upcoming_quality_bitrates[0]: Will be used for quality_bitrates in the next student_entrypoint call
	#       upcoming_quality_bitrates[1]: Will be used for quality_bitrates in the student_entrypoint call after that
	#       ...
	#
	quality_levels: int
	quality_bitrates: List[float]
	upcoming_quality_bitrates: List[List[float]]

	# You may use these to tune your algorithm to each user case! Remember, you can and should change these in the
	# config files to simulate different clients!
	#
	#   User Quality of Experience =    (Average chunk quality) * (Quality Coefficient) +
	#                                   -(Number of changes in chunk quality) * (Variation Coefficient)
	#                                   -(Amount of time spent rebuffering) * (Rebuffering Coefficient)
	#
	#   *QoE is then divided by total number of chunks
	#
	quality_coefficient: float
	variation_coefficient: float
	rebuffering_coefficient: float
# ======================================================================================================================


# Your helper functions, variables, classes here. You may also write initialization routines to be called
# when this script is first imported and anything else you wish.

# Global state
_in_startup = True 
_prev_quality = 0 
_throughput_history = []
_chunk_count = 0

def student_entrypoint(client_message: ClientMessage):
	"""
	Your mission, if you choose to accept it, is to build an algorithm for chunk bitrate selection that provides
	the best possible experience for users streaming from your service.

	Construct an algorithm below that selects a quality for a new chunk given the parameters in ClientMessage. Feel
	free to create any helper function, variables, or classes as you wish.

	Simulation does ~NOT~ run in real time. The code you write can be as slow and complicated as you wish without
	penalizing your results. Focus on picking good qualities!

	Also remember the config files are built for one particular client. You can (and should!) adjust the QoE metrics to
	see how it impacts the final user score. How do algorithms work with a client that really hates rebuffering? What
	about when the client doesn't care about variation? For what QoE coefficients does your algorithm work best, and
	for what coefficients does it fail?

	Args:
		client_message : ClientMessage holding the parameters for this chunk and current client state.

	:return: float Your quality choice. Must be one in the range [0 ... quality_levels - 1] inclusive.
	"""
	# return 0  # Let's see what happens if we select the lowest bitrate every time

	global _in_startup, _prev_quality, _throughput_history, _chunk_count

	def _harmonic_mean(values):
		positive = [v for v in values if v > 0]
		if not positive:
			return 0.0
		return len(positive) / sum(1.0 / v for v in positive)

	# Parameters
	quality_levels   = client_message.quality_levels
	quality_bitrates = client_message.quality_bitrates
	buffer_secs      = client_message.buffer_seconds_until_empty
	buffer_max       = client_message.buffer_max_size
	chunk_duration   = client_message.buffer_seconds_per_chunk
	throughput       = client_message.previous_throughput

	# Throughput history
	if _chunk_count > 0 and throughput > 0:
		_throughput_history.append(throughput)

	# Reservoir and cushion thresholds
	reservoir = max(chunk_duration * 3, buffer_max * 0.10)
	upper     = buffer_max * 0.90
	cushion   = upper - reservoir
	if cushion <= 0:
		reservoir = buffer_max * 0.10
		cushion   = buffer_max * 0.80

	if _in_startup:
		quality = 0
		if _chunk_count != 0 and _throughput_history:
			est_tp = _harmonic_mean(_throughput_history[-5:]) * 0.875
			max_downloadable = est_tp * chunk_duration
			for q in range(quality_levels):
				if quality_bitrates[q] > max_downloadable:
					break
				quality = q
		if buffer_secs >= reservoir and _chunk_count > 0:
			_in_startup = False
	else:
		# Buffer-to-rate map f(B)
		rate_min = quality_bitrates[0]
		rate_max = quality_bitrates[-1]
		f_quality = 0
		if buffer_secs >= reservoir + cushion:
			f_quality = quality_levels - 1
		elif buffer_secs > reservoir:
			frac = (buffer_secs - reservoir) / cushion
			target_rate = rate_min + frac * (rate_max - rate_min)
			for q in range(quality_levels):
				if quality_bitrates[q] > target_rate:
					break
				f_quality = q
		# Apply rate limiter
		if f_quality > _prev_quality:
			quality = _prev_quality + 1
			if _throughput_history:
				recent = _throughput_history[-5:]
				est_tp = _harmonic_mean(recent)
				if quality_bitrates[_prev_quality + 1] > est_tp * chunk_duration:
					quality -= 1
		elif f_quality < _prev_quality:
			quality = f_quality
		else:
			quality = _prev_quality

	if buffer_secs < chunk_duration * 1.5: # Low buffer
		quality = 0
	
	quality = max(0, min(quality_levels - 1, quality))

	# Update state
	_prev_quality = quality
	_chunk_count += 1
	return quality