"""
APIs for logging episode rollouts.
"""

import os
import time

import pandas

class EpisodeLogger:
    """
    A handle to an episode log file.

    Logs are CSV files with three columns:
      r: episode reward
      l: episode length (timesteps)
      t: timestamp of episode end, relative to log start.
    """
    def __init__(self, log_path):
        self._start_time = time.time()
        self._columns = ['r', 'l', 't']
        if os.path.isfile(log_path):
            contents = pandas.read_csv(log_path)
            # pylint: disable=C1801
            if len(contents) > 0:
                self._start_time = time.time() - max(contents['t'])
            self._out_file = open(log_path, 'a')
        else:
            self._out_file = open(log_path, 'wt+')
            self._write_header()

    def write_rollouts(self, rollouts):
        """
        Log the completed episodes from the rollouts.
        """
        data = {'r': [], 'l': [], 't': []}
        for rollout in rollouts:
            if rollout.trunc_end:
                continue
            data['r'].append(rollout.total_reward)
            data['l'].append(rollout.total_steps)
            data['t'].append(rollout.end_time - self._start_time)
        # pylint: disable=C1801
        if not data['r']:
            return
        self.write_frame(pandas.DataFrame(data))

    def write_frame(self, frame):
        """
        Write the pandas DataFrame to the end of the log.

        The frame must have r, l, and t columns.
        """
        new_frame = frame.sort_values(by='t')
        data = new_frame.to_csv(columns=self._columns, header=False, index=False)
        self._out_file.write(data)
        self._out_file.flush()

    def close(self):
        """
        Close the log file.
        """
        self._out_file.close()

    def _write_header(self):
        """
        Write the CSV header.
        """
        self._out_file.write(','.join(self._columns) + '\n')
        self._out_file.flush()

    def __enter__(self):
        return self

    def __exit__(self, _, value, traceback):
        self.close()
