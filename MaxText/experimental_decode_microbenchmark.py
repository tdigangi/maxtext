"""Tests for a mock version of the engine API, used in integration tests elsewhere.

What should we expect?

Prefill: Doubles the sequence by multiplying it with a weight [2].
Insert: Writes this sequence into a cache row
Generate step: Return sum(prefill_cache) + sum(generate_cache)/weight

I.e. if we prefill [2, 65, 66] (i.e. <BOS>, 'A', 'B') using an ACII vocab,
we should get [4, 130, 132].

If we then insert that and run three generation steps, we should see
266+0 / 2 = 266
266 + [266] /2  = 399
266 + [266, 399] /2 = 598
I.e. ['Ċ', 'Ə', 'ɖ'] when converted back with chr()
"""
import datetime
import sys
import jax
import jax.numpy as jnp
import json
import numpy as np

from jax.experimental.compilation_cache import compilation_cache as cc


import max_utils

import maxengine
from jetstream.engine import token_utils
from absl.testing import absltest

import os
import pyconfig
import sys

import max_logging
import maxtext_utils

def delete_pytree(p):
  def delete_leaf(leaf):
    if isinstance(leaf, jax.Array):
      leaf.delete()
    del leaf
  jax.tree_map(delete_leaf, p)

def profile(func):
  def wrapper(*args, **kwargs):
    max_utils.activate_profiler(config, kwargs["profile_name"])
    start = datetime.datetime.now()
    func(*args, **kwargs)
    end = datetime.datetime.now()
    max_utils.deactivate_profiler(config)
    return (end - start).total_seconds()
  return wrapper

# def print_objects():
#   print(f"Objects {len(gc.get_objects())}")

def summarize_pytree_data(params, name="Params", log=True):
  num_params, total_param_size, avg_param_size = max_utils.summarize_size_from_pytree(params)
  num_params_in_billions = num_params / 1e9
  total_param_size_in_gb = total_param_size / 1e9
  if log:
    max_logging.log(f"{name} stats: \n"
                    f"\tTotal number of params: {num_params_in_billions:.3f} billion \n"
                    f"\tTotal memory usage: {total_param_size_in_gb:.3f} GB \n"
                    f"\tAvg size: {avg_param_size:.3f} bytes\n")
  return num_params, total_param_size, avg_param_size 

@profile
def prefill_benchmark_loop(engine, decode_state, params, tokens, true_length, profile_name="", steps=100):
  for i in range(steps):
    slot = int(i % (jax.device_count() * config.per_device_batch_size))
    prefill_result = engine.prefill(params=params, padded_tokens=tokens, true_length=true_length)
    decode_state = engine.insert(prefill_result, decode_state, slot=slot)
  jax.block_until_ready(decode_state)

def prefill_benchmark(config, engine, params, tokens, true_length, steps=10, num_model_params=None): 
  decode_state = engine.init_decode_state()
  if num_model_params == None:
    num_model_params, _ = summarize_pytree_data(params, name="Params")

  prefill_result = engine.prefill(params=params, padded_tokens=tokens, true_length=true_length)
  decode_state = engine.insert(prefill_result, decode_state, slot=0)
  jax.block_until_ready(decode_state)
  prefill_result = engine.prefill(params=params, padded_tokens=tokens, true_length=true_length)
  decode_state = engine.insert(prefill_result, decode_state, slot=0)
  jax.block_until_ready(decode_state)

  profile_name = f"prefill_{tokens.size}"
  time_in_s = prefill_benchmark_loop(engine, decode_state, params, tokens, true_length, profile_name=profile_name, steps=config.steps)

  prefill_average_ms = 1000 * time_in_s / config.steps
  total_prefill_tflops, _, _ = maxtext_utils.calculate_tflops_prefill(num_model_params, tokens.size, config)
  tflops_per_sec_per_device = total_prefill_tflops / jax.device_count() / prefill_average_ms * 1000.
  print(f"Prefill results:\n"
        f"\tPrefill step average time: {prefill_average_ms:.2f}ms\n"
        f"\tPrefill total TFLOPs: {total_prefill_tflops}\n"
        f"\tPrefill TFLOPs/sec/device: {tflops_per_sec_per_device}\n")
  return {"prefill_time_in_ms": prefill_average_ms, 
          "prefill_total_tflops": total_prefill_tflops, 
          "prefill_tflops_per_sec_per_device": tflops_per_sec_per_device}

