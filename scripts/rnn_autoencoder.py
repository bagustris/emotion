#!/usr/bin/python

"""A TensorFlow 2 implementation of the auDeep representation learning
framework. Original implementation is available at
https://github.com/auDeep/auDeep.

References:
[1] S. Amiriparian, M. Freitag, N. Cummins, and B. Schuller, 'Sequence
to sequence autoencoders for unsupervised representation learning from
audio', 2017.
[2] M. Freitag, S. Amiriparian, S. Pugachevskiy, N. Cummins, and B.
Schuller, 'auDeep: Unsupervised learning of representations from audio
with deep recurrent neural networks', The Journal of Machine Learning
Research, vol. 18, no. 1, pp. 6340–6344, 2017.
"""

import argparse
from pathlib import Path

import netCDF4
import tensorflow as tf
from tensorflow.keras import Model
from tensorflow.keras.layers import (RNN, AbstractRNNCell, Bidirectional,
                                     Dense, GRUCell, Input, concatenate)
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import Callback

from emotion_recognition.dataset import NetCDFDataset


class _RNNCallback(Callback):
    def __init__(self, data: tf.data.Dataset, log_dir: str = 'logs',
                 checkpoint=False):
        super().__init__()
        self.data = data
        if self.data.element_spec[0].shape.ndims != 3:
            raise ValueError("Dataset elements must be batched (i.e. of shape "
                             "[batch, step, freq]).")
        self.log_dir = log_dir
        self.checkpoint = checkpoint
        train_log_dir = str(Path(log_dir) / 'train')
        valid_log_dir = str(Path(log_dir) / 'valid')
        self.train_writer = tf.summary.create_file_writer(train_log_dir)
        self.valid_writer = tf.summary.create_file_writer(valid_log_dir)

    def on_epoch_end(self, epoch, logs=None):
        super().on_epoch_end(epoch, logs)

        with self.valid_writer.as_default():
            tf.summary.scalar('rmse', logs['val_rmse'], step=epoch)

            batch, _ = next(iter(self.data))
            reconstruction, representation = self.model(batch, training=False)
            reconstruction = reconstruction[:, ::-1, :]
            images = tf.concat([batch, reconstruction], 2)
            images = tf.expand_dims(images, -1)
            images = (images + 1) / 2
            tf.summary.image('combined', images, step=epoch, max_outputs=20)
            tf.summary.histogram('representation', representation, step=epoch)

        with self.train_writer.as_default():
            tf.summary.scalar('rmse', logs['rmse'], step=epoch)

        if (epoch + 1) % 10 == 0 and self.checkpoint:
            save_path = str(Path(self.log_dir) / 'model-{:03d}'.format(
                epoch + 1))
            self.model.save_weights(save_path)


def _dropout_gru_cell(units: int = 256,
                      keep_prob: float = 0.8) -> AbstractRNNCell:
    return tf.nn.RNNCellDropoutWrapper(GRUCell(units), 0.8, 0.8)


def _make_rnn(units: int = 256, layers: int = 2, bidirectional: bool = False,
              dropout: float = 0.2, name='rnn') -> RNN:
    cells = [_dropout_gru_cell(units, 1 - dropout) for _ in range(layers)]
    rnn = RNN(cells, return_sequences=True, return_state=True, name=name)
    return Bidirectional(rnn, name=name) if bidirectional else rnn


class TimeRecurrentAutoencoder(Model):
    def train_step(self, data):
        x, _ = data
        with tf.GradientTape() as tape:
            reconstruction, _ = self(x, training=True)
            targets = x[:, ::-1, :]
            loss = tf.sqrt(tf.reduce_mean(tf.square(targets - reconstruction)))

        trainable_vars = self.trainable_variables
        gradients = tape.gradient(loss, trainable_vars)
        clipped_gvs = [tf.clip_by_value(x, -2, 2) for x in gradients]
        self.optimizer.apply_gradients(zip(clipped_gvs, trainable_vars))

        return {'rmse': loss}

    def test_step(self, data):
        x, _ = data
        reconstruction, _ = self(x, training=False)
        targets = x[:, ::-1, :]
        loss = tf.sqrt(tf.reduce_mean(tf.square(targets - reconstruction)))

        return {'rmse': loss}


