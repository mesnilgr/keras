from __future__ import absolute_import
from __future__ import print_function
import theano
import theano.tensor as T
import numpy as np
import warnings
import time
from collections import deque

from .utils.generic_utils import Progbar

class CallbackList(object):

    def __init__(self, callbacks, queue_length=10):
        self.callbacks = callbacks
        self.queue_length = queue_length

    def append(self, callback):
        self.callbacks.append(callback)

    def _set_params(self, params):
        for callback in self.callbacks:
            callback._set_params(params)

    def _set_model(self, model):
        for callback in self.callbacks:
            callback._set_model(model)

    def on_epoch_begin(self, epoch, logs={}):
        for callback in self.callbacks:
            callback.on_epoch_begin(epoch, logs)
        self._delta_t_batch = 0.
        self._delta_ts_batch_begin = deque([], maxlen=self.queue_length)
        self._delta_ts_batch_end = deque([], maxlen=self.queue_length)

    def on_epoch_end(self, epoch, logs={}):
        for callback in self.callbacks:
            callback.on_epoch_end(epoch, logs)

    def on_batch_begin(self, batch, logs={}):
        t_before_callbacks = time.time()
        for callback in self.callbacks:
            callback.on_batch_begin(batch, logs)
        self._delta_ts_batch_begin.append(time.time() - t_before_callbacks)
        delta_t_median = np.median(self._delta_ts_batch_begin)
        if self._delta_t_batch > 0. and delta_t_median > 0.95 * self._delta_t_batch \
            and delta_t_median > 0.1:
            warnings.warn('Method on_batch_begin() is slow compared '
                'to the batch update (%f). Check your callbacks.' % delta_t_median)
        self._t_enter_batch = time.time()

    def on_batch_end(self, batch, logs={}):
        self._delta_t_batch = time.time() - self._t_enter_batch
        t_before_callbacks = time.time()
        for callback in self.callbacks:
            callback.on_batch_end(batch, logs)
        self._delta_ts_batch_end.append(time.time() - t_before_callbacks)
        delta_t_median = np.median(self._delta_ts_batch_end)
        if self._delta_t_batch > 0. and delta_t_median > 0.95 * self._delta_t_batch \
            and delta_t_median > 0.1:
            warnings.warn('Method on_batch_end() is slow compared '
                'to the batch update (%f). Check your callbacks.' % delta_t_median)

    def on_train_begin(self, logs={}):
        for callback in self.callbacks:
            callback.on_train_begin(logs)

    def on_train_end(self, logs={}):
        for callback in self.callbacks:
            callback.on_train_end(logs)


class Callback(object):

    def __init__(self):
        pass

    def _set_params(self, params):
        self.params = params

    def _set_model(self, model):
        self.model = model

    def on_epoch_begin(self, epoch, logs={}):
        pass

    def on_epoch_end(self, epoch, logs={}):
        pass

    def on_batch_begin(self, batch, logs={}):
        pass

    def on_batch_end(self, batch, logs={}):
        pass

    def on_train_begin(self, logs={}):
        pass

    def on_train_end(self, logs={}):
        pass

class BaseLogger(Callback):

    def on_train_begin(self, logs={}):
        self.verbose = self.params['verbose']

    def on_epoch_begin(self, epoch, logs={}):
        if self.verbose:
            print('Epoch %d' % epoch)
            self.progbar = Progbar(target=self.params['nb_sample'], \
                verbose=self.verbose)
        self.current = 0
        self.tot_loss = 0.
        self.tot_acc = 0.

    def on_batch_begin(self, batch, logs={}):
        if self.current < self.params['nb_sample']:
            self.log_values = []

    def on_batch_end(self, batch, logs={}):
        batch_size = logs.get('size', 0)
        self.current += batch_size

        loss = logs.get('loss')
        self.log_values.append(('loss', loss))
        self.tot_loss += loss * batch_size
        if self.params['show_accuracy']:
            accuracy = logs.get('accuracy')
            self.log_values.append(('acc.', accuracy))
            self.tot_acc += accuracy * batch_size
        # skip progbar update for the last batch; will be handled by on_epoch_end
        if self.verbose and self.current < self.params['nb_sample']:
            self.progbar.update(self.current, self.log_values)

    def on_epoch_end(self, epoch, logs={}):
        self.log_values.append(('loss', self.tot_loss / self.current))
        if self.params['show_accuracy']:
            self.log_values.append(('acc.', self.tot_acc / self.current))
        if self.params['do_validation']:
            val_loss = logs.get('val_loss')
            self.log_values.append(('val. loss', val_loss))
            if self.params['show_accuracy']:
                val_acc = logs.get('val_accuracy')
                self.log_values.append(('val. acc.', val_acc))
        self.progbar.update(self.current, self.log_values)


class History(Callback):

    def on_train_begin(self, logs={}):
        self.epoch = []
        self.loss = []
        if self.params['show_accuracy']:
            self.accuracy = []
        if self.params['do_validation']:
            self.validation_loss = []
            if self.params['show_accuracy']:
                self.validation_accuracy = []

    def on_epoch_begin(self, epoch, logs={}):
        self.seen = 0
        self.tot_loss = 0.
        self.tot_accuracy = 0.

    def on_batch_end(self, batch, logs={}):
        batch_size = logs.get('size', 0)
        self.seen += batch_size
        self.tot_loss += logs.get('loss', 0.) * batch_size
        if self.params['show_accuracy']:
            self.tot_accuracy += logs.get('accuracy', 0.) * batch_size

    def on_epoch_end(self, epoch, logs={}):
        val_loss = logs.get('val_loss')
        val_acc = logs.get('val_accuracy')
        self.epoch.append(epoch)
        self.loss.append(self.tot_loss / self.seen)
        if self.params['show_accuracy']:
            self.accuracy.append(self.tot_accuracy / self.seen)
        if self.params['do_validation']:
            self.validation_loss.append(val_loss)
            if self.params['show_accuracy']:
                self.validation_accuracy.append(val_acc)