@profile
def ar_benchmark_loop(engine, decode_state, params, global_batch_size, profile_name="", steps=100):
  for i in range(config.steps):
    slot = int(i % (global_batch_size))
    # print(f"STEP {i} {slot}")
    decode_state, sampled_tokens = engine.generate(params, decode_state)
    # print_objects()
  jax.block_until_ready(decode_state)


def ar_benchmark(config, engine, params, steps=10, cache_size=None, model_size=None): 
  decode_state = engine.init_decode_state()
  if cache_size == None:
    _, cache_size, _ = summarize_pytree_data(decode_state['cache'], name="Cache")
  if model_size == None:
    _, model_size, _ = summarize_pytree_data(params, name="Params")
  global_batch_size = jax.device_count() * config.per_device_batch_size

  # Warmup
  decode_state, sampled_tokens = engine.generate(params, decode_state)
  jax.block_until_ready(decode_state)
  decode_state, sampled_tokens = engine.generate(params, decode_state)
  jax.block_until_ready(decode_state)


  time_in_s = ar_benchmark_loop(engine, decode_state, params, global_batch_size, profile_name="autoregress", steps=steps)
  seconds_per_step = time_in_s / config.steps
  ar_average_ms = seconds_per_step*1000
  total_throughput = jax.device_count() * config.per_device_batch_size / seconds_per_step

  GB_per_step_per_device = (model_size + cache_size) / 1e9 / jax.device_count()
  bw_per_device = GB_per_step_per_device/seconds_per_step
  print(f"AutoRegressive results:\n"
        f"\tAR step average time: {ar_average_ms:.2f}ms\n"
        f"\tAR global batch size: {global_batch_size}\n"
        f"\tAR throughput: {total_throughput:.2f} tokens/second\n"
        f"\tAR memory bandwidth per device: {bw_per_device:.2f} GB/s")
  return {"ar_step_in_ms": ar_average_ms, 
          "ar_global_batch_size": global_batch_size, 
          "ar_total_throughput_tokens_per_second": total_throughput,
          "ar_device_bandwidth_GB_per_second": bw_per_device}

def main(config):
  engine = maxengine.MaxEngine(config)
  params = engine.load_params()
  prefill_lengths = [128, 256, 512, 1024]
  num_steps = 10
  text = config.prompt
  metadata = engine.get_tokenizer()
  vocab = token_utils.load_vocab(metadata.path, metadata.extra_ids)

  decode_state = engine.init_decode_state()
  delete_pytree(decode_state)
  _, cache_size, _ = summarize_pytree_data(decode_state['cache'], name="Cache")
  num_model_params, model_size, _ = summarize_pytree_data(params, name="Params")
  results = {"config": {}, 
             "sizes": {
                "model_size_in_GB": model_size / 1e9,
                "cache_size_in_GB": cache_size / 1e9,
                "num_model_params_in_billions": num_model_params / 1e9,
             }}
  for k, v in dict(config.get_keys()).items():
    results["config"][k] = str(v) if k == "dtype" else v

  ar_results = ar_benchmark(config, engine, params, steps = num_steps, cache_size=cache_size, model_size=model_size)

  for prefill_length in prefill_lengths:
    tokens, true_length = token_utils.tokenize_and_pad(text, vocab, is_bos=True, prefill_lengths=[prefill_length])
    print(f"Prompt tokenized to size {tokens.size}")
    prefill_results = prefill_benchmark(config, engine, params, tokens, true_length, num_steps, num_model_params)
    prefill_results.update(ar_results)
    results[prefill_length] = prefill_results

  with open("benchmark_results.json", "w") as f:
    json.dump(results, f, indent=2)


if __name__ == "__main__":
  jax.config.update('jax_default_prng_impl', 'unsafe_rbg')
  os.environ["TF_CPP_MIN_LOG_LEVEL"] = "0"
  pyconfig.initialize(sys.argv)
  config = pyconfig.config
  cc.set_cache_dir(os.path.expanduser(config.jax_cache_dir))

  main(config)
