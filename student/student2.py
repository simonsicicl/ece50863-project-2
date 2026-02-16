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

import itertools

LOOKAHEAD = 5  # chunks to look ahead
throughput_history = []
prev_quality = 0

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
	# return client_message.quality_levels - 1  # Let's see what happens if we select the highest bitrate every time

	global throughput_history, prev_quality

	quality_levels = client_message.quality_levels
	buffer_secs = client_message.buffer_seconds_until_empty
	buffer_max = client_message.buffer_max_size
	chunk_duration = client_message.buffer_seconds_per_chunk
	quality_bitrates = client_message.quality_bitrates
	upcoming = client_message.upcoming_quality_bitrates
	prev_throughput = client_message.previous_throughput
	qual_coef = client_message.quality_coefficient
	var_coef = client_message.variation_coefficient
	rebuf_coef = client_message.rebuffering_coefficient

	if prev_throughput > 0:
		throughput_history.append(prev_throughput)
	if len(throughput_history) == 0:
		prev_quality = 0
		return 0
	recent = throughput_history[-5:]
	predicted = sum(recent) / len(recent)
	predicted = predicted * 0.7
	chunks = [quality_bitrates]
	for i in range(min(LOOKAHEAD - 1, len(upcoming))):
		chunks.append(upcoming[i])
	window = len(chunks)
	# try all possible quality sequences
	best_qoe = float('-inf')
	best_quality = 0
	for seq in itertools.product(range(quality_levels), repeat=window):
		# simulate this sequence
		buf = buffer_secs
		total_qual = 0
		total_var = 0
		total_rebuf = 0
		last_q = prev_quality
		for i in range(len(seq)):
			chunk_size = chunks[i][seq[i]]
			download_time = chunk_size / predicted if predicted > 0 else float('inf')
			# check for rebuffering
			if download_time > buf:
				total_rebuf += download_time - buf
				buf = 0
			else:
				buf -= download_time
			buf += chunk_duration
			if buf > buffer_max:
				buf = buffer_max
			total_qual += seq[i]
			total_var += abs(seq[i] - last_q)
			last_q = seq[i]
		# calculate QoE
		qoe = (qual_coef * total_qual - var_coef * total_var - rebuf_coef * total_rebuf) / window
		if qoe > best_qoe:
			best_qoe = qoe
			best_quality = seq[0]

	prev_quality = best_quality
	return best_quality
