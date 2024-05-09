"""
 Copyright 2023 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """

# pylint: disable=g-bad-todo, abstract-method, consider-using-with, ungrouped-imports
"""Standalone checkpointer - only saves and restores checkpoints at regular intervals, accesses storage needs."""

# Calling jax.device_count here prevents a "TPU platform already registered" error.
# See github.com/google/maxtext/issues/20 for more

import datetime
import os

from typing import Sequence
from absl import app
from flax.linen import partitioning as nn_partitioning
import jax
import numpy as np
import time

import checkpointing
import max_utils
import max_logging
import pyconfig
from train import setup_mesh_and_model, validate_train_config

from layers import models

Transformer = models.Transformer

def checkpoint_loop(config, state=None):
  """Main Checkpointing loop.
  Saves checkpoints.
  Args:
    config:
    state:
    ckpt_path:
  Returns:
  """
  init_rng, writer, checkpoint_manager, mesh, model, _, tx = setup_mesh_and_model(config)

  unboxed_abstract_state, state_mesh_annotations = max_utils.get_abstract_state(model, tx,
                                                config, init_rng, mesh, is_training=True)
  ckpt_read_time = []
  for step in range(config.steps):
    # A barrier to sync all hosts before starting to restore checkpoint
    jax.experimental.multihost_utils.sync_global_devices("Barrier before load")
    checkpoint_load_start = datetime.datetime.now()
    with nn_partitioning.axis_rules(config.logical_axis_rules):
      state, _ = checkpointing.load_state_if_possible(checkpoint_manager,
                                                  config.load_parameters_path,
                                                  config.load_full_state_path,
                                                  unboxed_abstract_state,
                                                  mesh,
                                                  state_mesh_annotations)
    jax.block_until_ready(state)
    checkpoint_load_end = datetime.datetime.now()
    if state is not None: # Checkpoint was available for restore
      time_diff = (checkpoint_load_end-checkpoint_load_start).total_seconds()
      ckpt_read_time.append([jax.process_index(), step, time_diff])
      max_logging.log(f"STANDALONE CHECKPOINTER : Checkpoint restored in: "
                      f"{time_diff}")
    else: # Checkpoint was unavailable, state needs to be initialized
      raise Exception("Checkpoint not available")
    max_logging.log(f"Finished step {step}, sleeping for 20s...")
    time.sleep(20)

  if config.gcs_csv_folder != '':
    max_logging.log("Uploading metrics to GCS")
    csv_file = f"{jax.process_index()}.csv"
    # Update the raw metrics CSV file to GCS.
    metrics_path = os.path.join(config.gcs_csv_folder, config.run_name, csv_file)
    max_utils.upload_csv(csv_file, ckpt_read_time, metrics_path)

  max_utils.close_summary_writer(writer)
  return state

def main(argv: Sequence[str]) -> None:
  jax.config.update('jax_cpu_enable_gloo_collectives', True)
  os.environ["TF_CPP_MIN_LOG_LEVEL"] = "0"
  pyconfig.initialize(argv)
  config = pyconfig.config
  validate_train_config(config)
  print(f"Found {jax.device_count()} devices.")
  print(f"Found {jax.process_count()} processes.")
  print(f"Found {jax.devices()} devices.")
  os.environ["TFDS_DATA_DIR"] = config.dataset_path
  checkpoint_loop(config)

if __name__ == "__main__":
  app.run(main)