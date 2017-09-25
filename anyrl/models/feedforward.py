"""
Stateless neural network models.
"""

import numpy as np
import tensorflow as tf
from tensorflow.contrib.layers import fully_connected # pylint: disable=E0611

from .base import TFActorCritic
from .util import mini_batches, product

# pylint: disable=E1129

class FeedforwardAC(TFActorCritic):
    """
    A base class for any feed-forward actor-critic model.

    Subclasses should set several attributes on init:
      obs_ph: placeholder for observation batch
      actor_out: actor output batch
      critic_out: critic output batch. Should be of shape
        (None,).
    """
    def __init__(self, session, action_dist, obs_vectorizer):
        """
        Construct a feed-forward model.
        """
        super(FeedforwardAC, self).__init__(session, action_dist, obs_vectorizer)

        # Set these in your constructor.
        self.obs_ph = None
        self.actor_out = None
        self.critic_out = None

    def scale_outputs(self, scale):
        """
        Scale the network outputs by the given amount.

        This may be called right after initializing the
        model to help deal with different reward scales.
        """
        self.critic_out *= scale
        self.actor_out *= scale

    @property
    def stateful(self):
        return False

    def start_state(self, batch_size):
        return None

    def step(self, observations, states):
        feed_dict = {
            self.obs_ph: self.obs_vectorizer.to_vecs(observations)
        }
        act, val = self.session.run((self.actor_out, self.critic_out), feed_dict)
        return {
            'action_params': act,
            'actions': self.action_dist.sample(act),
            'states': None,
            'values': val
        }

    def batch_outputs(self):
        mask = tf.ones(tf.shape(self.critic_out))
        return self.actor_out, self.critic_out, mask

    def batches(self, rollouts, batch_size=None):
        obses, rollout_idxs, timestep_idxs = _frames_from_rollouts(rollouts)
        for mini_indices in mini_batches([1]*len(obses), batch_size):
            sub_obses = [obses[i] for i in mini_indices]
            yield {
                'rollout_idxs': np.take(rollout_idxs, mini_indices),
                'timestep_idxs': np.take(timestep_idxs, mini_indices),
                'feed_dict': {
                    self.obs_ph: self.obs_vectorizer.to_vecs(sub_obses)
                }
            }

class MLP(FeedforwardAC):
    """
    A multi-layer perceptron actor-critic model.
    """
    # pylint: disable=R0913
    def __init__(self, session, action_dist, obs_vectorizer, layer_sizes,
                 activation=tf.nn.relu):
        """
        Create an MLP model.

        Args:
          session: TF session.
          action_dist: an action Distribution.
          obs_vectorizer: an observation SpaceVectorizer.
          layer_sizes: list of hidden layer sizes.
        """
        super(MLP, self).__init__(session, action_dist, obs_vectorizer)

        in_batch_shape = (None,) + obs_vectorizer.out_shape
        self.obs_ph = tf.placeholder(tf.float32, shape=in_batch_shape)

        # Iteratively generate hidden layers.
        layer_in_size = product(obs_vectorizer.out_shape)
        vectorized_shape = (tf.shape(self.obs_ph)[0], layer_in_size)
        layer_in = tf.reshape(self.obs_ph, vectorized_shape)
        for layer_idx, out_size in enumerate(layer_sizes):
            with tf.variable_scope('layer_' + str(layer_idx)):
                layer_in = fully_connected(layer_in, out_size, activation_fn=activation)
            layer_in_size = out_size

        with tf.variable_scope('actor'):
            out_size = product(action_dist.param_shape)
            actor_out = fully_connected(layer_in, out_size,
                                        activation_fn=None,
                                        weights_initializer=tf.zeros_initializer())
            batch = tf.shape(actor_out)[0]
            self.actor_out = tf.reshape(actor_out, (batch,) + action_dist.param_shape)

        with tf.variable_scope('critic'):
            critic_out = fully_connected(layer_in, 1, activation_fn=None)
            self.critic_out = tf.reshape(critic_out, (tf.shape(critic_out)[0],))

def _frames_from_rollouts(rollouts):
    """
    Flatten out the rollouts and produce a list of
    observations, rollout indices, and timestep indices.

    Does not include trailing observations for truncated
    rollouts.

    For example, [[obs1, obs2], [obs3, obs4, obs5]] would
    become ([obs1, obs2, ..., obs5], [0, 0, 1, 1, 1],
    [0, 1, 0, 1, 2])
    """
    all_obs = []
    rollout_indices = []
    timestep_indices = []
    for rollout_idx, rollout in enumerate(rollouts):
        for timestep_idx, obs in enumerate(rollout.step_observations):
            all_obs.append(obs)
            rollout_indices.append(rollout_idx)
            timestep_indices.append(timestep_idx)
    return all_obs, rollout_indices, timestep_indices