def create_rnn_model(input_shape: tuple,
                     units: int = 256,
                     layers: int = 2,
                     bidirectional_encoder: bool = False,
                     bidirectional_decoder: bool = False
                     ) -> TimeRecurrentAutoencoder:
    inputs = Input(input_shape)
    time_steps, features = input_shape

    # Make encoder layers
    enc = _make_rnn(units, layers, bidirectional_encoder, name='encoder')
    _, *enc_states = enc(inputs)
    # Concatenate output of layers
    encoder = concatenate(enc_states, name='encoder_output_state')

    # Fully connected needs to have output dimension equal to dimension of
    # decoder state
    dec_dim = units * layers
    if bidirectional_decoder:
        dec_dim *= 2
    representation = Dense(dec_dim, activation='tanh', name='representation')(
        encoder)

    # Initial state of decoder
    decoder_init = tf.split(
        representation, 2 * layers if bidirectional_decoder else layers,
        axis=-1
    )
    # Decoder input is reversed and shifted input sequence
    targets = inputs[:, ::-1, :]
    dec_inputs = targets[:, :time_steps - 1, :]
    dec_inputs = tf.pad(dec_inputs, [[0, 0], [1, 0], [0, 0]],
                        name='decoder_input_sequence')

    # Make decoder layers and init with output from fully connected layer
    dec1 = _make_rnn(units, layers, bidirectional_decoder, name='decoder')
    dec_seq, *_ = dec1(dec_inputs, initial_state=decoder_init)
    # Concatenate output of layers
    decoder = (dec_seq)

    reconstruction = Dense(features, activation='tanh',
                           name='reconstruction')(decoder)

    model = TimeRecurrentAutoencoder(
        inputs=inputs, outputs=[reconstruction, representation])
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--logs', type=Path, default='logs/rae',
                        help="Directory to store TensorBoard logs.")
    parser.add_argument('--epochs', type=int, default=50,
                        help="Number of epochs to train for.")
    parser.add_argument('--dataset', type=Path, required=True,
                        help="File containing spectrogram data.")
    parser.add_argument('--valid_fraction', type=float, default=0.1,
                        help="Fraction of data to use as validation data.")
    parser.add_argument('--learning_rate', type=float, default=0.001,
                        help="Learning rate.")
    parser.add_argument('--batch_size', type=int, default=64,
                        help="Batch size.")

    parser.add_argument('--units', type=int, default=256,
                        help="Dimensionality of RNN cells.")
    parser.add_argument('--layers', type=int, default=2,
                        help="Number of stacked RNN layers.")
    parser.add_argument('--bidirectional_encoder', action='store_true',
                        help="Use a bidirectional encoder.")
    parser.add_argument('--bidirectional_decoder', action='store_true',
                        help="Use a bidirectional decoder.")
    args = parser.parse_args()

    args.logs.parent.mkdir(parents=True, exist_ok=True)

    # dataset = NetCDFDataset('jl/output/spectrogram-120.nc')
    dataset = netCDF4.Dataset(str(args.dataset))
    x = tf.constant(dataset.variables['features'])
    data = tf.data.Dataset.from_tensor_slices((x, x)).shuffle(
        1500, reshuffle_each_iteration=False)
    n_valid = int(len(x) * args.valid_fraction)
    valid_data = data.take(n_valid).batch(64)
    train_data = data.skip(n_valid).take(-1).shuffle(1500).batch(64)

    model = create_rnn_model(
        x[0].shape, units=args.units, layers=args.layers,
        bidirectional_encoder=args.bidirectional_encoder,
        bidirectional_decoder=args.bidirectional_decoder
    )
    model.compile(optimizer=Adam(learning_rate=args.learning_rate))
    model.summary()
    model.fit(
        train_data, validation_data=valid_data, epochs=args.epochs, callbacks=[
            _RNNCallback(valid_data.take(1), log_dir=str(args.logs))
        ]
    )


if __name__ == "__main__":
    main()
